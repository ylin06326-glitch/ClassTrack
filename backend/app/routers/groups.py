# -*- coding: utf-8 -*-
"""
分组管理 API:查看/初始化/整表保存/锁定/解锁/重置/移动学生
"""

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.deps import class_is_locked, get_class_id, get_db, lock_error, get_body
from app.database import GROUP_COLORS

router = APIRouter(prefix="/api", tags=["groups"])


@router.get("/groups")
def api_get_groups(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    groups = db.execute(
        "SELECT * FROM groups_info WHERE class_id = ? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    result = []
    for g in groups:
        students = db.execute(
            "SELECT id, name, sort_order FROM students "
            "WHERE group_id = ? AND class_id = ? ORDER BY sort_order, id",
            (g["id"], cid)
        ).fetchall()
        result.append({
            "id": g["id"], "name": g["name"], "color": g["color"],
            "sort_order": g["sort_order"], "is_locked": bool(g["is_locked"]),
            "students": [{"id": s["id"], "name": s["name"], "sort_order": s["sort_order"]}
                         for s in students]
        })
    unassigned = db.execute(
        "SELECT id, name FROM students WHERE (group_id = 0 OR group_id IS NULL) "
        "AND class_id = ? ORDER BY sort_order, id", (cid,)).fetchall()
    return {"code": 0, "data": {"groups": result, "unassigned": [
        {"id": s["id"], "name": s["name"]} for s in unassigned]}}


@router.post("/groups/init")
def api_init_groups(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    count = data.get("count", 0)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    if count < 2 or count > 20:
        return JSONResponse(
            {"code": 1, "msg": "分组数量需在2-20之间"}, status_code=400)
    if class_is_locked(db, cid):
        return JSONResponse(*lock_error())

    existing = db.execute(
        "SELECT * FROM groups_info WHERE class_id=? ORDER BY sort_order, id", (cid,)
    ).fetchall()
    if len(existing) > count:
        # 多余分组的学生移到未分组池,删除多余组
        for g in existing[count:]:
            db.execute(
                "UPDATE students SET group_id=0 WHERE group_id=? AND class_id=?",
                (g["id"],
                 cid))
            db.execute("DELETE FROM groups_info WHERE id=?", (g["id"],))
    elif len(existing) < count:
        # 不足则新建
        for i in range(len(existing), count):
            db.execute(
                "INSERT INTO groups_info (name, class_id, color, sort_order) VALUES (?, ?, ?, ?)",
                (f"第{i + 1}组", cid, GROUP_COLORS[i % len(GROUP_COLORS)], i)
            )
    db.commit()
    return {"code": 0, "msg": f"已设置为 {count} 个分组"}


@router.post("/groups/save")
def api_save_groups(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """锁定前的整表保存:前端 DOM 快照一次性提交"""

    groups = data.get("groups", None)
    if not isinstance(groups, list):
        return JSONResponse({"code": 1, "msg": "参数格式错误"}, status_code=400)
    if class_is_locked(db, cid):
        return JSONResponse(*lock_error())

    # 先校验所有非零 group_id 属于当前班级
    for g in groups:
        gid = g.get("group_id", 0)
        if gid and gid > 0:
            row = db.execute(
                "SELECT id FROM groups_info WHERE id=? AND class_id=?", (gid, cid)).fetchone()
            if not row:
                return JSONResponse(
                    {"code": 1, "msg": f"分组不存在: [{gid}]"}, status_code=404)
    total = 0
    for g in groups:
        gid = g.get("group_id", 0)
        student_ids = g.get("student_ids", [])
        if not student_ids:
            continue
        placeholders = ",".join("?" * len(student_ids))
        db.execute(
            f"UPDATE students SET group_id=? WHERE id IN ({placeholders}) AND class_id=?",
            [gid] + list(student_ids) + [cid])
        total += len(student_ids)
    db.commit()
    return {"code": 0, "msg": f"分组已保存（{total} 名学生）"}


@router.put("/students/{sid}/move")
def api_move_student(
        sid: int,
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    group_id = data.get("group_id", 0)
    student = db.execute(
        "SELECT class_id FROM students WHERE id=?", (sid,)).fetchone()
    if not student:
        return JSONResponse({"code": 1, "msg": "学生不存在"}, status_code=404)
    if class_is_locked(db, student["class_id"]):
        return JSONResponse(*lock_error())
    if group_id and group_id > 0:
        g = db.execute("SELECT id FROM groups_info WHERE id=?",
                       (group_id,)).fetchone()
        if not g:
            return JSONResponse({"code": 1, "msg": "分组不存在"}, status_code=404)
    db.execute("UPDATE students SET group_id=? WHERE id=?", (group_id, sid))
    db.commit()
    return {"code": 0, "msg": "移动成功"}


@router.put("/students/batch-move")
def api_batch_move_students(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    student_ids = data.get("student_ids", [])
    group_id = data.get("group_id", 0)
    if not student_ids:
        return JSONResponse({"code": 1, "msg": "未选择学生"}, status_code=400)
    if class_is_locked(db, cid):
        return JSONResponse(*lock_error())
    if group_id and group_id > 0:
        g = db.execute("SELECT id FROM groups_info WHERE id=?",
                       (group_id,)).fetchone()
        if not g:
            return JSONResponse({"code": 1, "msg": "分组不存在"}, status_code=404)
    placeholders = ",".join("?" * len(student_ids))
    db.execute(f"UPDATE students SET group_id=? WHERE id IN ({placeholders})",
               [group_id] + list(student_ids))
    db.commit()
    return {"code": 0, "msg": f"已移动 {len(student_ids)} 名学生"}


@router.post("/groups/lock")
def api_lock_groups(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    db.execute("UPDATE groups_info SET is_locked=1 WHERE class_id=?", (cid,))
    now = db.execute("SELECT datetime('now','localtime')").fetchone()[0]
    db.execute(
        "INSERT OR REPLACE INTO app_config (key,value) VALUES ('last_lock_time',?)",
        (now,
         ))
    db.commit()
    return {"code": 0, "msg": "分组已锁定", "data": {"lock_time": now}}


@router.post("/groups/unlock")
def api_unlock_groups(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    db.execute("UPDATE groups_info SET is_locked=0 WHERE class_id=?", (cid,))
    db.commit()
    return {"code": 0, "msg": "分组已解锁，可以自由调整"}


@router.post("/groups/reset")
def api_reset_groups(
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    if class_is_locked(db, cid):
        return JSONResponse(*lock_error())
    db.execute("UPDATE students SET group_id=0 WHERE class_id=?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id=?", (cid,))
    db.commit()
    return {"code": 0, "msg": "分组已重置"}
