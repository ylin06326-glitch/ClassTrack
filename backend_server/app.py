#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack.com — Web 服务（用户端）
===================================
技术栈: Python Flask + SQLite
功能:
  1. 用户页面：软件下载 + 指纹换注册码
  2. API 接口：供用户端调用（注册码生成、查询、下载）
  3. 管理后台：由 PyQt6 桌面端 (admin_app.py) 接管
     (Web 管理页 /admin 仍保留作为备选)
"""

import os
import sys
import atexit
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, request, jsonify, send_file, render_template,
    session, redirect, url_for, g as flask_g
)

# ---- PyInstaller 路径适配 ----
if getattr(sys, 'frozen', False):
    _ROOT = Path(sys._MEIPASS)
    _EXE_DIR = Path(sys.executable).resolve().parent
else:
    _ROOT = Path(__file__).resolve().parent
    _EXE_DIR = _ROOT

# ---- 导入 ClassTrack 激活模块 ----
sys.path.insert(0, str(_ROOT.parent if getattr(sys, 'frozen', False) else _ROOT.parent))
_ACTIVATION_AVAILABLE = False
_PRIVATE_KEY_PEM = None
try:
    from activation.crypto import load_private_key_from_pem
    from activation.license_manager import generate_activation, decode_fingerprint, export_fingerprint
    from activation.hardware_id import collect_hardware_id, hardware_id_to_machine_code

    # 加载商家私钥
    if getattr(sys, 'frozen', False):
        _key_file = _EXE_DIR / "activation" / "private_key.pem"
    else:
        _key_file = _ROOT.parent / "activation" / "private_key.pem"
    if _key_file.exists():
        _PRIVATE_KEY_PEM = _key_file.read_text(encoding="utf-8")
        load_private_key_from_pem(_PRIVATE_KEY_PEM)  # 验证私钥有效
        _ACTIVATION_AVAILABLE = True
        print(f"  ✅ 激活模块已加载，私钥就绪: {_key_file}")
    else:
        print(f"  ⚠️ 未找到私钥文件: {_key_file}")
except Exception as e:
    print(f"  ⚠️ 激活模块加载失败: {e}")

# ============================================================
# 路径配置
# ============================================================
ROOT = _ROOT
DATA_DIR = _EXE_DIR / "data"
DB_PATH = DATA_DIR / "classtrack_server.db"
FILES_DIR = DATA_DIR / "files"
MEDIA_DIR = DATA_DIR / "media"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "static"))
app.secret_key = "classtrack_server_secret_2026"

# ---- 隧道 + 订单模块 ----
from tunnel import TunnelManager
from order_utils import (
    generate_order_no, calculate_expiry, expire_stale_orders,
    validate_status_transition, get_status_label, get_status_color,
    VALID_STATUSES
)


# ============================================================
# 数据库管理
# ============================================================
def get_db():
    if "db" not in flask_g:
        flask_g.db = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
        flask_g.db.row_factory = sqlite3.Row
        flask_g.db.execute("PRAGMA journal_mode=WAL")
        flask_g.db.execute("PRAGMA foreign_keys=ON")
    return flask_g.db


@app.teardown_appcontext
def close_db(error):
    db = flask_g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        -- 注册码记录（用户通过指纹申请）
        CREATE TABLE IF NOT EXISTS registration_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            reg_code TEXT NOT NULL UNIQUE,
            user_note TEXT DEFAULT '',
            is_paid INTEGER DEFAULT 0,
            paid_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 供下载的软件包记录
        CREATE TABLE IF NOT EXISTS software_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            version TEXT DEFAULT '1.0.0',
            file_size INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 系统配置
        CREATE TABLE IF NOT EXISTS server_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        -- 管理日志
        CREATE TABLE IF NOT EXISTS admin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 订单记录（v2.0 新增）
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            fingerprint TEXT DEFAULT '',
            reg_code TEXT DEFAULT '',
            amount REAL DEFAULT 0.00,
            payment_method TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            txn_id TEXT DEFAULT '',
            paid_at TEXT DEFAULT NULL,
            expired_at TEXT DEFAULT NULL,
            refunded_at TEXT DEFAULT NULL,
            cancelled_at TEXT DEFAULT NULL,
            user_note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    # ---- 迁移：registration_codes 增加新列 ----
    _migrate_registration_codes(db)

    # ---- 默认配置 ----
    defaults = {
        "payment_api_url": "",
        "payment_api_enabled": "0",
        "payment_api_key": "",
        "payment_simulation_mode": "1",
        "hero_video_filename": "",
        "payment_qr_filename": "",
        "payment_instructions": "请使用微信或支付宝扫描二维码完成付款\n付款后请点击下方「模拟支付成功」验证并解锁下载",
        # v2.0 新增
        "order_expiry_minutes": "30",
        "tunnel_enabled": "1",
        "tunnel_backend": "serveo",
        "tunnel_ngrok_auth_token": "",
        "tunnel_public_url": "",
        "default_amount": "0.00",
    }
    for k, v in defaults.items():
        existing = db.execute("SELECT value FROM server_config WHERE key=?", (k,)).fetchone()
        if not existing:
            db.execute("INSERT INTO server_config (key, value) VALUES (?, ?)", (k, v))

    db.commit()
    db.close()


def _migrate_registration_codes(db):
    """安全迁移：为 registration_codes 表增加 order_id / order_no 列（如不存在）"""
    existing_cols = {r[1] for r in db.execute("PRAGMA table_info(registration_codes)").fetchall()}
    if "order_id" not in existing_cols:
        db.execute("ALTER TABLE registration_codes ADD COLUMN order_id INTEGER DEFAULT NULL")
    if "order_no" not in existing_cols:
        db.execute("ALTER TABLE registration_codes ADD COLUMN order_no TEXT DEFAULT ''")
    if "amount" not in existing_cols:
        db.execute("ALTER TABLE registration_codes ADD COLUMN amount REAL DEFAULT 0.00")
    if "payment_method" not in existing_cols:
        db.execute("ALTER TABLE registration_codes ADD COLUMN payment_method TEXT DEFAULT ''")


# ============================================================
# 辅助函数
# ============================================================
def generate_reg_code(fingerprint: str) -> str:
    """根据用户指纹生成真实激活密钥（RSA签名）

    校验逻辑与 merchant_tool.py 完全一致：
    1. 空输入检查
    2. 机器码误输入检测（含短横线、长度<80）
    3. Base64解码指纹 → 原始硬件ID
    4. 解码失败时判断是否为原始硬件ID（长度>=10）
    5. RSA私钥签名生成激活密钥
    """
    # ---- 步骤0: 空输入 ----
    if not fingerprint:
        raise ValueError("请输入机器指纹（从客户端'复制机器指纹'按钮获取）")

    # ---- 步骤1: 机器码误输入检测 ----
    # 机器码格式: XXXX-XXXX-...（含短横线, ~47字符）
    # 机器指纹格式: Base64（无短横线, ~30-50字符）
    if "-" in fingerprint and len(fingerprint) < 80:
        raise ValueError(
            "检测到您粘贴的是「机器码」（短横线格式），不能用于生成激活密钥。"
            "请点击客户端激活页的「复制机器指纹（发送给商家）」按钮，"
            "然后粘贴到这里。机器指纹是一长串字母数字（约30-50字符），不含短横线。"
        )

    # ---- 步骤2: 解码指纹 (Base64 → 原始硬件ID) ----
    hardware_id = decode_fingerprint(fingerprint)
    if hardware_id is None:
        # 未被识别为有效指纹
        if len(fingerprint) < 10:
            raise ValueError(
                "无法识别此内容。请确保从客户端激活页面点击的是："
                "「复制机器指纹（发送给商家）」，而不是复制「机器码」。"
                "（机器码带短横线，仅供查看）"
            )
        # 可能是用户直接发送了原始硬件ID
        hardware_id = fingerprint

    if not hardware_id:
        raise ValueError("无法解析机器指纹，请确认复制的内容完整。")

    # ---- 步骤3: 生成激活密钥 ----
    if not _ACTIVATION_AVAILABLE:
        # 降级：使用简单哈希（不推荐，仅开发用）
        raw = f"{fingerprint}_CLASSTRACK_SALT_2026"
        h = hashlib.sha256(raw.encode()).hexdigest()[:20].upper()
        return f"CT-{h[:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"

    activation = generate_activation(_PRIVATE_KEY_PEM, hardware_id)
    if activation is None:
        raise ValueError("激活密钥生成失败，请检查私钥配置。")

    return activation


def is_admin_logged_in() -> bool:
    return session.get("admin_logged_in", False)


def admin_required(f):
    """装饰器：需要管理员登录"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin_logged_in():
            return redirect(url_for("page_admin_login"))
        return f(*args, **kwargs)
    return decorated


