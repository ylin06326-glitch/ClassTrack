# -*- coding: utf-8 -*-
"""
AI 服务层(纯函数,无 FastAPI 依赖)
==================================
从 Flask main.py 1:1 迁移:
- AI 配置读取 / LLM 调用(_call_llm 保留同步 requests,由路由层包 run_in_threadpool)
- 意图提取与数据上下文构建(_extract_intent)
- 数据文本提示词(_build_data_prompt)
- 服务端图表自动构建(_build_chart_from_context)
- 智能追问建议(_generate_follow_ups)
- 兜底文字回复(_generate_fallback_reply)
"""

import json
from datetime import datetime, timedelta

import requests

from app.utils import ai_key_decode


def _get_ai_config(db) -> dict:
    """从 app_config 读取 AI 配置"""
    rows = db.execute(
        "SELECT key, value FROM app_config WHERE key LIKE 'ai_%'"
    ).fetchall()
    config = {r["key"]: r["value"] for r in rows}
    return {
        "provider": config.get("ai_provider", "deepseek"),
        "api_key": ai_key_decode(config.get("ai_api_key", "")),
        "base_url": config.get("ai_base_url", ""),
        "model": config.get("ai_model", ""),
    }


def _get_llm_url(config: dict) -> str:
    """根据 provider 返回 LLM API 端点"""
    provider = config["provider"]
    base = config.get("base_url", "")
    if provider == "deepseek":
        return base or "https://api.deepseek.com/v1"
    elif provider == "openai":
        return base or "https://api.openai.com/v1"
    elif provider == "qwen":
        return base or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    else:  # custom
        return base.rstrip("/") if base else ""


def _call_llm(config: dict, messages: list, timeout: int = 30) -> tuple:
    """调用大模型 API，返回 (success: bool, content: str)"""
    base_url = _get_llm_url(config)
    api_key = config.get("api_key", "")
    model = config.get("model", "")

    if not base_url:
        return False, "请先在设置中配置 AI 服务商和 Base URL"
    if not api_key:
        return False, "请先在设置中配置 API Key"
    if not model:
        return False, "请先在设置中配置模型名称"

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return True, content
        else:
            try:
                detail = resp.json()
                err_msg = detail.get("error", {}).get("message", resp.text)
            except Exception:
                err_msg = resp.text[:200]
            return False, f"API 返回错误 ({resp.status_code}): {err_msg}"
    except requests.exceptions.Timeout:
        return False, "请求超时（30秒），请检查网络连接或 API 服务状态"
    except requests.exceptions.ConnectionError:
        return False, "无法连接到 API 服务器，请检查 Base URL 和网络连接"
    except Exception as e:
        return False, f"服务暂时不可用，请检查网络或 API Key: {str(e)[:100]}"


