# -*- coding: utf-8 -*-
"""
学生管理 + 名单导入 API
=======================
GET/DELETE students、批量删除、清空未分组、Excel/文本导入
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app.config import ensure_data_dir
from app.deps import get_class_id, get_db, get_body
from app.utils import parse_excel_students, parse_text_names

router = APIRouter(prefix="/api", tags=["students"])

UPLOAD_DIR = ensure_data_dir() / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/students")
def api_get_students(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT s.*, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id AND g.class_id = ? "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order, s.id",
        (cid, cid)
    ).fetchall()
    students = [{"id": r["id"],
                 "name": r["name"],
                 "student_code": r["student_code"] or "",
                 "group_id": r["group_id"] or 0,
                 "group_name": r["group_name"] or "",
                 "group_color": r["group_color"] or "",
                 "sort_order": r["sort_order"],
                 "class_id": r["class_id"]} for r in rows]
    return {"code": 0, "data": students}


@router.delete("/students/{sid}")
def api_delete_student(sid: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM students WHERE id = ?", (sid,))
    db.commit()
    return {"code": 0, "msg": "已删除"}


@router.delete("/students/clear")
def api_clear_students(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    student_ids = [r[0] for r in db.execute(
        "SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
    for sid in student_ids:
        db.execute("DELETE FROM homework WHERE student_id=?", (sid,))
    db.execute("DELETE FROM students WHERE class_id=?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id=?", (cid,))
    db.commit()
    return {"code": 0, "msg": "已清空当前班级数据"}


@router.post("/students/batch-delete")
def api_batch_delete_students(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    """批量删除学生及其作业记录"""

    student_ids = data.get("student_ids", [])
    if not student_ids:
        return JSONResponse({"code": 1, "msg": "未选择学生"}, status_code=400)
    if len(student_ids) > 200:
        return JSONResponse({"code": 1, "msg": "单次最多删除200人"}, status_code=400)
    placeholders = ",".join("?" * len(student_ids))
    db.execute(
        f"DELETE FROM homework WHERE student_id IN ({placeholders})",
        student_ids)
    db.execute(
        f"DELETE FROM students WHERE id IN ({placeholders})",
        student_ids)
    db.commit()
    return {"code": 0, "msg": f"已删除 {len(student_ids)} 名学生"}


@router.post("/students/clear-unassigned")
def api_clear_unassigned(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """清除当前班级所有未分组学生"""

    unassigned = db.execute(
        "SELECT id FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=?",
        (cid,)
    ).fetchall()
    if not unassigned:
        return {"code": 0, "msg": "没有未分组的学生"}
    ids = [r[0] for r in unassigned]
    placeholders = ",".join("?" * len(ids))
    db.execute(
        f"DELETE FROM homework WHERE student_id IN ({placeholders})",
        ids)
    db.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
    db.commit()
    return {
        "code": 0, "msg": f"已清除 {
            len(ids)} 名未分组学生", "data": {
            "count": len(ids)}}


@router.post("/import")
async def api_import_students(
    request: Request,
    file: UploadFile = File(...),
    cid: int = Depends(get_class_id),
    db: sqlite3.Connection = Depends(get_db),
):
    if not file or not file.filename:
        return JSONResponse({"code": 1, "msg": "文件名为空"}, status_code=400)
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return JSONResponse(
            {"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}, status_code=400)
    # 清洗文件名,防路径穿越
    safe_name = Path(file.filename).name
    file_path = UPLOAD_DIR / \
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    content = await file.read()
    file_path.write_bytes(content)
    try:
        records = parse_excel_students(str(file_path))
    except Exception as e:
        return JSONResponse(
            {"code": 1, "msg": f"解析Excel失败: {str(e)}"}, status_code=400)
    if not records:
        return JSONResponse(
            {"code": 1, "msg": "未在表格中找到有效学生姓名"}, status_code=400)
    if len(records) > 200:
        return JSONResponse(
            {"code": 1, "msg": f"学生数量({len(records)})超过上限(200人)"}, status_code=400)
    imported, skipped = 0, 0
    for r in records:
        try:
            db.execute(
                "INSERT INTO students (name, student_code, class_id) VALUES (?, ?, ?)",
                (r["name"],
                 r["code"],
                    cid))
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    db.commit()
    try:
        file_path.unlink()
    except Exception:
        pass
    return {
        "code": 0,
        "msg": f"导入完成：新增 {imported} 人，跳过重复 {skipped} 人",
        "data": {"imported": imported, "skipped": skipped}
    }


@router.post("/import/text")
def api_import_text(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """纯文字导入学生名单(v1.2: 支持学号识别)"""

    text = data.get("text", "")
    # v1.2: 前端已解析学号,直接使用 parsed_records
    parsed_records = data.get("parsed_records", None)
    if parsed_records:
        # 使用前端解析结果 [{name, code}]
        records = [(r.get("name", "").strip(), r.get("code", "").strip())
                   for r in parsed_records]
        records = [(n, c) for n, c in records if n]
    else:
        # 兼容旧版:后端自行解析姓名
        names = parse_text_names(text)
        records = [(n, "") for n in names if n]
    if not records:
        return JSONResponse({"code": 1, "msg": "未能解析出有效姓名"}, status_code=400)
    if len(records) > 200:
        return JSONResponse(
            {"code": 1, "msg": f"学生数量({len(records)})超过上限(200人)"}, status_code=400)
    imported, skipped = 0, 0
    for name, code in records:
        try:
            db.execute(
                "INSERT INTO students (name, student_code, class_id) VALUES (?, ?, ?)",
                (name,
                 code,
                 cid))
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    db.commit()
    return {"code": 0, "msg": f"导入完成：新增 {imported} 人，跳过重复 {skipped} 人", "data": {
        "imported": imported, "skipped": skipped, "parsed": [n for n, _ in records]}}