# ============================================================
# 公开页面 — 用户首页
# ============================================================
@app.route("/")
def page_index():
    """ClassTrack.com 首页"""
    return render_template("index.html")


# ============================================================
# 用户 API — 指纹换注册码
# ============================================================
@app.route("/api/exchange-code", methods=["POST"])
def api_exchange_code():
    """用户提交指纹，获取激活密钥"""
    data = request.get_json(silent=True) or {}
    fingerprint = (data.get("fingerprint", "") or "").strip()
    user_note = (data.get("user_note", "") or "").strip()

    # ---- 生成激活密钥（校验逻辑内置在 generate_reg_code 中）----
    try:
        reg_code = generate_reg_code(fingerprint)
    except ValueError as e:
        return jsonify({"code": 1, "msg": str(e)}), 400
    except Exception as e:
        return jsonify({"code": 1, "msg": f"激活密钥生成失败: {str(e)}"}), 500

    if reg_code is None:
        return jsonify({"code": 1, "msg": "激活密钥生成失败，请联系管理员"}), 500

    db = get_db()

    # 检查是否已有记录
    existing = db.execute(
        "SELECT id, reg_code, is_paid FROM registration_codes WHERE fingerprint = ? ORDER BY id DESC LIMIT 1",
        (fingerprint,)
    ).fetchone()

    if existing:
        return jsonify({
            "code": 0,
            "msg": "该指纹已有激活密钥",
            "data": {
                "reg_code": existing["reg_code"],
                "is_paid": bool(existing["is_paid"]),
                "is_existing": True,
            }
        })

    db.execute(
        "INSERT INTO registration_codes (fingerprint, reg_code, user_note) VALUES (?, ?, ?)",
        (fingerprint, reg_code, user_note)
    )

    # 记录日志
    fp_short = fingerprint[:16] + "..." if len(fingerprint) > 16 else fingerprint
    code_short = reg_code[:20] + "..." if len(reg_code) > 20 else reg_code
    db.execute(
        "INSERT INTO admin_log (action, detail) VALUES (?, ?)",
        ("new_registration", f"指纹: {fp_short}, 密钥: {code_short}")
    )
    db.commit()

    return jsonify({
        "code": 0,
        "msg": "激活密钥已生成",
        "data": {
            "reg_code": reg_code,
            "is_paid": False,
            "is_existing": False,
        }
    })


@app.route("/api/check-code", methods=["POST"])
def api_check_code():
    """查询注册码状态"""
    data = request.get_json(silent=True) or {}
    reg_code = (data.get("reg_code", "") or "").strip().upper()

    if not reg_code:
        return jsonify({"code": 1, "msg": "请输入注册码"}), 400

    db = get_db()
    row = db.execute(
        "SELECT id, reg_code, is_paid, paid_at, fingerprint, created_at FROM registration_codes WHERE reg_code = ?",
        (reg_code,)
    ).fetchone()

    if not row:
        return jsonify({"code": 1, "msg": "未找到该注册码，请确认输入正确"}), 404

    return jsonify({
        "code": 0,
        "data": {
            "reg_code": row["reg_code"],
            "is_paid": bool(row["is_paid"]),
            "paid_at": row["paid_at"],
            "created_at": row["created_at"],
            "fingerprint_masked": row["fingerprint"][:8] + "****" if len(row["fingerprint"]) > 8 else "****",
        }
    })


# ============================================================
# 媒体文件服务
# ============================================================
@app.route("/api/media/<path:filename>", methods=["GET"])
def api_serve_media(filename: str):
    """提供上传的媒体文件（视频、图片等）"""
    # 安全检查：防止路径穿越
    safe_name = Path(filename).name
    file_path = MEDIA_DIR / safe_name
    if not file_path.exists():
        return jsonify({"code": 1, "msg": "文件不存在"}), 404

    ext = file_path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml",
    }
    mime = mime_map.get(ext, "application/octet-stream")
    return send_file(str(file_path), mimetype=mime)


@app.route("/api/media-info", methods=["GET"])
def api_media_info():
    """返回当前媒体文件信息"""
    db = get_db()
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key IN ('hero_video_filename','payment_qr_filename')"
    ).fetchall()}
    return jsonify({
        "code": 0,
        "data": {
            "hero_video": rows.get("hero_video_filename", ""),
            "payment_qr": rows.get("payment_qr_filename", ""),
        }
    })


