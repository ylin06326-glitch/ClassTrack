# -*- coding: utf-8 -*-
"""
系统 API
========
应用配置读写、班级统计信息、安全关闭服务器
"""

import os
import sqlite3
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.deps import class_is_locked, get_class_id, get_db, get_body

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def api_get_config(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT key, value FROM app_config").fetchall()
    return {"code": 0, "data": {r["key"]: r["value"] for r in rows}}


@router.post("/config")
def api_save_config(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    for key, value in data.items():
        db.execute(
            "INSERT OR REPLACE INTO app_config (key,value) VALUES (?,?)",
            (str(key),
             str(value)))
    db.commit()
    return {"code": 0, "msg": "配置已保存"}


@router.get("/stats")
def api_get_stats(homework_type_id: int = 0, cid: int = Depends(get_class_id),
                  db: sqlite3.Connection = Depends(get_db)):
    hw_type_id = homework_type_id or 0
    total_students = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    total_groups = db.execute(
        "SELECT COUNT(*) as c FROM groups_info WHERE class_id=?",
        (cid,
         )).fetchone()["c"]
    grouped = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE group_id > 0 AND class_id=?", (cid,)
    ).fetchone()["c"]
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    rec_params = (cid,) if hw_type_id == 0 else (cid, hw_type_id)
    total_records = db.execute(
        f"SELECT COUNT(*) as c FROM homework h JOIN students s ON h.student_id=s.id WHERE s.class_id=?{hw_filter}",
        rec_params).fetchone()["c"]
    last_lock = db.execute(
        "SELECT value FROM app_config WHERE key='last_lock_time'").fetchone()
    cls = db.execute("SELECT name FROM classes WHERE id=?", (cid,)).fetchone()
    return {
        "code": 0,
        "data": {
            "total_students": total_students,
            "total_groups": total_groups,
            "grouped_students": grouped,
            "unassigned_students": total_students -
            grouped,
            "total_homework_records": total_records,
            "last_lock_time": last_lock["value"] if last_lock else "尚未锁定",
            "is_locked": class_is_locked(
                db,
                cid),
            "class_name": cls["name"] if cls else "",
        }}


@router.post("/shutdown")
def api_shutdown():
    """安全关闭服务器(配合 PyInstaller windowed 模式)

    原实现直接 os._exit(0),响应根本来不及返回;改为定时器延迟退出,
    保证 {"code":0,...} 能先写回前端。
    """
    timer = threading.Timer(0.3, lambda: os._exit(0))
    timer.daemon = True
    timer.start()
    return {"code": 0, "msg": "程序即将退出"}
