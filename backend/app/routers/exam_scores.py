# -*- coding: utf-8 -*-
"""
考试成绩管理 API:考试列表、成绩查询/保存/批量/删除、Excel 导入
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app.config import ensure_data_dir
from app.deps import get_class_id, get_db, get_body
from app.utils import _parse_exam_excel, calc_exam_grade

router = APIRouter(prefix="/api/exam-scores", tags=["exam-scores"])

UPLOAD_DIR = ensure_data_dir() / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/exams")
def api_get_exams(cid: int = Depends(get_class_id),
     db: sqlite3.Connection = Depends(get_db)):
    """获取当前班级的所有考试列表(去重 exam_name + date)"""

    rows = db.execute("""
        SELECT exam_name, date, total_score
        FROM exam_scores
        WHERE class_id=?
        GROUP BY exam_name, date
        ORDER BY date DESC
    """, (cid,)).fetchall()
    exams = [{
        "exam_name": r["exam_name"],
        "date": r["date"],
        "total_score": r["total_score"],
    } for r in rows]
    return {"code": 0, "data": exams}


@router.get("")
def api_get_exam_scores(exam_name: str = "", date: str = "",
                        cid: int = Depends(get_class_id),
                        db: sqlite3.Connection = Depends(get_db)):
    if not exam_name or not date:
        return JSONResponse({"code": 1, "msg": "请指定考试名称和日期"}, status_code=400)
    rows = db.execute("""
        SELECT e.id, e.student_id, e.date, e.exam_name, e.score, e.total_score, e.grade,
               s.name as student_name, s.student_code, s.group_id,
               g.name as group_name, g.color as group_color
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
        ORDER BY s.group_id, s.sort_order
    """, (exam_name, date, cid)).fetchall()
    # data 以 student_id 为字符串键(契约不可改)
    records = {}
    for r in rows:
        records[r["student_id"]] = {
            "id": r["id"], "student_id": r["student_id"],
            "student_name": r["student_name"], "student_code": r["student_code"] or "",
            "date": r["date"], "exam_name": r["exam_name"],
            "score": r["score"], "total_score": r["total_score"],
            "grade": r["grade"], "group_id": r["group_id"],
            "group_name": r["group_name"], "group_color": r["group_color"],
        }
    return {"code": 0, "data": records}


@router.post("")
def api_save_exam_score(
    data: dict = Depends(get_body),
     db: sqlite3.Connection = Depends(get_db)):
    student_id = int(data.get("student_id", 0))
    exam_name = (data.get("exam_name") or "").strip()
    date = data.get("date", "")
    score = data.get("score", 0)
    total_score = data.get("total_score", 100)
    if not exam_name:
        return JSONResponse({"code": 1, "msg": "考试名称不能为空"}, status_code=400)
    student = db.execute(
    "SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)
    try:
        score = float(score)
        total_score = float(total_score)
    except (TypeError, ValueError):
        score = 0.0
        total_score = 100.0
    grade = calc_exam_grade(score, total_score)
    db.execute("""
        INSERT INTO exam_scores (student_id, date, exam_name, score, total_score, grade, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT DO UPDATE SET
            score=excluded.score, total_score=excluded.total_score,
            grade=excluded.grade, updated_at=datetime('now','localtime')
    """, (student_id, date, exam_name, score, total_score, grade))
    db.commit()
    return {"code": 0, "msg": "成绩已保存"}


@router.post("/batch")
def api_batch_exam_scores(
    data: dict = Depends(get_body),
    cid: int = Depends(get_class_id),
     db: sqlite3.Connection = Depends(get_db)):
    exam_name = (data.get("exam_name") or "").strip()
    date = data.get("date", "")
    total_score = data.get("total_score", 100)
    group_id = int(data.get("group_id", 0))
    student_ids = data.get("student_ids", [])
    score = data.get("score", 80)
    if not exam_name:
        return JSONResponse({"code": 1, "msg": "考试名称不能为空"}, status_code=400)
    try:
        score = float(score)
        total_score = float(total_score)
    except (TypeError, ValueError):
        score = 80.0
        total_score = 100.0
    grade = calc_exam_grade(score, total_score)
    # 作用域三级:student_ids > group_id > 全班
    if student_ids:
        placeholders = ",".join("?" * len(student_ids))
        db.execute(
    f"DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN ({placeholders})", [
        exam_name, date] + student_ids)
        db.execute(
    f"""INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, class_id, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE id IN ({placeholders})""", [
        date, exam_name, score, total_score, grade] + student_ids)
    elif group_id > 0:
        db.execute(
    "DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN "
    "(SELECT id FROM students WHERE group_id=? AND class_id=?)",
    (exam_name,
    date,
    group_id,
     cid))
        db.execute(
    """INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, class_id, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE group_id=? AND class_id=?""",
    (date,
    exam_name,
    score,
    total_score,
    grade,
    group_id,
     cid))
    else:
        db.execute(
    "DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN "
    "(SELECT id FROM students WHERE class_id=?)", (exam_name, date, cid))
        db.execute(
    """INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, class_id, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE class_id=?""", (date, exam_name, score, total_score, grade, cid))
    db.commit()
    return {"code": 0, "msg": f"已批量录入「{exam_name}」成绩"}


@router.delete("/{eid}")
def api_delete_exam_score(eid: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM exam_scores WHERE id=?", (eid,))
    db.commit()
    return {"code": 0, "msg": "已删除"}


@router.post("/import")
async def api_import_exam_scores(
    request: Request,
    file: UploadFile = File(...),
    date: str | None = None,
    cid: int = Depends(get_class_id),
    db: sqlite3.Connection = Depends(get_db),
):
    """上传考试 Excel 并导入到 exam_scores 表"""

    if not file or not file.filename:
        return JSONResponse({"code": 1, "msg": "文件名为空"}, status_code=400)
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return JSONResponse(
            {"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}, status_code=400)
    safe_name = Path(file.filename).name
    file_path = UPLOAD_DIR / \
        f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    file_path.write_bytes(await file.read())
    try:
        result = _parse_exam_excel(str(file_path))
    except Exception as e:
        try:
            file_path.unlink()
        except Exception:
            pass
        return JSONResponse(
            {"code": 1, "msg": f"解析失败: {str(e)}"}, status_code=400)
    if "error" in result:
        try:
            file_path.unlink()
        except Exception:
            pass
        return JSONResponse(
            {"code": 1, "msg": result["error"]}, status_code=400)
    try:
        file_path.unlink()
    except Exception:
        pass

    # 考试日期:query date > JSON body date > 今天
    exam_date = date
    if not exam_date:
        try:
            exam_date = (body or {}).get(
                "date") or datetime.now().strftime("%Y-%m-%d")
        except Exception:
            exam_date = datetime.now().strftime("%Y-%m-%d")

    all_students = db.execute(
        "SELECT id, name, student_code FROM students WHERE class_id=?", (cid,)
    ).fetchall()
    # 建立查找映射:name → id, code → id
    name_map = {s["name"].strip(): s["id"] for s in all_students}
    code_map = {}
    for s in all_students:
        if s["student_code"]:
            code_map[s["student_code"].strip()] = s["id"]

    imported, skipped = 0, 0
    for cls_data in result.get("classes", []):
        exam_name = cls_data.get("name", "") or safe_name.rsplit(".", 1)[0]
        for stu in cls_data.get("students", []):
            name = stu.get("name", "").strip()
            sid = name_map.get(name)
            if not sid and stu.get("code"):
                sid = code_map.get(stu.get("code", "").strip())
            if not sid:
                skipped += 1
                continue
            score = float(stu.get("score", 0)) if stu.get(
                "score") is not None else 0
            total = float(cls_data.get("total_score", 100))
            grade = stu.get("grade", "")
            if not grade and total > 0:
                grade = calc_exam_grade(score, total)
            db.execute("""
                INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT DO UPDATE SET
                    score=excluded.score, total_score=excluded.total_score,
                    grade=excluded.grade, updated_at=datetime('now','localtime')
            """, (sid, cid, exam_date, exam_name, score, total, grade))
            imported += 1
    db.commit()
    return {
        "code": 0, "msg": f"导入完成：{imported} 条，跳过(未匹配) {skipped} 条",
        "data": {"imported": imported, "skipped": skipped}
    }