# ============================================================
# 付款 & 购买流程
# ============================================================
@app.route("/api/payment/info", methods=["GET"])
def api_payment_info():
    """获取付款信息"""
    db = get_db()
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key IN ('payment_qr_filename','payment_instructions')"
    ).fetchall()}
    qr = rows.get("payment_qr_filename", "")
    return jsonify({
        "code": 0,
        "data": {
            "qr_url": f"/api/media/{qr}" if qr else "",
            "has_qr": bool(qr),
            "instructions": rows.get("payment_instructions", ""),
        }
    })


@app.route("/api/payment/submit", methods=["POST"])
def api_payment_submit():
    """用户提交付款信息 — v2.0 创建订单"""
    data = request.get_json(silent=True) or {}
    fingerprint = (data.get("fingerprint", "") or "").strip()
    txn_id = (data.get("txn_id", "") or "").strip()
    user_note = (data.get("user_note", "") or "").strip()
    payment_method = (data.get("payment_method", "") or "manual").strip()

    db = get_db()

    # 读取配置
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key IN ('order_expiry_minutes','default_amount')"
    ).fetchall()}
    amount = float(rows.get("default_amount", "0") or "0")
    expiry_mins = rows.get("order_expiry_minutes", "30")

    reg_code = None
    # 检查是否已有注册码
    existing = db.execute(
        "SELECT id, reg_code, is_paid, order_id FROM registration_codes WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
        (fingerprint,)
    ).fetchone()

    if existing:
        reg_code = existing["reg_code"]
        # 更新备注
        db.execute("UPDATE registration_codes SET user_note=? WHERE id=?",
                   (f"交易号:{txn_id}" + (f" | {user_note}" if user_note else ""), existing["id"]))
    else:
        # 生成新注册码
        try:
            reg_code = generate_reg_code(fingerprint)
        except ValueError as e:
            return jsonify({"code": 1, "msg": str(e)}), 400
        except Exception as e:
            return jsonify({"code": 1, "msg": f"激活密钥生成失败: {str(e)}"}), 500

    # ---- 如果还没有关联订单，创建新订单 ----
    order_no = None
    order_status = "pending"
    if existing and existing["order_id"]:
        # 已有订单，查询状态
        order_row = db.execute(
            "SELECT order_no, status FROM orders WHERE id=?", (existing["order_id"],)
        ).fetchone()
        if order_row:
            order_no = order_row["order_no"]
            order_status = order_row["status"]
        # 更新交易号
        if txn_id:
            db.execute("UPDATE orders SET txn_id=? WHERE id=?", (txn_id, existing["order_id"]))

    if not order_no:
        # 创建新订单
        expired_at = calculate_expiry(expiry_mins)
        order_no = generate_order_no(db)
        db.execute(
            "INSERT INTO orders (order_no, fingerprint, reg_code, amount, payment_method, "
            "status, txn_id, expired_at, user_note) VALUES (?,?,?,?,?,?,?,?,?)",
            (order_no, fingerprint, reg_code, amount, payment_method,
             "pending", txn_id, expired_at, user_note)
        )
        order_row = db.execute("SELECT id FROM orders WHERE order_no=?", (order_no,)).fetchone()
        order_id = order_row["id"]

        if existing:
            db.execute("UPDATE registration_codes SET order_id=?, order_no=? WHERE id=?",
                       (order_id, order_no, existing["id"]))
        else:
            db.execute(
                "INSERT INTO registration_codes (fingerprint, reg_code, user_note, order_id, order_no, amount, payment_method) "
                "VALUES (?,?,?,?,?,?,?)",
                (fingerprint, reg_code, f"交易号:{txn_id}" + (f" | {user_note}" if user_note else ""),
                 order_id, order_no, amount, payment_method)
            )

    db.execute("INSERT INTO admin_log (action, detail) VALUES ('new_order', ?)",
               (f"订单 {order_no}: 指纹={fingerprint[:16]}... 金额={amount} 状态={order_status}",))
    db.commit()

    return jsonify({
        "code": 0,
        "msg": "订单已创建，请完成付款",
        "data": {
            "order_no": order_no,
            "reg_code": reg_code,
            "amount": amount,
            "status": order_status,
            "is_paid": order_status == "paid",
        }
    })


# ============================================================
# 支付 API 框架（可配置真实支付接口或模拟模式）
# ============================================================
@app.route("/api/payment/config", methods=["GET"])
def api_payment_config():
    """获取支付配置"""
    db = get_db()
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key LIKE 'payment_%'"
    ).fetchall()}
    return jsonify({
        "code": 0,
        "data": {
            "api_enabled": rows.get("payment_api_enabled", "0") == "1",
            "api_url": rows.get("payment_api_url", ""),
            "simulation_mode": rows.get("payment_simulation_mode", "1") == "1",
        }
    })


