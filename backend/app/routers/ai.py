# -*- coding: utf-8 -*-
"""
AI 教学助手 API:配置管理、连接测试、智能对话、数据导出、
考试 Excel 导入、评语生成、智能预警、智能均衡分组
(从 Flask main.py 1:1 迁移,响应 JSON 契约与 msg 文案逐字一致)
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import ensure_data_dir
from app.database import GROUP_COLORS
from app.deps import get_class_id, get_db, get_body
from app.services import ai_service, report_service
from app.utils import _parse_exam_excel, ai_key_encode

router = APIRouter(prefix="/api/ai", tags=["ai"])

DATA_DIR = ensure_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
TEMP_DIR = DATA_DIR / "temp"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 存储最近一次上传的考试数据（内存缓存，用于 AI 对话上下文）
_exam_data_cache = {}  # key: class_id -> parsed exam data


# ============================================================
# AI 配置 API
# ============================================================
@router.get("/config")
def api_get_ai_config(db: sqlite3.Connection = Depends(get_db)):
    """获取 AI 配置（API Key 脱敏）"""

    config = ai_service._get_ai_config(db)
    raw_key = config.get("api_key", "")
    masked = ""
    if raw_key:
        if len(raw_key) > 4:
            masked = raw_key[:4] + "*" * (len(raw_key) - 4)
        else:
            masked = raw_key[:2] + "**"
    return {
        "code": 0,
        "data": {
            "provider": config["provider"],
            "api_key_masked": masked,
            "has_key": bool(raw_key),
            "base_url": config.get("base_url", ""),
            "model": config["model"],
        }
    }


@router.post("/config")
def api_save_ai_config(
    data: dict = Depends(get_body),
     db: sqlite3.Connection = Depends(get_db)):
    """保存 AI 配置"""

    provider = data.get("provider", "deepseek").strip()
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "").strip()

    if provider not in ("deepseek", "openai", "qwen", "custom"):
        return JSONResponse({"code": 1, "msg": "无效的 AI 服务商"}, status_code=400)
    if provider == "custom" and not base_url:
        return JSONResponse(
            {"code": 1, "msg": "自定义服务商需填写 Base URL"}, status_code=400)
    if not api_key:
        return JSONResponse(
            {"code": 1, "msg": "API Key 不能为空"}, status_code=400)
    if not model:
        return JSONResponse({"code": 1, "msg": "模型名称不能为空"}, status_code=400)
    db.execute(
    "INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_provider',?)",
    (provider,
    ))
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_api_key',?)",
               (ai_key_encode(api_key),))
    db.execute(
    "INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_base_url',?)",
    (base_url,
    ))
    db.execute(
    "INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_model',?)", (model,))
    db.commit()

    return {"code": 0, "msg": "AI 配置已保存"}


@router.post("/test")
async def api_ai_test(
    data: dict = Depends(get_body),
    db: sqlite3.Connection = Depends(get_db)):
    """测试 AI 连接"""
    # 可用前端传的临时配置测试，未传则用已保存配置
    provider = data.get("provider", "").strip()
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "").strip()

    if provider:
        config = {
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }
    else:
        config = ai_service._get_ai_config(db)

    success, content = await run_in_threadpool(
        ai_service._call_llm, config,
        [{"role": "user", "content": "你好，请回复'连接成功'这两个字，不要其他内容。"}],
        15,
    )

    if success:
        return {"code": 0, "msg": "连接成功 🟢", "data": {"reply": content.strip()}}
    else:
        return JSONResponse(
            {"code": 1, "msg": f"连接失败 🔴 {content}"}, status_code=400)


# ============================================================
# 动态提问建议 API
# ============================================================
@router.get("/suggestions")
def api_ai_suggestions(homework_type_id: int = 0,
                       cid: int = Depends(get_class_id),
                       db: sqlite3.Connection = Depends(get_db)):
    """返回基于当前数据的智能提问建议"""

    hw_type_id = homework_type_id or 0

    today = datetime.now().strftime("%Y-%m-%d")
    total = db.execute(
    "SELECT COUNT(*) as c FROM students WHERE class_id=?",
    (cid,
    )).fetchone()["c"]

    # 构建作业种类过滤条件
    hw_type_join = ""
    hw_type_where = ""
    hw_type_params_extra = ()
    if hw_type_id > 0:
        hw_type_join = " JOIN homework_types ht ON h.homework_type_id = ht.id"
        hw_type_where = " AND h.homework_type_id = ?"
        hw_type_params_extra = (hw_type_id,)

    # 基于数据动态生成建议
    suggestions = []

    # 基础问题
    suggestions.append({"text": "今天哪个组表现最好？", "icon": "🏆"})
    suggestions.append({"text": "最近一周的提交率趋势如何？", "icon": "📈"})
    suggestions.append({"text": "今天的作业等级分布是怎样的？", "icon": "🍩"})

    # 数据驱动的问题
    if total > 0:
        # 找到A率最高和最低的组
        groups = db.execute(
            "SELECT id, name FROM groups_info WHERE class_id=? ORDER BY sort_order", (
                cid,)
        ).fetchall()
        if groups:
            # 有分组数据时，生成具体问题
            best_name = None
            best_rate = -1
            worst_name = None
            worst_rate = 101
            for g in groups:
                gs = db.execute(
                    "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (
                        g["id"], cid)
                ).fetchone()["c"]
                if gs == 0:
                    continue
                ga = db.execute(f"""
                    SELECT COUNT(DISTINCT h.student_id) as c FROM homework h JOIN students s ON h.student_id=s.id
                    {hw_type_join}
                    WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=? {hw_type_where}
                """, (today, g["id"], cid) + hw_type_params_extra).fetchone()["c"]
                rate = round(ga / gs * 100, 1) if gs > 0 else 0
                if rate > best_rate:
                    best_rate = rate
                    best_name = g["name"]
                if rate < worst_rate:
                    worst_rate = rate
                    worst_name = g["name"]

            if best_name and worst_name and best_name != worst_name:
                suggestions.append({
                    "text": f"为什么{best_name}表现这么好？对比一下{worst_name}",
                    "icon": "🔍",
                })

        # 检查是否有连续未交的学生
        students = db.execute(
            "SELECT s.id, s.name FROM students s WHERE s.class_id=? ORDER BY s.id", (
                cid,)
        ).fetchall()
        at_risk_names = []
        for s in students:
            rows = db.execute(f"""
                SELECT h.grade FROM homework h
                {hw_type_join}
                WHERE h.student_id=? {hw_type_where}
                ORDER BY h.date DESC LIMIT 5
            """, (s["id"],) + hw_type_params_extra).fetchall()
            cx = 0
            for r in rows:
                if r["grade"] == "X":
                    cx += 1
                else:
                    break
            if cx >= 3:
                at_risk_names.append(s["name"])

        if at_risk_names:
            suggestions.append({
                "text": f"哪些学生需要特别关注？（如{at_risk_names[0]}）",
                "icon": "⚠️",
            })
        else:
            suggestions.append({"text": "对比本周和上周的作业表现", "icon": "📉"})

    # 学生个体问题
    if total > 0:
        suggestions.append({"text": "帮我分析一下整体学情，哪些学生进步最大？", "icon": "🌟"})

    # 去重并限制数量
    seen = set()
    unique = []
    for s in suggestions:
        if s["text"] not in seen:
            seen.add(s["text"])
            unique.append(s)
    suggestions = unique[:8]

    return {"code": 0, "data": {"suggestions": suggestions}}


# ============================================================
# AI 对话 API
# ============================================================
@router.post("/chat")
async def api_ai_chat(data: dict = Depends(get_body), cid: int = Depends(get_class_id),
                      db: sqlite3.Connection = Depends(get_db)):
    """AI 对话接口：分析问题 + 获取数据 + 调用 LLM + 返回图表"""

    question = (data.get("question") or "").strip()
    if not question:
        return JSONResponse({"code": 1, "msg": "请输入问题"}, status_code=400)
    hw_type_id = data.get("homework_type_id", 0) or 0
    config = ai_service._get_ai_config(db)

    # 1. 提取意图和上下文数据
    context = ai_service._extract_intent(question, db, cid, hw_type_id)

    # 1.5 如果有缓存的考试数据，合并到上下文中
    exam_cache = _exam_data_cache.get(str(cid))
    if exam_cache:
        context["exam_data"] = exam_cache["data"]
        context["has_exam_data"] = True

    data_prompt = ai_service._build_data_prompt(context)

    # 2. 服务端自动构建图表兜底（当 LLM 无法生成 HTML 时使用）
    auto_chart = ai_service._build_chart_from_context(context)

    # 3. 构建 LLM prompt — LLM 自由生成 HTML 可视化面板
    system_prompt = """你是 ClassTrack 的 AI 教学助手。你必须严格遵守以下格式回复。

