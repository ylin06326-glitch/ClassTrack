# -*- coding: utf-8 -*-
"""
扫码登记 API
============
学号查学生、扫码批量/单条登记、手机联动(配对/扫码/轮询/清空)、
二维码生成、CA 证书下载
"""

import io
import sqlite3
from datetime import datetime

import qrcode
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.config import get_data_dir
from app.deps import get_class_id, get_db, get_body

router = APIRouter(prefix="/api", tags=["scan"])

VALID_GRADES = ("A", "B", "C", "L", "X")


@router.get("/student/by-code/{code}")
def api_student_by_code(code: str, cid: int = Depends(get_class_id),
                        db: sqlite3.Connection = Depends(get_db)):
    """通过学号查找学生"""

    row = db.execute(
        "SELECT s.*, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.student_code = ? AND s.class_id = ?",
        (code.strip(), cid)
    ).fetchone()
    if not row:
        # 未找到:HTTP 200 + code=1(external 标记供前端识别,契约不可改)
        return {"code": 1, "msg": f"未找到学号 {code} 对应的学生", "external": True}
    return {
        "code": 0,
        "data": {
            "id": row["id"],
            "name": row["name"],
            "student_code": row["student_code"] or "",
            "group_id": row["group_id"] or 0,
            "group_name": row["group_name"] or "",
            "group_color": row["group_color"] or "",
        }}


@router.post("/scan/batch")
def api_scan_batch(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """批量提交扫码结果(使用 executemany 批量写入)"""

    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    records = data.get("records", [])  # [{student_code, grade}, ...]
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if not records:
        return JSONResponse({"code": 1, "msg": "无扫码记录"}, status_code=400)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 批量查询所有学号对应的 student_id
    codes = [r.get("student_code", "").strip() for r in records]
    placeholders = ",".join(["?" for _ in codes])
    rows = db.execute(
        f"SELECT id, student_code FROM students WHERE student_code IN ({placeholders}) AND class_id=?",
        (*codes, cid)
    ).fetchall()
    code_to_id = {r["student_code"]: r["id"] for r in rows}
    # 批量写入(executemany 比逐条 INSERT 快 10 倍+)
    batch = []
    for rec in records:
        code = rec.get("student_code", "").strip()
        grade = rec.get("grade", "X")
        if grade not in VALID_GRADES:
            continue
        sid = code_to_id.get(code)
        if not sid:
            continue
        batch.append((sid, date, grade, hw_type_id, now))
    if batch:
        db.executemany("""
            INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET
                grade = excluded.grade,
                updated_at = excluded.updated_at
        """, batch)
    db.commit()
    return {
        "code": 0, "msg": f"已保存 {
            len(batch)} 条记录", "data": {
            "saved": len(batch)}}


@router.post("/scan/single")
def api_scan_single(
        data: dict = Depends(get_body),
        cid: int = Depends(get_class_id),
        db: sqlite3.Connection = Depends(get_db)):
    """单点扫码录入"""

    code = data.get("student_code", "").strip()
    grade = data.get("grade", "X")
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if grade not in VALID_GRADES:
        return JSONResponse({"code": 1, "msg": "无效等级"}, status_code=400)
    student = db.execute(
        "SELECT id FROM students WHERE student_code=? AND class_id=?",
        (code, cid)).fetchone()
    if not student:
        # 未找到:HTTP 200 + code=1(扫码页按 external 提示学生不存在)
        return {"code": 1, "msg": f"未找到学号 {code}", "external": True}
    db.execute("""
        INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
    VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET
            grade = excluded.grade,
            updated_at = datetime('now','localtime')
    """, (student["id"], date, grade, hw_type_id))
    db.commit()
    return {"code": 0, "msg": "登记成功"}


# ============================================================
# 手机联动
# ============================================================
@router.get("/mobile/pair")
def api_mobile_pair():
    """返回配对信息(移动端使用 HTTPS 才能调用摄像头)"""

    import socket
    host = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        host = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    port = 5088
    return {
        "code": 0,
        "data": {
            "ip": host, "port": port,
            "url": f"https://{host}:{port}/mobile",
            "ssl": True,
        }
    }