@app.route("/api/payment/verify", methods=["POST"])
def api_payment_verify():
    """验证支付交易 — v2.0 更新订单状态"""
    data = request.get_json(silent=True) or {}
    txn_id = (data.get("txn_id", "") or "").strip()
    fingerprint = (data.get("fingerprint", "") or "").strip()
    order_no = (data.get("order_no", "") or "").strip()

    if not txn_id and not order_no:
        return jsonify({"code": 1, "msg": "请输入付款交易号或订单号"}), 400

    db = get_db()

    # 读取支付配置
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key LIKE 'payment_%'"
    ).fetchall()}
    api_url = rows.get("payment_api_url", "")
    api_enabled = rows.get("payment_api_enabled", "0") == "1"
    api_key = rows.get("payment_api_key", "")

    verified = False
    verify_msg = ""

    if api_enabled and api_url:
        # ---- 真实支付 API 调用 ----
        try:
            import urllib.request
            import json as _json
            req = urllib.request.Request(
                api_url,
                data=_json.dumps({"txn_id": txn_id, "api_key": api_key}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = _json.loads(resp.read().decode("utf-8"))
                verified = result.get("verified", False) or result.get("paid", False)
                verify_msg = result.get("msg", "") or result.get("message", "")
        except Exception as e:
            verify_msg = f"支付接口调用失败: {str(e)}"
            verified = rows.get("payment_simulation_mode", "1") == "1"
            if verified:
                verify_msg += "（已自动切换为模拟验证模式）"
    elif rows.get("payment_simulation_mode", "1") == "1":
        # ---- 模拟模式 ----
        verified = len(txn_id) >= 6
        verify_msg = "模拟验证通过" if verified else "交易号格式不正确（模拟模式要求至少6位字符）"
    else:
        verify_msg = "支付接口未配置，请联系管理员"

    if verified:
        reg_code = None
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ---- 更新订单 ----
        if order_no:
            order_row = db.execute("SELECT id, fingerprint FROM orders WHERE order_no=?", (order_no,)).fetchone()
            if order_row:
                db.execute(
                    "UPDATE orders SET status='paid', txn_id=?, paid_at=? WHERE order_no=?",
                    (txn_id, now_str, order_no)
                )
                if not fingerprint and order_row["fingerprint"]:
                    fingerprint = order_row["fingerprint"]

        # ---- 更新注册码 ----
        if fingerprint:
            existing = db.execute(
                "SELECT id, reg_code, order_id FROM registration_codes WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
                (fingerprint,)
            ).fetchone()
            if existing:
                reg_code = existing["reg_code"]
                db.execute(
                    "UPDATE registration_codes SET is_paid=1, paid_at=? WHERE id=?",
                    (now_str, existing["id"])
                )
                # 同时更新关联的订单
                if existing["order_id"] and not order_no:
                    db.execute(
                        "UPDATE orders SET status='paid', txn_id=?, paid_at=? WHERE id=?",
                        (txn_id, now_str, existing["order_id"])
                    )
                    order_no_row = db.execute("SELECT order_no FROM orders WHERE id=?", (existing["order_id"],)).fetchone()
                    if order_no_row:
                        order_no = order_no_row["order_no"]
            else:
                # 生成新注册码并标记已付
                try:
                    reg_code = generate_reg_code(fingerprint)
                except ValueError as e:
                    return jsonify({"code": 1, "msg": str(e)}), 400
                db.execute(
                    "INSERT INTO registration_codes (fingerprint, reg_code, user_note, is_paid, paid_at) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (fingerprint, reg_code, f"交易号:{txn_id}", now_str)
                )

        db.execute(
            "INSERT INTO admin_log (action, detail) VALUES ('payment_verified', ?)",
            (f"{'订单 '+order_no if order_no else '交易号:'+txn_id} 验证成功",)
        )
        db.commit()

        # 授权下载
        session["download_authorized"] = True
        session["download_reg_code"] = reg_code or txn_id

        return jsonify({
            "code": 0,
            "msg": verify_msg or "支付验证成功",
            "data": {
                "verified": True,
                "txn_id": txn_id,
                "order_no": order_no,
                "reg_code": reg_code,
            }
        })

    return jsonify({
        "code": 1,
        "msg": verify_msg or "支付验证失败",
        "data": {"verified": False}
    }), 402


@app.route("/api/payment/simulate", methods=["POST"])
def api_payment_simulate():
    """模拟支付成功（测试用）— v2.0 创建订单"""
    data = request.get_json(silent=True) or {}
    fingerprint = (data.get("fingerprint", "") or "").strip()

    db = get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 读取默认金额
    rows = {r["key"]: r["value"] for r in db.execute(
        "SELECT key, value FROM server_config WHERE key IN ('default_amount','order_expiry_minutes')"
    ).fetchall()}
    amount = float(rows.get("default_amount", "0") or "0")

    reg_code = None
    order_no = None
    if fingerprint:
        existing = db.execute(
            "SELECT id, reg_code, is_paid, order_id FROM registration_codes WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
            (fingerprint,)
        ).fetchone()

        if existing:
            reg_code = existing["reg_code"]
            db.execute(
                "UPDATE registration_codes SET is_paid=1, paid_at=? WHERE id=?",
                (now_str, existing["id"])
            )
            # 更新关联订单
            if existing["order_id"]:
                db.execute("UPDATE orders SET status='paid', paid_at=? WHERE id=?",
                           (now_str, existing["order_id"]))
                orow = db.execute("SELECT order_no FROM orders WHERE id=?", (existing["order_id"],)).fetchone()
                if orow:
                    order_no = orow["order_no"]
            else:
                # 创建订单
                order_no = generate_order_no(db)
                db.execute(
                    "INSERT INTO orders (order_no, fingerprint, reg_code, amount, status, paid_at, user_note) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (order_no, fingerprint, reg_code, amount, "paid", now_str, "模拟支付")
                )
                oid = db.execute("SELECT id FROM orders WHERE order_no=?", (order_no,)).fetchone()["id"]
                db.execute("UPDATE registration_codes SET order_id=?, order_no=? WHERE id=?",
                           (oid, order_no, existing["id"]))
        else:
            try:
                reg_code = generate_reg_code(fingerprint)
            except ValueError as e:
                return jsonify({"code": 1, "msg": str(e)}), 400
            order_no = generate_order_no(db)
            db.execute(
                "INSERT INTO orders (order_no, fingerprint, reg_code, amount, status, paid_at, user_note) "
                "VALUES (?,?,?,?,?,?,?)",
                (order_no, fingerprint, reg_code, amount, "paid", now_str, "模拟支付")
            )
            oid = db.execute("SELECT id FROM orders WHERE order_no=?", (order_no,)).fetchone()["id"]
            db.execute(
                "INSERT INTO registration_codes (fingerprint, reg_code, user_note, is_paid, paid_at, order_id, order_no, amount) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (fingerprint, reg_code, "模拟支付", now_str, oid, order_no, amount)
            )

        db.execute(
            "INSERT INTO admin_log (action, detail) VALUES ('payment_simulated', ?)",
            (f"模拟支付: 订单={order_no} 指纹={fingerprint[:16]}...",)
        )
    else:
        order_no = generate_order_no(db)
        db.execute(
            "INSERT INTO orders (order_no, amount, status, paid_at, user_note) VALUES (?,?,?,?,?)",
            (order_no, amount, "paid", now_str, "模拟支付（无指纹）")
        )
        db.execute(
            "INSERT INTO admin_log (action, detail) VALUES ('payment_simulated', ?)",
            ("模拟支付（无指纹）",)
        )

    db.commit()

    session["download_authorized"] = True
    session["download_reg_code"] = reg_code or "simulated"

    return jsonify({
        "code": 0,
        "msg": "模拟支付成功！现在可以下载软件了",
        "data": {
            "verified": True,
            "reg_code": reg_code,
            "order_no": order_no,
            "simulated": True,
        }
    })


@app.route("/api/verify-download", methods=["POST"])
def api_verify_download():
    """验证注册码是否已付款，解锁下载"""
    data = request.get_json(silent=True) or {}
    reg_code = (data.get("reg_code", "") or "").strip().upper()

    if not reg_code:
        return jsonify({"code": 1, "msg": "请输入注册码"}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM registration_codes WHERE reg_code=?", (reg_code,)
    ).fetchone()

    if not row:
        return jsonify({"code": 1, "msg": "未找到该注册码，请确认输入正确"}), 404

    if not row["is_paid"]:
        return jsonify({"code": 1, "msg": "该注册码尚未付款，请先完成支付"}), 403

    # 已付款 → 授权下载
    session["download_authorized"] = True
    session["download_reg_code"] = reg_code

    # 同时返回可用软件包列表
    packages = db.execute(
        "SELECT id, filename, version, file_size, download_count FROM software_packages WHERE is_active=1 ORDER BY id DESC"
    ).fetchall()

    return jsonify({
        "code": 0,
        "msg": "验证通过，下载已解锁",
        "data": {
            "authorized": True,
            "reg_code": reg_code,
            "is_paid": True,
            "packages": [{
                "id": p["id"], "filename": p["filename"], "version": p["version"],
                "file_size_mb": f"{p['file_size']/1024/1024:.1f} MB" if p["file_size"] else "未知",
                "download_count": p["download_count"],
                "download_url": f"/api/download/{p['id']}",
            } for p in packages]
        }
    })


# ============================================================
# 管理端 — 媒体上传
# ============================================================
@app.route("/api/admin/upload-media", methods=["POST"])
@admin_required
def api_admin_upload_media():
    """管理端上传媒体文件（视频/二维码）"""
    if "file" not in request.files:
        return jsonify({"code": 1, "msg": "未选择文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"code": 1, "msg": "文件名为空"}), 400

    media_type = (request.form.get("media_type", "") or "").strip()
    if media_type not in ("hero_video", "payment_qr"):
        return jsonify({"code": 1, "msg": "无效的媒体类型"}), 400

    ext = Path(file.filename).suffix.lower()
    if media_type == "hero_video" and ext not in (".mp4", ".webm"):
        return jsonify({"code": 1, "msg": "视频仅支持 .mp4 / .webm 格式"}), 400
    if media_type == "payment_qr" and ext not in (".png", ".jpg", ".jpeg"):
        return jsonify({"code": 1, "msg": "二维码仅支持 .png / .jpg / .jpeg 格式"}), 400

    config_key = "hero_video_filename" if media_type == "hero_video" else "payment_qr_filename"
    prefix = "hero_video" if media_type == "hero_video" else "payment_qr"
    new_filename = f"{prefix}{ext}"

    # 删除旧文件
    db = get_db()
    old = db.execute("SELECT value FROM server_config WHERE key=?", (config_key,)).fetchone()
    if old and old["value"]:
        old_path = MEDIA_DIR / old["value"]
        try:
            if old_path.exists():
                old_path.unlink()
        except Exception:
            pass

    # 保存新文件
    file_path = MEDIA_DIR / new_filename
    file.save(str(file_path))

    # 更新配置
    db.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
               (config_key, new_filename))
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('upload_media', ?)",
               (f"上传{'视频' if media_type=='hero_video' else '二维码'}: {new_filename}",))
    db.commit()

    return jsonify({
        "code": 0,
        "msg": f"{'视频' if media_type=='hero_video' else '二维码'}上传成功",
        "data": {"filename": new_filename, "url": f"/api/media/{new_filename}"}
    })


# ============================================================
# 用户端 — 软件下载
# ============================================================
@app.route("/api/download-info", methods=["GET"])
def api_download_info():
    """获取可下载的软件列表"""
    db = get_db()
    rows = db.execute(
        "SELECT id, filename, version, file_size, download_count FROM software_packages WHERE is_active = 1 ORDER BY id DESC"
    ).fetchall()

    packages = []
    for r in rows:
        packages.append({
            "id": r["id"],
            "filename": r["filename"],
            "version": r["version"],
            "file_size": r["file_size"],
            "file_size_mb": f"{r['file_size'] / 1024 / 1024:.1f} MB" if r["file_size"] > 0 else "未知",
            "download_count": r["download_count"],
            "download_url": f"/api/download/{r['id']}",
        })

    return jsonify({"code": 0, "data": packages})


@app.route("/api/download/<int:pid>", methods=["GET"])
def api_download(pid: int):
    """下载软件包（需要付款验证）"""
    if not session.get("download_authorized"):
        return jsonify({"code": 1, "msg": "请先验证已付款的注册码后再下载"}), 403

    db = get_db()
    row = db.execute("SELECT * FROM software_packages WHERE id = ? AND is_active = 1", (pid,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "文件不存在或已下架"}), 404

    file_path = FILES_DIR / row["filename"]
    if not file_path.exists():
        return jsonify({"code": 1, "msg": "文件实体丢失，请联系管理员"}), 404

    db.execute("UPDATE software_packages SET download_count = download_count + 1 WHERE id = ?", (pid,))
    db.commit()

    return send_file(str(file_path), as_attachment=True, download_name=row["filename"])


@app.route("/api/download-status", methods=["GET"])
def api_download_status():
    """检查当前会话下载授权状态"""
    authorized = session.get("download_authorized", False)
    reg_code = session.get("download_reg_code", "")
    return jsonify({
        "code": 0,
        "data": {
            "authorized": authorized,
            "reg_code": reg_code,
        }
    })


# ============================================================
# 管理员 — 登录
# ============================================================
ADMIN_PASSWORD = "admin123"


@app.route("/admin/login", methods=["GET"])
def page_admin_login():
    if is_admin_logged_in():
        return redirect(url_for("page_admin"))
    return render_template("admin_login.html")


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    password = (data.get("password", "") or "")

    if password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        db = get_db()
        db.execute("INSERT INTO admin_log (action, detail) VALUES ('admin_login', '管理员登录成功')")
        db.commit()
        return jsonify({"code": 0, "msg": "登录成功", "data": {"redirect": "/admin"}})

    return jsonify({"code": 1, "msg": "密码错误"}), 401


@app.route("/admin/logout")
def page_admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("page_admin_login"))


# ============================================================
# 管理员 — 管理看板
# ============================================================
@app.route("/admin")
@admin_required
def page_admin():
    return render_template("admin.html")


@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def api_admin_stats():
    db = get_db()

    total_codes = db.execute("SELECT COUNT(*) as c FROM registration_codes").fetchone()["c"]
    paid_codes = db.execute("SELECT COUNT(*) as c FROM registration_codes WHERE is_paid = 1").fetchone()["c"]
    unpaid_codes = total_codes - paid_codes

    total_downloads = db.execute(
        "SELECT COALESCE(SUM(download_count), 0) as c FROM software_packages"
    ).fetchone()["c"]

    today = datetime.now().strftime("%Y-%m-%d")
    today_new = db.execute(
        "SELECT COUNT(*) as c FROM registration_codes WHERE date(created_at) = ?", (today,)
    ).fetchone()["c"]

    # ---- 订单统计 (v2.0) ----
    total_orders = db.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
    pending_orders = db.execute("SELECT COUNT(*) as c FROM orders WHERE status='pending'").fetchone()["c"]
    today_orders = db.execute(
        "SELECT COUNT(*) as c FROM orders WHERE date(created_at) = ?", (today,)
    ).fetchone()["c"]
    today_revenue = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as c FROM orders WHERE status='paid' AND date(paid_at) = ?", (today,)
    ).fetchone()["c"]
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as c FROM orders WHERE status='paid'"
    ).fetchone()["c"]

    return jsonify({
        "code": 0,
        "data": {
            "total_codes": total_codes,
            "paid_codes": paid_codes,
            "unpaid_codes": unpaid_codes,
            "total_downloads": total_downloads,
            "today_new": today_new,
            # v2.0 订单数据
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "today_orders": today_orders,
            "today_revenue": round(today_revenue, 2),
            "total_revenue": round(total_revenue, 2),
        }
    })