## 回复格式（不可违反）
你的每个回复必须包含两部分，用单独一行 `---VIZ---` 分隔：

第一段：文字分析（必填，2-5句话，中文）
- 直接回应老师的问题
- 引用具体数据（组名、数字、百分比）
- 给出可操作的建议

第二段：HTML 可视化面板
- 如果问题适合可视化（对比、分布、趋势、排名等），生成 HTML
- 如果只是闲聊或简单问答，第二段留空（但 `---VIZ---` 分隔符必须保留）

## HTML 可视化规范
- 使用 inline CSS，马卡龙配色：卡片 #fff，主色 #7EB5D6，强调 #E8A0BF，成功 #A8D5BA，警告 #F4C97E，背景 #f8f6f5
- 可以包含：统计卡片数字、ECharts图表、表格、进度条、标签
- ECharts 变量 `echarts` 已全局可用，图表容器用 id="viz_chart_1"、id="viz_chart_2" 等
- 每个图表容器必须有明确的 width 和 height（如 style="width:100%;height:280px"）
- 使用 `<script>` 标签初始化 ECharts，放在 HTML 末尾
- ★ ECharts 初始化必须监听 'echartsReady' 事件（或直接用 DOMContentLoaded），不要使用 window.onload 赋值！
- 可视化要突出关键发现（最好/最差高亮、趋势箭头、异常标注）
- 示例脚本写法（二选一）：

  方式1（推荐，等待 echarts 就绪）：
  <script>
  window.addEventListener('echartsReady', function() {
    var dom = document.getElementById('viz_chart_1');
    if (dom && typeof echarts !== 'undefined') {
      var chart = echarts.init(dom);
      chart.setOption({ ... });
    }
  });
  </script>

  方式2（echarts 已在脚本之前注入，直接执行）：
  <script>
  (function() {
    var dom = document.getElementById('viz_chart_1');
    if (dom && typeof echarts !== 'undefined') {
      var chart = echarts.init(dom);
      chart.setOption({ ... });
    }
  })();
  </script>"""

    user_prompt = f"""以下是当前班级数据：