@router.post("/mobile/scan/batch")
def api_mobile_scan_batch(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    """手机端批量提交扫码(一次请求提交 N 个学号)"""

    codes = data.get("codes", [])
    if not codes or not isinstance(codes, list):
        return JSONResponse({"code": 1, "msg": "无效的学号列表"}, status_code=400)
    # 去重 + 清洗
    unique = list(dict.fromkeys([c.strip() for c in codes if c and c.strip()]))
    if not unique:
        return JSONResponse({"code": 1, "msg": "无有效学号"}, status_code=400)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 批量 INSERT(比逐条快 10x+)
    db.executemany(
        "INSERT INTO mobile_scans (student_code, scanned_at) VALUES (?, ?)",
        [(c, now) for c in unique]
    )
    db.commit()
    return {
        "code": 0, "msg": f"已接收 {
            len(unique)} 条", "data": {
            "count": len(unique)}}


@router.post("/mobile/scan")
def api_mobile_scan(
        data: dict = Depends(get_body),
        db: sqlite3.Connection = Depends(get_db)):
    """手机端提交扫码(单条,保留兼容旧版)"""

    code = data.get("student_code", "").strip()
    if not code:
        return JSONResponse({"code": 1, "msg": "未识别到学号"}, status_code=400)
    db.execute(
        "INSERT INTO mobile_scans (student_code, scanned_at) VALUES (?, ?)",
        (code, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    return {"code": 0, "msg": "已接收"}


@router.get("/mobile/scans")
def api_mobile_scans(since: str = "1970-01-01 00:00:00",
                     cid: int = Depends(get_class_id),
                     db: sqlite3.Connection = Depends(get_db)):
    """电脑端轮询获取手机扫码(since 游标,回显本轮最大 scanned_at)"""

    rows = db.execute(
        "SELECT id, student_code, scanned_at FROM mobile_scans "
        "WHERE scanned_at > ? AND processed = 0 ORDER BY scanned_at",
        (since,)
    ).fetchall()
    scans = []
    max_ts = since
    for r in rows:
        student = db.execute(
            "SELECT id, name, group_id FROM students WHERE student_code=? AND class_id=?",
            (r["student_code"], cid)
        ).fetchone()
        scans.append({
            "id": r["id"], "student_code": r["student_code"],
            "scanned_at": r["scanned_at"],
            "student_name": student["name"] if student else "未知学生",
            "student_id": student["id"] if student else None,
            "found": student is not None,
        })
        max_ts = r["scanned_at"]
    return {"code": 0, "data": scans, "since": max_ts, "total": len(scans)}


@router.post("/mobile/clear")
def api_mobile_clear(db: sqlite3.Connection = Depends(get_db)):
    """清空待处理扫码"""

    db.execute("DELETE FROM mobile_scans")
    db.commit()
    return {"code": 0, "msg": "已清空"}


# ============================================================
# 二维码生成(服务端 Python 生成,无需 CDN,离线可用)
# ============================================================
@router.get("/qrcode")
def api_qrcode(data: str = "", size: int = 150):
    """生成真实二维码(PNG 格式),可通过 ?data=URL&size=200 调整尺寸"""

    if not data:
        return JSONResponse({"code": 1, "msg": "缺少 data 参数"}, status_code=400)
    # 使用 qrcode 库生成真实可扫描的二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#5D5A5A", back_color="#ffffff")
    # 缩放到目标尺寸
    img = img.resize((size, size))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# ============================================================
# CA 证书下载(供手机安装信任)
# ============================================================
@router.get("/cert/download")
def api_cert_download():
    """下载 CA 根证书,供手机等设备安装信任"""

    ca_cert_file = get_data_dir() / "ca-cert.pem"
    if not ca_cert_file.exists():
        return JSONResponse(
            {"code": 1, "msg": "CA 证书尚未生成，请先在电脑端启动一次程序"},
            status_code=404,
        )
    return FileResponse(
        str(ca_cert_file),
        filename="ClassTrack_CA_Certificate.crt",
        media_type="application/x-x509-ca-cert",
    )