@app.route("/api/admin/records", methods=["GET"])
@admin_required
def api_admin_records():
    """获取注册记录列表"""
    db = get_db()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    status = request.args.get("status", "all")  # all / paid / unpaid
    search = (request.args.get("search", "") or "").strip()

    where = "WHERE 1=1"
    params = []
    if status == "paid":
        where += " AND is_paid = 1"
    elif status == "unpaid":
        where += " AND is_paid = 0"

    if search:
        where += " AND (fingerprint LIKE ? OR reg_code LIKE ? OR user_note LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    total = db.execute(f"SELECT COUNT(*) as c FROM registration_codes {where}", params).fetchone()["c"]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM registration_codes {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    records = []
    for r in rows:
        records.append({
            "id": r["id"],
            "fingerprint": r["fingerprint"][:20] + "..." if len(r["fingerprint"]) > 20 else r["fingerprint"],
            "fingerprint_full": r["fingerprint"],
            "reg_code": r["reg_code"],
            "user_note": r["user_note"],
            "is_paid": bool(r["is_paid"]),
            "paid_at": r["paid_at"],
            "created_at": r["created_at"],
            "order_no": r["order_no"] if "order_no" in r.keys() else "",
            "amount": r["amount"] if "amount" in r.keys() else 0.00,
        })

    return jsonify({
        "code": 0,
        "data": {
            "records": records,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        }
    })