{data_prompt}

老师的问题是：{question}

请严格遵守格式回复（文字分析 + ---VIZ--- + HTML面板）。"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 4. 调用 LLM
    success, content = await run_in_threadpool(ai_service._call_llm, config, messages)

    # 5. 解析回复：文字 + HTML 可视化
    reply = ""
    viz_html = None
    chart = auto_chart  # 兜底

    if success:
        # 按 ---VIZ--- 分隔
        viz_split = re.split(r'\n?---VIZ---\n?', content, maxsplit=1)

        if len(viz_split) == 2:
            reply = viz_split[0].strip()
            viz_raw = viz_split[1].strip()

            # 提取 HTML（支持有/无 ```html 包裹）
            html_match = re.search(
    r'```html?\s*\n(.*?)\n```', viz_raw, re.DOTALL)
            if html_match:
                viz_html = html_match.group(1).strip()
            elif viz_raw and viz_raw[0] == '<':
                viz_html = viz_raw
        else:
            # LLM 没有用 ---VIZ--- 分隔，整体作为回复
            reply = content.strip()

        # 兜底：如果回复为空，根据数据生成自动摘要
        if not reply:
            reply = ai_service._generate_fallback_reply(context, question)

        # 如果 LLM 没生成 HTML，用服务端图表
        if viz_html and len(viz_html) > 50:
            chart = None  # 用 viz_html 替代 chart
        elif not viz_html and chart:
            pass  # 用服务端图表

        # 兼容旧图表格式
        chart_match = re.search(r'```chart\s*\n(.*?)\n```', content, re.DOTALL)
        if chart_match:
            try:
                chart = json.loads(chart_match.group(1))
                if not reply:
                    reply = content[:chart_match.start()].strip()
            except json.JSONDecodeError:
                pass
    else:
        reply = f"❌ {content}"

    # 确保 reply 至少有一段文字
    if not reply:
        reply = ai_service._generate_fallback_reply(context, question)

    return {
        "code": 0 if success else 1,
        "data": {
            "reply": reply,
            "chart": chart,
            "viz_html": viz_html,
            "follow_ups": ai_service._generate_follow_ups(context, question),
            "export_data": {
                "class_name": context.get("class_name", ""),
                "date": context.get("date", ""),
                "grade_counts": context.get("grade_counts", {}),
                "group_data": context.get("group_data", []),
                "trend": context.get("trend", []),
                "total_students": context.get("total_students", 0),
            },
            "context": {
                "intents": context.get("intents", []),
                "date": context["date"],
            }
        }
    }


