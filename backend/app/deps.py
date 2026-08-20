# -*- coding: utf-8 -*-
"""
FastAPI 依赖注入
================
- get_db: 请求级 SQLite 连接
- get_class_id: 从 query/body 解析目标班级(缺省活跃班级)
- 锁定校验辅助
"""

import json
import sqlite3

from fastapi import Depends, Request

from app.database import connect


def get_db(request: Request):
    """请求级数据库连接依赖,响应完成后关闭"""
    db = connect()
    try:
        yield db
    finally:
        db.close()


def get_active_class_id(db: sqlite3.Connection) -> int:
    """获取当前活跃班级ID"""
    row = db.execute(
        "SELECT value FROM app_config WHERE key='active_class_id'"
    ).fetchone()
    return int(row["value"]) if row else 1


def get_body(request: Request) -> dict:
    """同步获取 JSON 请求体(由 _cache_json_body 中间件预先缓存)"""
    raw = getattr(request.state, "body", b"")
    if not raw:
        return {}
    try:
        return json.loads(raw) or {}
    except Exception:
        return {}


def get_class_id(request: Request, db: sqlite3.Connection = Depends(get_db), data: dict = Depends(get_body)) -> int:
    """
    从请求参数或 body 解析 class_id,缺省时取活跃班级。
    兼容旧版 get_class_id_from_request 的行为:
    query 参数 > JSON body 的 class_id 字段 > 活跃班级。
    """
    cid = request.query_params.get("class_id")
    if not cid:
        cid = data.get("class_id", 0)
    try:
        cid = int(cid) if cid else 0
    except (TypeError, ValueError):
        cid = 0
    return cid if cid > 0 else get_active_class_id(db)


def class_is_locked(db: sqlite3.Connection, cid: int) -> bool:
    """当前班级的分组是否已锁定"""
    row = db.execute(
        "SELECT 1 FROM groups_info WHERE class_id=? AND is_locked=1 LIMIT 1", (cid,)
    ).fetchone()
    return row is not None


def lock_error() -> tuple[dict, int]:
    """锁定状态下的统一错误响应"""
    return {"code": 1, "msg": "分组已锁定，请先点击「解锁分组」后再调整"}, 400