@app.route("/api/admin/mark-paid", methods=["POST"])
@admin_required
def api_admin_mark_paid():
    """标记为已付款"""
    data = request.get_json(silent=True) or {}
    record_id = int(data.get("id", 0))
    is_paid = bool(data.get("is_paid", True))  # True=标记已付, False=取消

    db = get_db()
    row = db.execute("SELECT id, reg_code, is_paid FROM registration_codes WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "记录不存在"}), 404

    if is_paid:
        db.execute(
            "UPDATE registration_codes SET is_paid = 1, paid_at = datetime('now','localtime') WHERE id = ?",
            (record_id,)
        )
        db.execute(
            "INSERT INTO admin_log (action, detail) VALUES ('mark_paid', ?)",
            (f"注册码 {row['reg_code']} 标记为已付款",)
        )
        msg = "已标记为已付款"
    else:
        db.execute("UPDATE registration_codes SET is_paid = 0, paid_at = NULL WHERE id = ?", (record_id,))
        db.execute(
            "INSERT INTO admin_log (action, detail) VALUES ('unmark_paid', ?)",
            (f"注册码 {row['reg_code']} 取消已付款标记",)
        )
        msg = "已取消已付款标记"

    db.commit()
    return jsonify({"code": 0, "msg": msg})


@app.route("/api/admin/delete-record", methods=["POST"])
@admin_required
def api_admin_delete_record():
    """删除注册记录"""
    data = request.get_json(silent=True) or {}
    record_id = int(data.get("id", 0))

    db = get_db()
    row = db.execute("SELECT id, reg_code FROM registration_codes WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "记录不存在"}), 404

    db.execute("DELETE FROM registration_codes WHERE id = ?", (record_id,))
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('delete_record', ?)",
               (f"删除注册码 {row['reg_code']}",))
    db.commit()
    return jsonify({"code": 0, "msg": "记录已删除"})


# ============================================================
# 管理员 — 软件包管理
# ============================================================
@app.route("/api/admin/packages", methods=["GET"])
@admin_required
def api_admin_packages():
    db = get_db()
    rows = db.execute("SELECT * FROM software_packages ORDER BY id DESC").fetchall()
    return jsonify({"code": 0, "data": [{
        "id": r["id"], "filename": r["filename"], "version": r["version"],
        "file_size": r["file_size"],
        "file_size_mb": f"{r['file_size'] / 1024 / 1024:.1f} MB" if r["file_size"] > 0 else "未知",
        "download_count": r["download_count"],
        "is_active": bool(r["is_active"]),
        "created_at": r["created_at"],
    } for r in rows]})


@app.route("/api/admin/packages/upload", methods=["POST"])
@admin_required
def api_admin_upload_package():
    """上传软件包"""
    if "file" not in request.files:
        return jsonify({"code": 1, "msg": "未选择文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"code": 1, "msg": "文件名为空"}), 400

    version = (request.form.get("version", "") or "1.0.0").strip()
    filename = file.filename

    # 保存文件
    file_path = FILES_DIR / filename
    file.save(str(file_path))
    file_size = file_path.stat().st_size

    db = get_db()
    db.execute(
        "INSERT INTO software_packages (filename, version, file_size) VALUES (?, ?, ?)",
        (filename, version, file_size)
    )
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('upload_package', ?)",
               (f"上传 {filename} v{version}",))
    db.commit()

    return jsonify({"code": 0, "msg": f"{filename} 上传成功"})


@app.route("/api/admin/packages/<int:pid>/toggle", methods=["POST"])
@admin_required
def api_admin_toggle_package(pid: int):
    db = get_db()
    row = db.execute("SELECT * FROM software_packages WHERE id = ?", (pid,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "文件不存在"}), 404

    new_state = 0 if row["is_active"] else 1
    db.execute("UPDATE software_packages SET is_active = ? WHERE id = ?", (new_state, pid))
    db.execute("INSERT INTO admin_log (action, detail) VALUES (?, ?)",
               ("toggle_package", f"{row['filename']} {'上架' if new_state else '下架'}"))
    db.commit()
    return jsonify({"code": 0, "msg": f"已{'上架' if new_state else '下架'}"})


@app.route("/api/admin/packages/<int:pid>", methods=["DELETE"])
@admin_required
def api_admin_delete_package(pid: int):
    db = get_db()
    row = db.execute("SELECT * FROM software_packages WHERE id = ?", (pid,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "文件不存在"}), 404

    # 删除物理文件
    file_path = FILES_DIR / row["filename"]
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass

    db.execute("DELETE FROM software_packages WHERE id = ?", (pid,))
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('delete_package', ?)",
               (f"删除 {row['filename']}",))
    db.commit()
    return jsonify({"code": 0, "msg": "已删除"})


# ============================================================
# 管理员 — 配置后台
# ============================================================
@app.route("/admin/settings")
@admin_required
def page_admin_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM server_config").fetchall()
    config = {r["key"]: r["value"] for r in rows}
    return render_template("settings.html", config=config)


@app.route("/api/admin/settings", methods=["GET"])
@admin_required
def api_get_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM server_config").fetchall()
    return jsonify({"code": 0, "data": {r["key"]: r["value"] for r in rows}})


@app.route("/api/admin/settings", methods=["POST"])
@admin_required
def api_save_settings():
    data = request.get_json(silent=True) or {}
    db = get_db()

    allowed_keys = {"payment_api_url", "video_upload_url", "software_package_path",
                    "hero_video_filename", "payment_qr_filename", "payment_instructions",
                    "order_expiry_minutes", "tunnel_enabled", "tunnel_backend",
                    "tunnel_ngrok_auth_token", "default_amount"}
    for key, value in data.items():
        if key in allowed_keys:
            db.execute(
                "INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                (key, str(value).strip())
            )

    db.execute("INSERT INTO admin_log (action, detail) VALUES ('update_settings', ?)",
               (f"更新了 {len(data)} 项配置",))
    db.commit()
    return jsonify({"code": 0, "msg": "配置已保存"})


# ============================================================
# 管理员 — 操作日志
# ============================================================
@app.route("/api/admin/logs", methods=["GET"])
@admin_required
def api_admin_logs():
    db = get_db()
    limit = int(request.args.get("limit", 50))
    rows = db.execute(
        "SELECT * FROM admin_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return jsonify({"code": 0, "data": [{
        "id": r["id"], "action": r["action"], "detail": r["detail"], "created_at": r["created_at"]
    } for r in rows]})


