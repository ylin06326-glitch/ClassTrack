# -*- coding: utf-8 -*-
"""
班级管理 API:列出/创建/重命名/删除/切换活跃班级
"""

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.deps import get_active_class_id, get_db, get_body

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.get("")
def api_get_classes(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM classes ORDER BY id").fetchall()
    active_id = get_active_class_id(db)
    return {
        "code": 0,
        "data": [{"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
                 for r in rows],
        "active_id": active_id
    }


@router.post("")
def api_create_class(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"code": 1, "msg": "班级名称不能为空"}, status_code=400)
    db.execute("INSERT INTO classes (name) VALUES (?)", (name,))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"code": 0, "msg": f"班级「{name}」已创建", "data": {"id": new_id}}


@router.put("/{cid}")
def api_rename_class(
        cid: int,
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"code": 1, "msg": "名称不能为空"}, status_code=400)
    db.execute("UPDATE classes SET name=? WHERE id=?", (name, cid))
    db.commit()
    return {"code": 0, "msg": "已重命名"}


@router.delete("/{cid}")
def api_delete_class(cid: int, db: sqlite3.Connection = Depends(get_db)):
    # 至少保留一个班级
    count = db.execute("SELECT COUNT(*) as c FROM classes").fetchone()["c"]
    if count <= 1:
        return JSONResponse({"code": 1, "msg": "至少保留一个班级"}, status_code=400)
    # 级联删除
    student_ids = [r[0] for r in db.execute(
        "SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
    for sid in student_ids:
        db.execute("DELETE FROM homework WHERE student_id=?", (sid,))
    db.execute("DELETE FROM students WHERE class_id=?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id=?", (cid,))
    db.execute("DELETE FROM classes WHERE id=?", (cid,))
    # 切换到第一个班级
    first = db.execute("SELECT id FROM classes ORDER BY id LIMIT 1").fetchone()
    if first:
        db.execute(
            "INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)",
            (str(
                first["id"]),
             ))
    db.commit()
    return {"code": 0, "msg": "班级已删除"}


@router.post("/{cid}/activate")
def api_activate_class(cid: int, db: sqlite3.Connection = Depends(get_db)):
    cls = db.execute("SELECT id FROM classes WHERE id=?", (cid,)).fetchone()
    if not cls:
        return JSONResponse({"code": 1, "msg": "班级不存在"}, status_code=404)
    db.execute(
        "INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)",
        (str(cid),
         ))
    db.commit()
    return {"code": 0, "msg": "已切换班级"}
