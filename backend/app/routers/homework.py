# -*- coding: utf-8 -*-
"""
作业登记 API:当日作业、单条/批量登记、区间查询、未交名单、作业种类管理
"""

import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.deps import get_class_id, get_db, get_body
from app.utils import grade_label

router = APIRouter(prefix="/api", tags=["homework"])

VALID_GRADES = ("A", "B", "C", "L", "X")


@router.get("/homework")
def api_get_homework(date: str | None = None, homework_type_id: int = 0,
                     cid: int = Depends(get_class_id),
                     db: sqlite3.Connection = Depends(get_db)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    rows = db.execute(
        "SELECT h.id, h.student_id, h.date, h.grade, s.name as student_name, "
        "s.group_id, g.name as group_name, g.color as group_color "
        "FROM homework h "
        "JOIN students s ON h.student_id = s.id "
        "LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE h.date = ? AND s.class_id = ?" + hw_filter + " "
        "ORDER BY s.group_id, s.sort_order",
        params
    ).fetchall()
    # 注意:data 以 student_id 为字符串键的对象(前端按 data[sid] 取值,契约不可改)
    records = {}
    for r in rows:
        records[r["student_id"]] = {
            "id": r["id"], "student_id": r["student_id"],
            "student_name": r["student_name"], "date": r["date"],
            "grade": r["grade"], "group_id": r["group_id"],
            "group_name": r["group_name"], "group_color": r["group_color"],
        }
    return {"code": 0, "data": records}


@router.post("/homework")
def api_save_homework(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    student_id = int(data.get("student_id", 0))
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    grade = data.get("grade", "X")
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if grade not in VALID_GRADES:
        return JSONResponse({"code": 1, "msg": "无效等级"}, status_code=400)
    student = db.execute(
        "SELECT id FROM students WHERE id = ?",
        (student_id,
         )).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)
    db.execute("""
        INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET
            grade = excluded.grade,
            updated_at = datetime('now','localtime')
    """, (student_id, date, grade, hw_type_id))
    db.commit()
    return {"code": 0, "msg": "登记成功"}


@router.post("/homework/batch")
def api_batch_homework(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    grade = data.get("grade", "X")
    group_id = int(data.get("group_id", 0))
    student_ids = data.get("student_ids", [])
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if grade not in VALID_GRADES:
        return JSONResponse({"code": 1, "msg": "无效等级"}, status_code=400)
    if student_ids:
        placeholders = ",".join("?" * len(student_ids))
        db.execute(
            f"DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN ({placeholders})", [
                date, hw_type_id] + student_ids)
        db.execute(
            f"""INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE id IN ({placeholders})""", [
                date, grade, hw_type_id] + student_ids)
    elif group_id > 0:
        db.execute(
            "DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
            "(SELECT id FROM students WHERE group_id=? AND class_id=?)",
            (date,
             hw_type_id,
             group_id,
             cid))
        db.execute(
            """INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE group_id=? AND class_id=?""",
            (date,
             grade,
             hw_type_id,
             group_id,
             cid))
    else:
        db.execute(
            "DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
            "(SELECT id FROM students WHERE class_id=?)", (date, hw_type_id, cid))
        db.execute(
            """INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE class_id=?""", (date, grade, hw_type_id, cid))
    db.commit()
    return {"code": 0, "msg": "批量登记成功"}


@router.get("/homework/range")
def api_get_homework_range(start: str = "", end: str = "",
                           cid: int = Depends(get_class_id),
                           db: sqlite3.Connection = Depends(get_db)):
    if not start or not end:
        return JSONResponse({"code": 1, "msg": "请指定起始和结束日期"}, status_code=400)
    rows = db.execute("""
        SELECT h.id, h.student_id, h.date, h.grade,
               s.name as student_name, s.group_id, g.name as group_name
        FROM homework h
        JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE h.date >= ? AND h.date <= ? AND s.class_id = ?
        ORDER BY s.group_id, h.date, s.sort_order
    """, (start, end, cid)).fetchall()
    records = [{
        "id": r["id"], "student_id": r["student_id"],
        "student_name": r["student_name"], "date": r["date"],
        "grade": r["grade"], "grade_label": grade_label(r["grade"]),
        "group_id": r["group_id"], "group_name": r["group_name"] or "未分组",
    } for r in rows]
    return {"code": 0, "data": records, "total": len(records)}


@router.get("/homework/missing")
def api_get_missing_homework(
        date: str | None = None,
        homework_type_id: int = 0,
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """获取指定日期未交作业的学生列表(催交用)"""

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    hw_type_id = homework_type_id or 0
    # 获取该班级所有学生
    all_students = db.execute(
        "SELECT s.id, s.name, s.group_id, g.name as group_name "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order",
        (cid,)
    ).fetchall()
    # 获取已有记录(非X的)
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    submitted = set()
    rows = db.execute(
        "SELECT h.student_id FROM homework h "
        "JOIN students s ON h.student_id = s.id "
        "WHERE h.date = ? AND h.grade != 'X' AND s.class_id = ?" + hw_filter,
        params
    ).fetchall()
    for r in rows:
        submitted.add(r["student_id"])
    # 未提交的 = 没有记录 或 记录为X
    missing = []
    for s in all_students:
        if s["id"] not in submitted:
            missing.append({
                "student_id": s["id"],
                "student_name": s["name"],
                "group_id": s["group_id"],
                "group_name": s["group_name"] or "未分组",
            })
    return {"code": 0, "data": missing, "total": len(missing)}


# ============================================================
# 作业种类管理 API(全局,不区分班级)
# ============================================================
@router.get("/homework-types")
def api_get_homework_types(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, name, sort_order FROM homework_types ORDER BY sort_order, id"
    ).fetchall()
    types = [{"id": r["id"], "name": r["name"],
              "sort_order": r["sort_order"]} for r in rows]
    return {"code": 0, "data": types}


@router.post("/homework-types")
def api_create_homework_type(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"code": 1, "msg": "名称不能为空"}, status_code=400)
    max_sort = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) as m FROM homework_types"
    ).fetchone()["m"]
    db.execute(
        "INSERT INTO homework_types (name, sort_order) VALUES (?,?)",
        (name, max_sort + 1)
    )
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"code": 0, "msg": "已添加作业种类", "data": {"id": new_id, "name": name}}


@router.put("/homework-types/{tid}")
def api_rename_homework_type(tid: int, request: Request,
                             db: sqlite3.Connection = Depends(get_db)):
    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"code": 1, "msg": "名称不能为空"}, status_code=400)
    row = db.execute(
        "SELECT id FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not row:
        return JSONResponse({"code": 1, "msg": "作业种类不存在"}, status_code=404)
    db.execute("UPDATE homework_types SET name=? WHERE id=?", (name, tid))
    db.commit()
    return {"code": 0, "msg": "已重命名"}


@router.delete("/homework-types/{tid}")
def api_delete_homework_type(
        tid: int,
        db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT id FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not row:
        return JSONResponse({"code": 1, "msg": "作业种类不存在"}, status_code=404)
    # 检查是否只剩一个(全局)
    count = db.execute(
        "SELECT COUNT(*) as c FROM homework_types").fetchone()["c"]
    if count <= 1:
        return JSONResponse({"code": 1, "msg": "至少保留一个作业种类"}, status_code=400)
    db.execute("DELETE FROM homework_types WHERE id=?", (tid,))
    db.commit()
    return {"code": 0, "msg": "已删除"}