# ============================================================
# 隧道管理 API（管理员）
# ============================================================
@app.route("/api/admin/tunnel/status", methods=["GET"])
@admin_required
def api_admin_tunnel_status():
    """获取隧道状态"""
    tunnel = TunnelManager()
    return jsonify({
        "code": 0,
        "data": tunnel.get_status()
    })


@app.route("/api/admin/tunnel/toggle", methods=["POST"])
@admin_required
def api_admin_tunnel_toggle():
    """启用/禁用隧道"""
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", True))
    db = get_db()
    db.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
               ("tunnel_enabled", "1" if enabled else "0"))
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('tunnel_config', ?)",
               (f"隧道 {'启用' if enabled else '禁用'}",))
    db.commit()

    # 立即生效
    tunnel = TunnelManager()
    if enabled:
        url = tunnel.restart(port=5099)
        return jsonify({"code": 0, "msg": f"隧道已启用", "data": {"public_url": url}})
    else:
        tunnel.stop()
        return jsonify({"code": 0, "msg": "隧道已禁用"})


@app.route("/api/admin/tunnel/restart", methods=["POST"])
@admin_required
def api_admin_tunnel_restart():
    """强制重启隧道"""
    tunnel = TunnelManager()
    url = tunnel.restart(port=5099)
    return jsonify({
        "code": 0,
        "msg": "隧道已重启" if url else "隧道重启失败",
        "data": {"public_url": url}
    })


@app.route("/api/admin/tunnel/config", methods=["POST"])
@admin_required
def api_admin_tunnel_config():
    """更新隧道配置"""
    data = request.get_json(silent=True) or {}
    db = get_db()
    if "backend" in data:
        db.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                   ("tunnel_backend", str(data["backend"]).strip()))
    if "auth_token" in data:
        db.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                   ("tunnel_ngrok_auth_token", str(data["auth_token"]).strip()))
    db.execute("INSERT INTO admin_log (action, detail) VALUES ('tunnel_config', '更新隧道配置')")
    db.commit()
    return jsonify({"code": 0, "msg": "隧道配置已保存，重启隧道后生效"})