def _extract_intent(question: str, db, cid: int, hw_type_id: int = 0) -> dict:
    """
    从用户问题中提取意图和数据上下文
    返回: {intent, context_data, data_prompt}
    """
    q = question.strip()
    context = {
        "question": q,
        "intents": [],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "cid": cid,
        "hw_type_id": hw_type_id,
    }

    # 关键词检测
    has_date = any(kw in q for kw in ["今天", "今日", "当天", "日期", "昨天", "前天"])
    has_ranking = any(kw in q for kw in ["排名", "排行", "最好", "最差", "最强", "最弱", "表现最好", "表现最差"])
    has_trend = any(kw in q for kw in ["趋势", "变化", "最近", "近几", "走势", "进步", "退步"])
    has_group = any(kw in q for kw in ["组", "小组", "分组"])
    has_compare = any(kw in q for kw in ["对比", "比较", "相比", "哪个"])
    has_student = any(kw in q for kw in ["学生", "同学", "谁", "哪些人", "名单"])

    if has_date:
        context["intents"].append("date_summary")
    if has_ranking:
        context["intents"].append("ranking")
    if has_trend:
        context["intents"].append("trend")
    if has_group:
        context["intents"].append("group")
    if has_compare:
        context["intents"].append("compare")
    if has_student:
        context["intents"].append("student")

    if not context["intents"]:
        context["intents"].append("general")

    # ---- 构建 SQL 过滤条件 ----
    hw_type_join = ""
    hw_type_where = ""
    hw_type_params_extra = ()
    if hw_type_id > 0:
        hw_type_join = " JOIN homework_types ht ON h.homework_type_id = ht.id"
        hw_type_where = " AND h.homework_type_id = ?"
        hw_type_params_extra = (hw_type_id,)

    # ---- 采集上下文数据 ----
    today_str = context["date"]
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]

    # 今日数据（带作业种类过滤）
    # ★ 使用子查询先按 student_id 去重取最优等级，避免多作业种类时 COUNT(*) 重复计数
    #   导致登记人数超学生总数、未登记为负数的问题
    grades = db.execute(f"""
        SELECT best_grade, COUNT(*) as cnt FROM (
            SELECT h.student_id,
                   MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                    WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END) as grade_rank,
                   CASE MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                         WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END)
                       WHEN 1 THEN 'A' WHEN 2 THEN 'B' WHEN 3 THEN 'C' WHEN 4 THEN 'L' ELSE 'X'
                   END as best_grade
            FROM homework h JOIN students s ON h.student_id = s.id
            {hw_type_join}
            WHERE h.date = ? AND s.class_id = ? {hw_type_where}
            GROUP BY h.student_id
        ) GROUP BY best_grade
    """, (today_str, cid) + hw_type_params_extra).fetchall()
    grade_counts = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for g in grades:
        grade_counts[g["best_grade"]] = g["cnt"]
    recorded = sum(grade_counts.values())
    grade_counts["未登记"] = total - recorded

    context["grade_counts"] = grade_counts
    context["total_students"] = total

    # 分组对比数据
    groups = db.execute(
        "SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order", (cid,)
    ).fetchall()
    group_data = []
    for g in groups:
        gs = db.execute(
            "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (g["id"], cid)
        ).fetchone()["c"]
        ga = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            {hw_type_join}
            WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=? {hw_type_where}
        """, (today_str, g["id"], cid) + hw_type_params_extra).fetchone()["c"]
        submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            {hw_type_join}
            WHERE h.date=? AND h.grade IN ('A','B','C','L') AND s.group_id=? AND s.class_id=? {hw_type_where}
        """, (today_str, g["id"], cid) + hw_type_params_extra).fetchone()["c"]
        group_data.append({
            "name": g["name"], "total": gs, "a_count": ga,
            "missing": gs - submitted,
            "a_rate": round(ga / gs * 100, 1) if gs > 0 else 0,
        })

    # 排序用于 context
    ranked = sorted(group_data, key=lambda x: x["a_rate"], reverse=True)
    context["group_data"] = group_data
    context["best_group"] = ranked[0] if ranked else None
    context["worst_group"] = ranked[-1] if ranked else None

    # 趋势数据（近7天）
    trend = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        sub = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            {hw_type_join}
            WHERE h.date=? AND h.grade!='X' AND s.class_id=? {hw_type_where}
        """, (d, cid) + hw_type_params_extra).fetchone()["c"]
        rate = round(sub / total * 100, 1) if total > 0 else 0
        trend.append({"date": d, "rate": rate})
    context["trend"] = trend

    # 学生数据（带近30天均分）
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    students = db.execute(
        "SELECT s.id, s.name, s.student_code, s.group_id, g.name as group_name "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id=? ORDER BY s.sort_order, s.id",
        (cid,)
    ).fetchall()

    student_list = []
    for s in students:
        rows = db.execute(f"""
            SELECT h.grade FROM homework h
            {hw_type_join}
            WHERE h.student_id=? AND h.date >= ? {hw_type_where}
        """, (s["id"], start_date) + hw_type_params_extra).fetchall()
        score_map = {"A": 3, "B": 2, "C": 1, "X": 0}
        # 请假(L)不计入均分：请假当天不交作业属正常，不应拉低均分
        scores = [score_map.get(r["grade"], 0) for r in rows if r["grade"] != "L"]
        avg = round(sum(scores) / len(scores), 2) if scores else 0
        student_list.append({
            "id": s["id"], "name": s["name"],
            "student_code": s["student_code"] or "",
            "group_name": s["group_name"] or "未分组",
            "avg_score": avg,
            "record_count": len(scores),
        })

    # 按均分排序
    student_list.sort(key=lambda x: x["avg_score"], reverse=True)
    context["students"] = student_list
    context["top_students"] = student_list[:5]
    context["bottom_students"] = student_list[-5:] if len(student_list) >= 5 else []

    # 班级名
    cls = db.execute("SELECT name FROM classes WHERE id=?", (cid,)).fetchone()
    context["class_name"] = cls["name"] if cls else ""

    # 作业种类名
    if hw_type_id > 0:
        hw_type = db.execute("SELECT name FROM homework_types WHERE id=?", (hw_type_id,)).fetchone()
        context["hw_type_name"] = hw_type["name"] if hw_type else ""

    return context


def _build_data_prompt(context: dict) -> str:
    """将上下文数据构建为给 LLM 的文本（结构化数据 + 可读摘要）"""
    lines = []

    # ---- 基础信息 ----
    lines.append(f"## 基础信息")
    lines.append(f"- 班级: {context['class_name']}")
    lines.append(f"- 日期: {context['date']}")
    lines.append(f"- 学生总数: {context['total_students']} 人")
    if context.get("hw_type_name"):
        lines.append(f"- 作业种类: {context['hw_type_name']}")
    if context.get("hw_type_id", 0) > 0:
        lines.append(f"- 注意: 以下所有数据仅统计「{context.get('hw_type_name', '指定种类')}」作业")

    # ---- 今日统计 ----
    gc = context.get("grade_counts", {})
    total_recorded = gc.get("A", 0) + gc.get("B", 0) + gc.get("C", 0) + gc.get("L", 0) + gc.get("X", 0)
    submit_rate = round((total_recorded - gc.get("X", 0)) / context["total_students"] * 100, 1) if context["total_students"] > 0 else 0
    a_rate = round(gc.get("A", 0) / context["total_students"] * 100, 1) if context["total_students"] > 0 else 0

    lines.append(f"\n## 今日作业统计")
    lines.append(f"- A(优秀): {gc.get('A', 0)}人")
    lines.append(f"- B(良好): {gc.get('B', 0)}人")
    lines.append(f"- C(待改进): {gc.get('C', 0)}人")
    lines.append(f"- 未交: {gc.get('X', 0)}人")
    lines.append(f"- 请假: {gc.get('L', 0)}人")
    lines.append(f"- 未登记: {gc.get('未登记', 0)}人")
    lines.append(f"- 提交率: {submit_rate}%")
    lines.append(f"- A率: {a_rate}%")

    # 提供 JSON 格式的分布数据（方便 LLM 直接在 HTML 中使用）
    grade_json = json.dumps({
        "grade_distribution": {
            "A": gc.get("A", 0), "B": gc.get("B", 0),
            "C": gc.get("C", 0), "L": gc.get("L", 0),
            "X": gc.get("X", 0),
            "unrecorded": gc.get("未登记", 0),
        },
        "submit_rate": submit_rate,
        "a_rate": a_rate,
    }, ensure_ascii=False)
    lines.append("\n```json\n" + grade_json + "\n```")

    # ---- 小组对比 ----
    group_data = context.get("group_data", [])
    if group_data:
        lines.append(f"\n## 各小组今日对比")
        for gd in group_data:
            missing = gd.get("missing", 0)
            total = gd.get("total", 0)
            g_submit = round((total - missing) / total * 100, 1) if total > 0 else 0
            lines.append(f"- {gd['name']}: {total}人, A率={gd.get('a_rate', 0)}%, 提交率={g_submit}%, 未交={missing}人")

        # 最好/最差组
        ranked = sorted(group_data, key=lambda x: x.get("a_rate", 0), reverse=True)
        if ranked:
            lines.append(f"\n表现最好: {ranked[0]['name']} (A率 {ranked[0].get('a_rate', 0)}%)")
            lines.append(f"表现最差: {ranked[-1]['name']} (A率 {ranked[-1].get('a_rate', 0)}%)")

        # JSON 格式
        groups_json = json.dumps({
            "groups": [{
                "name": g["name"], "total": g["total"],
                "a_rate": g.get("a_rate", 0), "a_count": g.get("a_count", 0),
                "missing": g.get("missing", 0),
            } for g in group_data]
        }, ensure_ascii=False)
        lines.append("\n```json\n" + groups_json + "\n```")

    # ---- 趋势数据 ----
    trend = context.get("trend", [])
    if trend:
        lines.append(f"\n## 近7天提交率趋势")
        for t in trend:
            direction = "↑" if len(trend) > 1 and t == trend[-1] and t["rate"] > trend[0]["rate"] else ("↓" if len(trend) > 1 and t == trend[-1] and t["rate"] < trend[0]["rate"] else "→")
            lines.append(f"- {t['date']}: {t['rate']}% {direction}")

        first_rate = trend[0]["rate"] if trend else 0
        last_rate = trend[-1]["rate"] if trend else 0
        change = round(last_rate - first_rate, 1)
        lines.append(f"\n趋势变化: {first_rate}% → {last_rate}% ({'+' if change >= 0 else ''}{change}%)")

        # JSON
        trend_json = json.dumps({
            "trend": [{"date": t["date"], "rate": t["rate"]} for t in trend]
        }, ensure_ascii=False)
        lines.append("\n```json\n" + trend_json + "\n```")

    # ---- 考试数据（如果有上传） ----
    exam_data = context.get("exam_data")
    if exam_data:
        lines.append(f"\n## 📝 已上传的考试数据")
        lines.append(f"- 学生总数: {exam_data.get('total_students', 0)} 人")
        lines.append(f"- 班级/组别数: {len(exam_data.get('classes', []))} 个")
        lines.append(f"- 识别列: {', '.join(exam_data.get('detected_columns', []))}")

        for cls in exam_data.get("classes", []):
            st = cls.get("stats", {})
            lines.append(f"\n### {cls['class_name']}")
            lines.append(f"- 人数: {cls['student_count']}, 均分: {cls['avg_score']}, 最高: {cls['max_score']}, 最低: {cls['min_score']}")
            lines.append(f"- A: {st.get('A', 0)}人, B: {st.get('B', 0)}人, C: {st.get('C', 0)}人, 未达标: {st.get('X', 0)}人")
            # 前5名学生
            top5 = [s for s in cls.get("students", []) if s.get("score") is not None]
            top5.sort(key=lambda x: x.get("score", 0), reverse=True)
            if top5:
                names_scores = ", ".join(f"{s['name']}({s.get('score_display', '')}分/{s.get('grade', '')})" for s in top5[:5])
                lines.append(f"- TOP5: {names_scores}")

            # 满分/高分学生
            perfect = [s for s in cls.get("students", []) if s.get("score") is not None and s["score"] >= 90]
            if perfect and len(perfect) <= 10:
                lines.append(f"- ≥90分: {', '.join(s['name'] for s in perfect)}")

            # 不及格学生
            failing = [s for s in cls.get("students", []) if s.get("grade") == "X"]
            if failing and len(failing) <= 10:
                lines.append(f"- 未达标(<60): {', '.join(s['name'] for s in failing)}")

        # JSON 格式
        exam_json = json.dumps({
            "classes": [{
                "class_name": cls["class_name"],
                "student_count": cls["student_count"],
                "avg_score": cls["avg_score"],
                "max_score": cls["max_score"],
                "min_score": cls["min_score"],
                "stats": cls.get("stats", {}),
                "top_students": sorted(
                    [s for s in cls.get("students", []) if s.get("score") is not None],
                    key=lambda x: x.get("score", 0), reverse=True
                )[:5],
            } for cls in exam_data.get("classes", [])]
        }, ensure_ascii=False)
        lines.append(f"\n```json\n{exam_json}\n```")

    # ---- 学生名单（采样） ----
    students = context.get("students", [])
    if students:
        lines.append(f"\n## 学生数据（部分采样）")
        lines.append(f"共 {len(students)} 名学生")
        for s in students[:20]:  # 最多20人
            lines.append(f"- {s['name']}: 组={s.get('group_name', '未分组')}, 近30天均分={s.get('avg_score', 0)}")
        if len(students) > 20:
            lines.append(f"... 还有 {len(students) - 20} 人")

    return "\n".join(lines)


def _build_chart_from_context(context: dict, override_type: str = None) -> dict:
    """
    根据上下文数据自动构建完整的 ECharts option。
    不依赖 LLM，直接从数据库提取的数据构建，保证图表永远完整可用。

    返回: {"type": "pie|bar|line", "title": "...", "option": {完整ECharts配置}}
    如果数据不足以构建图表，返回 None
    """
    MACARON = ['#7EB5D6', '#E8A0BF', '#A8D5BA', '#F4C97E', '#C4B5D6', '#F0B8A0',
               '#8EC8C0', '#D4A8C8', '#9DC8E0', '#F2C8DA']
    intents = context.get("intents", [])
    chart_type = override_type

    # ---- 自动推断图表类型 ----
    if not chart_type:
        if "trend" in intents:
            chart_type = "line"
        elif "compare" in intents or "ranking" in intents or "group" in intents:
            chart_type = "bar"
        elif "date_summary" in intents or "general" in intents:
            chart_type = "pie"
        else:
            chart_type = "bar"  # 默认柱状图

    # ---- 构建图表 ----
    if chart_type == "pie":
        # 饼图：今日作业等级分布
        gc = context.get("grade_counts", {})
        if not gc:
            return None
        pie_data = [
            {"name": "A 优秀", "value": gc.get("A", 0)},
            {"name": "B 良好", "value": gc.get("B", 0)},
            {"name": "C 待改进", "value": gc.get("C", 0)},
            {"name": "未交", "value": gc.get("X", 0)},
        ]
        unreg = gc.get("未登记", 0)
        if unreg > 0:
            pie_data.append({"name": "未登记", "value": unreg})

        if sum(d["value"] for d in pie_data) == 0:
            return None

        return {
            "type": "pie",
            "title": f"{context.get('date', '')} 作业等级分布",
            "option": {
                "tooltip": {"trigger": "item", "formatter": "{b}: {c}人 ({d}%)"},
                "legend": {"orient": "vertical", "right": "5%", "top": "center",
                          "textStyle": {"fontSize": 12}},
                "color": MACARON,
                "series": [{
                    "name": "作业等级",
                    "type": "pie",
                    "radius": ["45%", "75%"],
                    "center": ["45%", "55%"],
                    "avoidLabelOverlap": False,
                    "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                    "label": {"show": True, "formatter": "{b}\n{d}%"},
                    "emphasis": {"label": {"fontSize": 16, "fontWeight": "bold"}},
                    "data": pie_data,
                }],
            },
        }

    elif chart_type == "line":
        # 折线图：近7天提交率趋势
        trend = context.get("trend", [])
        if not trend or len(trend) < 2:
            return None
        dates = [t["date"] for t in trend]
        rates = [t["rate"] for t in trend]

        return {
            "type": "line",
            "title": "近7天作业提交率趋势",
            "option": {
                "tooltip": {"trigger": "axis", "formatter": "{b}<br/>提交率: {c}%"},
                "grid": {"left": "3%", "right": "5%", "bottom": "3%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": dates,
                    "axisLabel": {"fontSize": 11, "rotate": 30},
                    "boundaryGap": False,
                },
                "yAxis": {
                    "type": "value",
                    "name": "提交率 (%)",
                    "min": 0,
                    "max": 100,
                    "axisLabel": {"formatter": "{value}%"},
                },
                "color": [MACARON[0]],
                "series": [{
                    "name": "提交率",
                    "type": "line",
                    "data": rates,
                    "smooth": True,
                    "symbol": "circle",
                    "symbolSize": 8,
                    "lineStyle": {"width": 3},
                    "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                            "colorStops": [{"offset": 0, "color": "rgba(126,181,214,0.35)"},
                                                          {"offset": 1, "color": "rgba(126,181,214,0.02)"}]}},
                    "markLine": {
                        "silent": True,
                        "data": [{"type": "average", "name": "平均", "label": {"formatter": "平均 {c}%"}}],
                        "lineStyle": {"color": "#E8A0BF", "type": "dashed"},
                    },
                }],
            },
        }

    elif chart_type == "bar":
        # 柱状图：小组对比（A率 + 提交率）
        group_data = context.get("group_data", [])
        if not group_data:
            return None

        names = [g["name"] for g in group_data]
        a_rates = [g.get("a_rate", 0) for g in group_data]
        # 计算提交率
        submit_rates = []
        for g in group_data:
            missing = g.get("missing", 0)
            total = g.get("total", 1)
            submit_rates.append(round((total - missing) / total * 100, 1) if total > 0 else 0)

        return {
            "type": "bar",
            "title": "各小组今日作业对比",
            "option": {
                "tooltip": {
                    "trigger": "axis",
                    "axisPointer": {"type": "shadow"},
                },
                "legend": {
                    "data": ["A率", "提交率"],
                    "top": "bottom",
                    "textStyle": {"fontSize": 11},
                },
                "grid": {"left": "3%", "right": "5%", "bottom": "12%", "top": "8%", "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "data": names,
                    "axisLabel": {"fontSize": 11},
                },
                "yAxis": {
                    "type": "value",
                    "name": "百分比 (%)",
                    "min": 0,
                    "max": 100,
                    "axisLabel": {"formatter": "{value}%"},
                },
                "color": [MACARON[0], MACARON[3]],
                "series": [
                    {
                        "name": "A率",
                        "type": "bar",
                        "data": a_rates,
                        "barWidth": "45%",
                        "itemStyle": {"borderRadius": [6, 6, 0, 0]},
                        "label": {"show": True, "position": "top", "fontSize": 10,
                                 "formatter": "{c}%"},
                    },
                    {
                        "name": "提交率",
                        "type": "bar",
                        "data": submit_rates,
                        "barWidth": "45%",
                        "itemStyle": {"borderRadius": [6, 6, 0, 0]},
                        "label": {"show": True, "position": "top", "fontSize": 10,
                                 "formatter": "{c}%"},
                    },
                ],
            },
        }

    return None


def _generate_follow_ups(context: dict, question: str) -> list:
    """基于当前数据和问题，生成智能追问建议"""
    follow_ups = []
    gc = context.get("grade_counts", {})
    gd = context.get("group_data", [])
    trend = context.get("trend", [])
    students = context.get("students", [])
    total = context.get("total_students", 0)

    # 追问1: 如果有未交学生，追问具体名单
    if gc.get("X", 0) > 0:
        follow_ups.append({"text": f"今天未交作业的 {gc['X']} 个学生具体是谁？", "icon": "🔍"})

    # 追问2: 如果有小组差异大，追问原因分析
    if gd and len(gd) >= 2:
        ranked = sorted(gd, key=lambda x: x.get("a_rate", 0), reverse=True)
        gap = ranked[0].get("a_rate", 0) - ranked[-1].get("a_rate", 0)
        if gap > 15:
            follow_ups.append({
                "text": f"为什么{ranked[0]['name']}和{ranked[-1]['name']}差距这么大？怎么帮落后的组提升？",
                "icon": "💡",
            })

    # 追问3: 如果有趋势下降，追问原因
    if trend and len(trend) >= 3:
        recent = [t["rate"] for t in trend[-3:]]
        if len(recent) >= 3 and recent[-1] < recent[0] - 5:
            follow_ups.append({"text": "最近提交率为什么下降了？帮我分析一下可能的原因", "icon": "📉"})

    # 追问4: 学生个体分析
    if students:
        top = students[:3] if students else []
        bottom = students[-3:] if len(students) >= 3 else []
        if bottom:
            follow_ups.append({
                "text": f"帮我分析一下{', '.join(s['name'] for s in bottom[:1])}最近的学习状态",
                "icon": "👤",
            })
        if top and len(follow_ups) < 4:
            follow_ups.append({
                "text": f"进步最大的学生有哪些？他们的学习模式是怎样的？",
                "icon": "🌟",
            })

    # 追问5: 对比建议
    if gd and len(follow_ups) < 4:
        follow_ups.append({"text": "对比本周和上周的数据，有什么变化趋势？", "icon": "📊"})

    # 追问6: 通用建议
    if len(follow_ups) < 3:
        follow_ups.append({"text": "根据当前数据，你有什么教学建议？", "icon": "🎯"})

    # 去重
    seen = set()
    unique = []
    for f in follow_ups:
        if f["text"] not in seen:
            seen.add(f["text"])
            unique.append(f)

    return unique[:4]  # 最多4个追问


def _generate_fallback_reply(context: dict, question: str) -> str:
    """当 LLM 未返回文字时，用数据自动生成摘要"""
    gc = context.get("grade_counts", {})
    total = context["total_students"]
    a_cnt = gc.get("A", 0)
    submit_cnt = a_cnt + gc.get("B", 0) + gc.get("C", 0)

    parts = []
    # 今日概况
    parts.append(f"今日共 {total} 名学生，已提交 {submit_cnt} 人（{round(submit_cnt/total*100,1) if total else 0}%），其中 A 等 {a_cnt} 人。")

    # 最好/最差组
    gd = context.get("group_data", [])
    if gd:
        ranked = sorted(gd, key=lambda x: x.get("a_rate", 0), reverse=True)
        if ranked:
            parts.append(f"表现最好的是 {ranked[0]['name']}（A率 {ranked[0].get('a_rate', 0)}%），需要关注的是 {ranked[-1]['name']}（A率 {ranked[-1].get('a_rate', 0)}%）。")

    # 趋势
    trend = context.get("trend", [])
    if trend and len(trend) >= 2:
        change = trend[-1]["rate"] - trend[0]["rate"]
        if change > 3:
            parts.append(f"近7天提交率呈上升趋势（+{round(change,1)}%），继续保持！")
        elif change < -3:
            parts.append(f"近7天提交率有所下降（{round(change,1)}%），建议关注学生状态。")

    return " ".join(parts) if parts else f"好的，我来回答关于「{question}」的问题。请查看右侧可视化面板了解详情。"