# ============================================================
# AI 数据导出 API
# ============================================================
@router.post("/export/excel")
def api_ai_export_excel(data: dict = Depends(get_body)):
    """将当前 AI 对话的数据导出为 Excel"""

    export_data = data.get("export_data", {})
    title = data.get("title", "AI分析报告")

    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")

    file_path = TEMP_DIR / \
        f"AI分析报告_{class_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    report_service.build_ai_excel(export_data, title, file_path)

    return FileResponse(
        str(file_path),
        filename=f"AI分析报告_{class_name}_{date_str}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/export/word")
def api_ai_export_word(data: dict = Depends(get_body)):
    """将当前 AI 对话的数据导出为 Word（HTML格式，Word可直接打开）"""

    export_data = data.get("export_data", {})
    reply = data.get("reply", "")
    viz_html = data.get("viz_html", "")

    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")

    file_path = TEMP_DIR / \
        f"AI分析报告_{class_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.doc"
    report_service.build_ai_word_doc(export_data, reply, viz_html, file_path)

    return FileResponse(
        str(file_path),
        filename=f"AI分析报告_{class_name}_{date_str}.doc",
        media_type="application/msword",
    )


# ============================================================
# 考试 Excel 导入 API
# ============================================================
@router.post("/import-exam")
async def api_ai_import_exam(file: UploadFile | None = File(None),
                             cid: int = Depends(get_class_id)):
    """上传考试 Excel 并智能解析"""

    if not file:
        return JSONResponse(
            {"code": 1, "msg": "请选择 Excel 文件"}, status_code=400)
    if file.filename == "":
        return JSONResponse({"code": 1, "msg": "文件名为空"}, status_code=400)
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return JSONResponse(
            {"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}, status_code=400)
    filename = Path(file.filename).name
    file_path = UPLOAD_DIR / \
        f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file_path.write_bytes(await file.read())

    try:
        result = _parse_exam_excel(str(file_path))
    except Exception as e:
        try:
            file_path.unlink()
        except Exception:
            pass
        return JSONResponse(
            {"code": 1, "msg": f"解析 Excel 失败: {str(e)}"}, status_code=400)

    if "error" in result:
        try:
            file_path.unlink()
        except Exception:
            pass
        return JSONResponse(
            {"code": 1, "msg": result["error"]}, status_code=400)

    # 缓存到内存
    _exam_data_cache[str(cid)] = {
        "source_file": filename,
        "data": result,
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 清理临时文件
    try:
        file_path.unlink()
    except Exception:
        pass

    return {
        "code": 0,
        "msg": f"已识别 {result['total_students']} 名学生，{len(result['classes'])} 个班级/组别",
        "data": result,
    }


@router.get("/exam-data")
def api_ai_exam_data(cid: int = Depends(get_class_id)):
    """获取当前缓存的考试数据"""

    cached = _exam_data_cache.get(str(cid))
    if not cached:
        return {"code": 0, "data": None, "msg": "暂无考试数据"}
    return {"code": 0, "data": cached}


@router.post("/exam-data/clear")
def api_ai_exam_data_clear(cid: int = Depends(get_class_id)):
    """清除缓存的考试数据"""

    _exam_data_cache.pop(str(cid), None)
    return {"code": 0, "msg": "考试数据已清除"}


@router.post("/import-exam/apply")
def api_ai_import_exam_apply(data: dict = Depends(get_body), cid: int = Depends(get_class_id),
                                   db: sqlite3.Connection = Depends(get_db)):
    """将解析好的考试数据导入到 exam_scores 表（根据学号或姓名匹配学生）"""

    cached = _exam_data_cache.get(str(cid))
    if not cached:
        return JSONResponse(
            {"code": 1, "msg": "没有缓存的考试数据，请先上传 Excel"}, status_code=400)
    target_class_name = (data.get("class_name") or "").strip()
    exam_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    exam_data = cached["data"]

    # 获取当前班级的所有学生
    all_students = db.execute(
        "SELECT id, name, student_code FROM students WHERE class_id=?", (cid,)
    ).fetchall()

    # 建立匹配索引：学号 → id, 姓名 → id
    code_to_id = {}
    name_to_id = {}
    for s in all_students:
        if s["student_code"]:
            code_to_id[s["student_code"].strip()] = s["id"]
        name_to_id[s["name"].strip()] = s["id"]

    matched = 0
    unmatched = []
    total = 0

    for cls in exam_data["classes"]:
        if target_class_name and cls.get("name", "") != target_class_name:
            continue
        exam_name = cls.get(
    "name",
    "") or cached.get(
        "source_file",
        "考试").rsplit(
            ".",
             1)[0]
        total_score = float(cls.get("total_score", 100))

        for s in cls["students"]:
            total += 1
            student_id = None

            # 优先用学号匹配
            if s.get("code") and s["code"] in code_to_id:
                student_id = code_to_id[s["code"]]
            elif s.get("name") in name_to_id:
                student_id = name_to_id[s["name"]]
            else:
                clean_name = (
    s.get("name") or "").replace(
        " ",
        "").replace(
            "\t",
             "")
                for name, sid in name_to_id.items():
                    if name.replace(" ", "") == clean_name:
                        student_id = sid
                        break

            if student_id:
                score = float(s.get("score", 0)) if s.get(
                    "score") is not None else 0
                grade = s.get("grade", "")
                if not grade and total_score > 0:
                    pct = score / total_score * 100
                    if pct >= 90: grade = "A"
                    elif pct >= 75: grade = "B"
                    elif pct >= 60: grade = "C"
                    else: grade = "D"
                db.execute("""
                    INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ON CONFLICT DO UPDATE SET
                        score=excluded.score, total_score=excluded.total_score,
                        grade=excluded.grade, updated_at=datetime(
                            'now','localtime')
                """, (student_id, cid, exam_date, exam_name, score, total_score, grade))
                matched += 1
            else:
                unmatched.append({"name": s.get("name", ""),
                                  "reason": "未在系统中找到该学生（学号或姓名不匹配）"})

    db.commit()

    return {
        "code": 0,
        "msg": f"已导入 {matched} 条成绩（{exam_date}），{len(unmatched)} 条未匹配",
        "data": {
            "matched": matched,
            "unmatched_count": len(unmatched),
            "unmatched_preview": unmatched[:10],
            "total_processed": total,
            "date": exam_date,
        }
    }


# ============================================================
# AI 评语生成
# ============================================================
@router.get("/comment/{sid}")
def api_ai_comment(sid: int, cid: int = Depends(get_class_id),
                   db: sqlite3.Connection = Depends(get_db)):
    """为学生生成 AI 评语"""

    config = ai_service._get_ai_config(db)

    # 获取学生信息
    student = db.execute(
        "SELECT s.*, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.id = ? AND s.class_id = ?",
        (sid, cid)
    ).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)

    # 获取近30天作业记录
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = db.execute("""
        SELECT h.date, h.grade FROM homework h
        WHERE h.student_id = ? AND h.date >= ?
        ORDER BY h.date DESC
    """, (sid, start_date)).fetchall()

    stats = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for r in rows:
        stats[r["grade"]] = stats.get(r["grade"], 0) + 1
    total = sum(stats.values())
    a_rate = round(stats["A"] / total * 100, 1) if total > 0 else 0
    submit_rate = round(
        (total - stats["X"]) / total * 100,
        1) if total > 0 else 0

    # 检测连续未交
    grades_list = [r["grade"] for r in rows]
    consecutive_x = 0
    for g in grades_list:
        if g == "X":
            consecutive_x += 1
        else:
            break

    # 构建 prompt
    student_info = f"""学生姓名: {student['name']}
所属分组: {student['group_name'] or '未分组'}
近30天记录数: {total} 次
A: {stats['A']}次, B: {stats['B']}次, C: {stats['C']}次, 请假: {stats['L']}次, 未交: {stats['X']}次
提交率: {submit_rate}%, A率: {a_rate}%"""


    if consecutive_x >= 2:
        student_info += f"\n⚠️ 已连续 {consecutive_x} 天未交作业"

    prompt = f"""请为以下学生写一段期末评语（50-80字），语气鼓励、建设性：

{student_info}

要求：使用中文，包含学生姓名，肯定优点，提出1-2条改进建议，适合发给家长。"""
    success, content = ai_service._call_llm(config, [
        {"role": "user", "content": prompt}
    ])

    if not success:
        return JSONResponse({"code": 1, "msg": content}, status_code=500)
    return {
        "code": 0,
        "data": {
            "student_name": student["name"],
            "comment": content.strip(),
            "stats": {
                "total": total, "A": stats["A"], "B": stats["B"],
                "C": stats["C"], "X": stats["X"],
                "a_rate": a_rate, "submit_rate": submit_rate,
                "consecutive_x": consecutive_x,
            }
        }
    }


# ============================================================
# 智能预警 API
# ============================================================
@router.get("/alerts")
def api_ai_alerts(cid: int = Depends(get_class_id),
                  db: sqlite3.Connection = Depends(get_db)):
    """获取智能预警信息"""

    alerts = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 连续未交 ≥3 天检测
    students = db.execute(
        "SELECT s.id, s.name, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id=g.id WHERE s.class_id=?",
        (cid,)
    ).fetchall()

    consecutive_missing = []
    for s in students:
        rows = db.execute("""
            SELECT h.date, h.grade FROM homework h
            WHERE h.student_id=?
            ORDER BY h.date DESC LIMIT 10
        """, (s["id"],)).fetchall()
        if len(rows) < 3:
            continue
        grades = [r["grade"] for r in rows]
        cx = 0
        for g in grades:
            if g == "X":
                cx += 1
            else:
                break
        if cx >= 3:
            consecutive_missing.append({
                "student_id": s["id"],
                "student_name": s["name"],
                "group_name": s["group_name"] or "未分组",
                "consecutive_days": cx,
            })

    if consecutive_missing:
        alerts.append({
            "level": "danger",
            "title": f"⚠️ {len(consecutive_missing)} 名学生连续未交作业 ≥3 天",
            "detail": f"包括: {', '.join(m['student_name'] for m in consecutive_missing[:5])}"
                       + ("..." if len(consecutive_missing) > 5 else ""),
            "type": "consecutive_missing",
            "students": consecutive_missing,
        })

    # 2. 近3天 A 率较前3天下降超30%
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    if total > 0:
        recent_a, recent_total = 0, 0
        prev_a, prev_total = 0, 0
        for i in range(3):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            a_cnt = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade='A' AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            day_total = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            recent_a += a_cnt
            recent_total += day_total
        for i in range(3, 6):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            a_cnt = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade='A' AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            day_total = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            prev_a += a_cnt
            prev_total += day_total

        recent_rate = recent_a / recent_total * 100 if recent_total > 0 else 0
        prev_rate = prev_a / prev_total * 100 if prev_total > 0 else 0

        if prev_rate > 0 and (prev_rate - recent_rate) / prev_rate > 0.3:
            drop_pct = round((prev_rate - recent_rate) / prev_rate * 100, 1)
            alerts.append({
                "level": "warning",
                "title": f"📉 近3天A率({recent_rate:.1f}%)较前3天({prev_rate:.1f}%)下降 {drop_pct}%",
                "detail": f"A率从 {prev_rate:.1f}% 降至 {recent_rate:.1f}%，降幅超过30%",
                "type": "a_rate_drop",
                "data": {"recent_rate": round(recent_rate, 1), "prev_rate": round(prev_rate, 1),
                         "drop_pct": drop_pct},
            })

    return {
        "code": 0,
        "data": {
            "has_alerts": len(alerts) > 0,
            "alerts": alerts,
            "checked_at": today,
        }
    }


# ============================================================
# 智能分组 API
# ============================================================
@router.post("/smart-groups")
def api_ai_smart_groups(data: dict = Depends(get_body), cid: int = Depends(get_class_id),
                              db: sqlite3.Connection = Depends(get_db)):
    """AI 智能均衡分组（基于近30天平均等级）"""

    group_count = int(data.get("group_count", 6))
    if group_count < 2 or group_count > 20:
        return JSONResponse({"code": 1, "msg": "分组数量需在2-20之间"}, status_code=400)
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # 获取所有学生及其近30天作业记录
    students = db.execute(
        "SELECT id, name FROM students WHERE class_id=? ORDER BY id", (cid,)
    ).fetchall()

    # 计算每个学生的平均得分
    student_scores = []
    for s in students:
        rows = db.execute("""
            SELECT h.grade FROM homework h
            WHERE h.student_id=? AND h.date >= ?
        """, (s["id"], start_date)).fetchall()
        if not rows:
            student_scores.append({
                "id": s["id"], "name": s["name"], "avg_score": 0, "count": 0,
            })
            continue
        score_map = {"A": 3, "B": 2, "C": 1, "X": 0}
        # 请假(L)不计入均分：请假当天不交作业属正常，不应拉低均分
        scores = [score_map.get(r["grade"], 0) for r in rows if r["grade"] != "L"]
        avg = round(sum(scores) / len(scores), 2) if scores else 0
        student_scores.append({
            "id": s["id"], "name": s["name"], "avg_score": avg, "count": len(scores),
        })

    # 按平均分降序排列
    student_scores.sort(key=lambda x: x["avg_score"], reverse=True)

    # 贪心算法：蛇形分配（S形）确保均衡
    groups = [[] for _ in range(group_count)]
    group_scores = [0.0] * group_count
    group_counts = [0] * group_count

    # 使用蛇形（zigzag）分配
    direction = 1
    idx = 0
    for student in student_scores:
        groups[idx].append(student)
        group_scores[idx] += student["avg_score"]
        group_counts[idx] += 1
        idx += direction
        if idx >= group_count:
            idx = group_count - 1
            direction = -1
        elif idx < 0:
            idx = 0
            direction = 1

    # 构建结果
    result_groups = []
    for i, g in enumerate(groups):
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        avg = round(group_scores[i] / group_counts[i], 2) if group_counts[i] > 0 else 0
        result_groups.append({
            "name": f"第{i+1}组",
            "color": color,
            "sort_order": i,
            "student_count": len(g),
            "avg_score": avg,
            "students": [{"id": s["id"], "name": s["name"], "avg_score": s["avg_score"]}
                         for s in g],
        })

    # 统计均衡程度
    if group_count > 0 and all(gs > 0 for gs in group_counts):
        max_avg = max(group_scores[i] / group_counts[i] for i in range(group_count) if group_counts[i] > 0)
        min_avg = min(group_scores[i] / group_counts[i] for i in range(group_count) if group_counts[i] > 0)
        balance = round(max_avg - min_avg, 2)
    else:
        balance = 0

    return {
        "code": 0,
        "msg": f"智能分组完成：{group_count} 个组，均衡度差异 {balance}",
        "data": {
            "group_count": group_count,
            "balance_score": balance,
            "groups": result_groups,
            "student_count": len(student_scores),
        }
    }


@router.post("/smart-groups/apply")
def api_ai_smart_groups_apply(data: dict = Depends(get_body), cid: int = Depends(get_class_id),
                                    db: sqlite3.Connection = Depends(get_db)):
    """将智能分组结果应用到数据库"""

    groups = data.get("groups", [])
    if not groups:
        return JSONResponse({"code": 1, "msg": "缺少分组数据"}, status_code=400)

    # 清除旧分组
    db.execute("UPDATE students SET group_id = 0 WHERE class_id = ?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id = ?", (cid,))

    # 创建新分组并分配学生
    for g in groups:
        db.execute(
            "INSERT INTO groups_info (name, color, sort_order, class_id) VALUES (?,?,?,?)",
            (g["name"], g["color"], g["sort_order"], cid)
        )
        new_gid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for s in g.get("students", []):
            db.execute("UPDATE students SET group_id = ? WHERE id = ? AND class_id = ?",
                       (new_gid, s["id"], cid))

    db.commit()
    return {"code": 0, "msg": f"智能分组已应用（{len(groups)} 组）"}