# ============================================================
# 订单管理 API（管理员）
# ============================================================
@app.route("/api/admin/order-stats", methods=["GET"])
@admin_required
def api_admin_order_stats():
    """订单统计"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    stats = {}
    for status in VALID_STATUSES:
        stats[status] = db.execute(
            "SELECT COUNT(*) as c FROM orders WHERE status=?", (status,)
        ).fetchone()["c"]
    stats["total"] = sum(stats.values())
    stats["today_orders"] = db.execute(
        "SELECT COUNT(*) as c FROM orders WHERE date(created_at)=?", (today,)
    ).fetchone()["c"]
    stats["today_revenue"] = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as c FROM orders WHERE status='paid' AND date(paid_at)=?", (today,)
    ).fetchone()["c"]
    stats["total_revenue"] = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as c FROM orders WHERE status='paid'"
    ).fetchone()["c"]
    return jsonify({"code": 0, "data": stats})


@app.route("/api/admin/orders", methods=["GET"])
@admin_required
def api_admin_orders():
    """订单列表（分页 + 筛选 + 搜索）"""
    db = get_db()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    status = request.args.get("status", "all")
    search = (request.args.get("search", "") or "").strip()

    where = "WHERE 1=1"
    params = []
    if status in VALID_STATUSES:
        where += " AND status = ?"
        params.append(status)
    if search:
        where += " AND (order_no LIKE ? OR fingerprint LIKE ? OR reg_code LIKE ? OR user_note LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])

    total = db.execute(f"SELECT COUNT(*) as c FROM orders {where}", params).fetchone()["c"]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM orders {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    orders = []
    for r in rows:
        fp = r["fingerprint"] or ""
        orders.append({
            "id": r["id"],
            "order_no": r["order_no"],
            "fingerprint": fp[:20] + "..." if len(fp) > 20 else fp,
            "fingerprint_full": fp,
            "reg_code": r["reg_code"],
            "amount": r["amount"],
            "payment_method": r["payment_method"],
            "status": r["status"],
            "status_label": get_status_label(r["status"]),
            "txn_id": r["txn_id"],
            "paid_at": r["paid_at"],
            "expired_at": r["expired_at"],
            "refunded_at": r["refunded_at"],
            "cancelled_at": r["cancelled_at"],
            "user_note": r["user_note"],
            "created_at": r["created_at"],
        })

    return jsonify({
        "code": 0,
        "data": {
            "orders": orders,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        }
    })


@app.route("/api/admin/orders/<order_no>", methods=["GET"])
@admin_required
def api_admin_order_detail(order_no: str):
    """订单详情"""
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "订单不存在"}), 404
    fp = row["fingerprint"] or ""
    return jsonify({
        "code": 0,
        "data": {
            "id": row["id"],
            "order_no": row["order_no"],
            "fingerprint": fp,
            "fingerprint_display": fp[:20] + "..." if len(fp) > 20 else fp,
            "reg_code": row["reg_code"],
            "amount": row["amount"],
            "payment_method": row["payment_method"],
            "status": row["status"],
            "status_label": get_status_label(row["status"]),
            "txn_id": row["txn_id"],
            "paid_at": row["paid_at"],
            "expired_at": row["expired_at"],
            "refunded_at": row["refunded_at"],
            "cancelled_at": row["cancelled_at"],
            "user_note": row["user_note"],
            "created_at": row["created_at"],
        }
    })


@app.route("/api/admin/orders/<order_no>/status", methods=["POST"])
@admin_required
def api_admin_order_update_status(order_no: str):
    """更新订单状态"""
    data = request.get_json(silent=True) or {}
    target = (data.get("status", "") or "").strip()

    if target not in VALID_STATUSES:
        return jsonify({"code": 1, "msg": f"无效状态: {target}"}), 400

    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "订单不存在"}), 404

    current = row["status"]
    if not validate_status_transition(current, target):
        return jsonify({"code": 1, "msg": f"不允许从 {get_status_label(current)} 转为 {get_status_label(target)}"}), 400

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if target == "paid":
        db.execute("UPDATE orders SET status='paid', paid_at=? WHERE order_no=?", (now_str, order_no))
        # 同步更新注册码
        if row["fingerprint"]:
            db.execute(
                "UPDATE registration_codes SET is_paid=1, paid_at=? WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
                (now_str, row["fingerprint"])
            )
    elif target == "refunded":
        db.execute("UPDATE orders SET status='refunded', refunded_at=? WHERE order_no=?", (now_str, order_no))
        if row["fingerprint"]:
            db.execute(
                "UPDATE registration_codes SET is_paid=0, paid_at=NULL WHERE fingerprint=?",
                (row["fingerprint"],)
            )
    elif target == "cancelled":
        db.execute("UPDATE orders SET status='cancelled', cancelled_at=? WHERE order_no=?", (now_str, order_no))
    elif target == "expired":
        db.execute("UPDATE orders SET status='expired' WHERE order_no=?", (order_no,))
    elif target == "pending":
        db.execute("UPDATE orders SET status='pending', paid_at=NULL, refunded_at=NULL, cancelled_at=NULL WHERE order_no=?",
                   (order_no,))

    db.execute("INSERT INTO admin_log (action, detail) VALUES ('order_status_update', ?)",
               (f"订单 {order_no}: {get_status_label(current)} → {get_status_label(target)}",))
    db.commit()

    return jsonify({"code": 0, "msg": f"订单状态已更新为 {get_status_label(target)}"})


@app.route("/api/admin/orders/expire-stale", methods=["POST"])
@admin_required
def api_admin_expire_stale_orders():
    """手动触发过期处理"""
    db = get_db()
    count = expire_stale_orders(db)
    if count > 0:
        db.execute("INSERT INTO admin_log (action, detail) VALUES ('orders_expired', ?)",
                   (f"过期处理: {count} 笔订单已过期",))
        db.commit()
    return jsonify({"code": 0, "msg": f"已过期 {count} 笔订单", "data": {"expired_count": count}})


# ============================================================
# 公开订单查询 API
# ============================================================
@app.route("/api/order/<order_no>/status", methods=["GET"])
def api_public_order_status(order_no: str):
    """公开查询订单状态（无需登录）"""
    db = get_db()
    # 自动过期
    expire_stale_orders(db)
    row = db.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "订单不存在"}), 404

    # 关联查询注册码
    reg_code = row["reg_code"]
    if not reg_code and row["fingerprint"]:
        rc = db.execute(
            "SELECT reg_code FROM registration_codes WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
            (row["fingerprint"],)
        ).fetchone()
        if rc:
            reg_code = rc["reg_code"]

    return jsonify({
        "code": 0,
        "data": {
            "order_no": row["order_no"],
            "amount": row["amount"],
            "status": row["status"],
            "status_label": get_status_label(row["status"]),
            "payment_method": row["payment_method"],
            "reg_code": reg_code,
            "created_at": row["created_at"],
            "paid_at": row["paid_at"],
            "expired_at": row["expired_at"],
        }
    })


# ============================================================
# 启动入口
# ============================================================
def main():
    print("=" * 60)
    print("  🌐 ClassTrack.com — Web 服务 v2.0")
    if getattr(sys, 'frozen', False):
        print(f"  📦 运行模式: EXE (PyInstaller)")
        print(f"  📂 数据目录: {DATA_DIR}")
    print("  用户页面: http://localhost:5099")
    print("  管理后台: 请运行 python admin_app.py (PyQt6 桌面端)")
    print("=" * 60)

    try:
        init_db()
        print(f"  ✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:
        print(f"  ❌ 数据库初始化失败: {e}")
        sys.exit(1)

    # ---- 隧道启动 ----
    tunnel = TunnelManager()
    tunnel.set_db_path(DB_PATH)
    if tunnel.is_enabled():
        print("  🌐 正在启动内网穿透...")
        url = tunnel.start(port=5099)
        if url:
            print(f"  🌐 公网地址: {url}")
            print(f"  💡 其他人可以通过上面的公网地址访问本服务")
        else:
            print(f"  ⚠️ 内网穿透启动失败，仅局域网可用")
            print(f"  💡 请检查管理后台 → 系统设置 → 隧道配置")
    else:
        print(f"  🔒 内网穿透未启用，仅局域网可用")

    # 注册退出清理
    atexit.register(lambda: tunnel.stop())

    print(f"  🔑 管理密码: {ADMIN_PASSWORD}")
    print(f"  📁 文件存储: {FILES_DIR}")
    print(f"  📋 按 Ctrl+C 停止服务")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5099, debug=True, threaded=True)


if __name__ == "__main__":
    main()
