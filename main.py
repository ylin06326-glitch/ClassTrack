#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack - 班级作业分组管理系统 v1.1
======================================
面向中小学教师的班级作业分组管理Windows桌面工具
技术栈: Python Flask + SQLite + HTML5/CSS3/JS

新增功能:
- 多班级切换管理
- 纯文字导入学生名单
- 可视化数据图表分析API
- 催交作业通知
- PyInstaller 打包路径适配
- 程序退出API

所有数据仅本地存储，保护学生隐私
"""

import os
import sys
import io
import json
import base64
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import qrcode
import requests
from flask import (
    Flask, request, jsonify, send_file, render_template,
    g as flask_g, Response
)
from werkzeug.utils import secure_filename

# ---- 激活校验模块 (v1.5 新增，纯离线，不侵入原有代码) ----
try:
    from activation.license_manager import (
        verify_activation,
        save_activation_file,
        export_fingerprint,
        decode_fingerprint,
    )
    from activation.hardware_id import get_full_hardware_fingerprint
    _ACTIVATION_AVAILABLE = True
except Exception:
    import traceback
    traceback.print_exc()
    _ACTIVATION_AVAILABLE = False

# ============================================================
# PyInstaller 路径适配
# ============================================================
if getattr(sys, 'frozen', False):
    _ROOT = Path(sys._MEIPASS)
else:
    _ROOT = Path(__file__).resolve().parent

BASE_DIR = _ROOT

# data 目录位置（打包版: %APPDATA%\ClassTrack，自动迁移旧版 exe 旁 data）
# 注意: 目录创建放到 main() 里做，避免 import 阶段因无权限直接崩溃
from app_paths import get_data_dir, get_legacy_data_dir, migrate_legacy_data

if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).resolve().parent
else:
    _EXE_DIR = _ROOT
DATA_DIR = get_data_dir(_EXE_DIR)
LEGACY_DATA_DIR = get_legacy_data_dir(_EXE_DIR)

DB_PATH = DATA_DIR / "classtrack.db"
UPLOAD_DIR = DATA_DIR / "uploads"
TEMP_DIR = DATA_DIR / "temp"


def _fatal(message: str):
    """启动阶段致命错误：控制台打印 + 打包版弹窗提示"""
    print(f"  ❌ {message}")
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "ClassTrack 启动失败", 0x10)
        except Exception:
            pass

# 分组颜色主题（柔和马卡龙色系）
GROUP_COLORS = [
    "#7EB5D6", "#E8A0BF", "#A8D5BA", "#F4C97E",
    "#C4B5D6", "#F0B8A0", "#8EC8C0", "#D4A8C8",
    "#9DC8E0", "#F2C8DA", "#B8D8C8", "#F8DCA0",
]

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"))
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True


# ============================================================
# 数据库管理
# ============================================================
def get_db():
    if "db" not in flask_g:
        # busy_timeout: 并发写时等待最多 5 秒，避免 database is locked
        flask_g.db = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES, timeout=5)
        flask_g.db.row_factory = sqlite3.Row
        flask_g.db.execute("PRAGMA busy_timeout=5000")
        flask_g.db.execute("PRAGMA foreign_keys=ON")
    return flask_g.db


@app.teardown_appcontext
def close_db(error):
    db = flask_g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库 + 自动迁移"""
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    # WAL 只在初始化时设置一次（每个连接都执行 journal_mode 会在并发下抢写锁）
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")

    # 基础表结构（v2.2: homework_types 全局化）
    db.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_id INTEGER DEFAULT 1,
            group_id INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS groups_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_id INTEGER DEFAULT 1,
            color TEXT DEFAULT '#7EB5D6',
            sort_order INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            grade TEXT NOT NULL DEFAULT 'X',
            tag TEXT DEFAULT '',
            homework_type_id INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(student_id, date, homework_type_id)
        );

        CREATE TABLE IF NOT EXISTS homework_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS exam_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL DEFAULT 1,
            date TEXT NOT NULL,
            exam_name TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL,
            total_score REAL NOT NULL DEFAULT 100,
            grade TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(student_id, exam_name, date)
        );

        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS mobile_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT NOT NULL,
            scanned_at TEXT DEFAULT (datetime('now','localtime')),
            processed INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_homework_date ON homework(date);
        CREATE INDEX IF NOT EXISTS idx_homework_student ON homework(student_id);
        CREATE INDEX IF NOT EXISTS idx_exam_scores_student ON exam_scores(student_id);
        CREATE INDEX IF NOT EXISTS idx_exam_scores_class ON exam_scores(class_id);
        CREATE INDEX IF NOT EXISTS idx_students_group ON students(group_id);
        CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);
        CREATE INDEX IF NOT EXISTS idx_groups_class ON groups_info(class_id);
    """)

    # ---- 自动迁移：兼容 v1.0 数据库 ----
    cols = [r[1] for r in db.execute("PRAGMA table_info(students)").fetchall()]
    if "class_id" not in cols:
        db.execute("ALTER TABLE students ADD COLUMN class_id INTEGER DEFAULT 1")
    cols_g = [r[1] for r in db.execute("PRAGMA table_info(groups_info)").fetchall()]
    if "class_id" not in cols_g:
        db.execute("ALTER TABLE groups_info ADD COLUMN class_id INTEGER DEFAULT 1")

    # v1.2: 学号字段
    cols_s = [r[1] for r in db.execute("PRAGMA table_info(students)").fetchall()]
    if "student_code" not in cols_s:
        db.execute("ALTER TABLE students ADD COLUMN student_code TEXT DEFAULT ''")

    # v2.1: 数据结构扁平化 —— 移除 homework_type_id，合并重复记录
    # 仅对 v2.1 之前的旧数据库生效（v2.2+ 已用新 schema，跳过）
    schema_ver = _get_schema_version(db)
    cols_hw = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "homework_type_id" in cols_hw and schema_ver < "2.2":
        # 合并同一 (student_id, date) 的多条记录（不同 homework_type），保留最新
        db.execute("PRAGMA foreign_keys=OFF")
        db.executescript("""
            CREATE TABLE homework_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                grade TEXT NOT NULL DEFAULT 'X',
                tag TEXT DEFAULT '',
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(student_id, date)
            );
            INSERT INTO homework_new (student_id, date, grade, updated_at)
                SELECT student_id, date, grade, MAX(updated_at)
                FROM homework
                GROUP BY student_id, date;
            DROP TABLE homework;
            ALTER TABLE homework_new RENAME TO homework;
        """)
        db.execute("PRAGMA foreign_keys=ON")

    # 确保 homework.tag 列存在（新建或迁移后的表都应有）
    cols_hw2 = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "tag" not in cols_hw2:
        db.execute("ALTER TABLE homework ADD COLUMN tag TEXT DEFAULT ''")

    # v2.1: homework_types 表（如果不存在则创建，兼容旧数据库；v2.2+ 跳过）
    if schema_ver < "2.2":
        db.execute("""
            CREATE TABLE IF NOT EXISTS homework_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_id INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        """)

    # 给 homework 表添加 homework_type_id 列（如果不存在，v2.2+ 已包含在初始建表）
    cols_hw3 = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "homework_type_id" not in cols_hw3:
        db.execute("ALTER TABLE homework ADD COLUMN homework_type_id INTEGER DEFAULT 0")

    # ---- v2.2 自动迁移：作业种类全局化 + 支持多类型同日记录 ----
    _migrate_v2_2(db)

    # 确保至少有一个全局作业种类
    type_count = db.execute("SELECT COUNT(*) FROM homework_types").fetchone()[0]
    if type_count == 0:
        db.execute("INSERT INTO homework_types (name, sort_order) VALUES (?, ?)",
                   ("默认作业", 0))

    # 确保至少有一个默认班级
    class_count = db.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    if class_count == 0:
        db.execute("INSERT INTO classes (name) VALUES (?)", ("我的班级",))
        db.execute("UPDATE students SET class_id = 1")
        db.execute("UPDATE groups_info SET class_id = 1")

    # 设置默认活跃班级
    active = db.execute(
        "SELECT value FROM app_config WHERE key='active_class_id'"
    ).fetchone()
    if not active:
        db.execute("INSERT INTO app_config (key,value) VALUES ('active_class_id','1')")

    db.commit()
    db.close()


def _get_schema_version(db):
    """读取当前数据库 schema 版本号"""
    try:
        row = db.execute(
            "SELECT value FROM app_config WHERE key='schema_version'"
        ).fetchone()
        return row["value"] if row else "0"
    except Exception:
        return "0"


def _migrate_v2_2(db):
    """v2.2 迁移：作业种类全局化 + homework 支持多类型同日记录"""
    # 检查是否需要迁移（homework_types 表是否有 class_id 列）
    try:
        cols_ht = [r[1] for r in db.execute("PRAGMA table_info(homework_types)").fetchall()]
    except Exception:
        return  # 表不存在，初始创建会处理
    types_migrated = "class_id" not in cols_ht

    db.execute("PRAGMA foreign_keys=OFF")
    try:
        if not types_migrated:
            print("[v2.2] 开始迁移：作业种类全局化...")

            # Step 1: 合并同名作业种类（保留最小 id）
            all_types = db.execute("SELECT id, name FROM homework_types ORDER BY id").fetchall()
            name_to_canonical = {}
            duplicates = []
            for ht in all_types:
                name_key = ht["name"].strip()
                if name_key in name_to_canonical:
                    duplicates.append((ht["id"], name_to_canonical[name_key]))
                else:
                    name_to_canonical[name_key] = ht["id"]

            for dup_id, canon_id in duplicates:
                db.execute("UPDATE homework SET homework_type_id=? WHERE homework_type_id=?",
                           (canon_id, dup_id))
            if duplicates:
                print(f"[v2.2] 合并了 {len(duplicates)} 个重复作业种类")

            # Step 2: 重建 homework_types 表（移除 class_id）
            db.executescript("""
                CREATE TABLE homework_types_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );
                INSERT INTO homework_types_new (id, name, sort_order, created_at)
                    SELECT MIN(id), name, MIN(sort_order), MIN(created_at)
                    FROM homework_types
                    GROUP BY LOWER(TRIM(name));
                DROP TABLE homework_types;
                ALTER TABLE homework_types_new RENAME TO homework_types;
            """)

        # Step 3: 修正 homework UNIQUE 约束（加入 homework_type_id）。
        # 注意不能用 sqlite_master.sql 判断——ALTER TABLE ADD COLUMN 会把列名
        # 追加进存储的 SQL，但 UNIQUE 约束仍是旧的，导致新库/旧库都可能带着
        # 错误的 UNIQUE(student_id, date) 逃过检测。改用 PRAGMA index_list
        # 检查真实约束；且 Step 3 独立于 homework_types 状态执行（历史版本
        # 存在「种类已迁移但约束未修复」的库，需单独补救）。
        need_rebuild = True
        for ix in db.execute("PRAGMA index_list(homework)").fetchall():
            if ix["unique"]:
                cols = [c["name"] for c in db.execute(
                    "PRAGMA index_info(%s)" % ix["name"]).fetchall()]
                if set(cols) == {"student_id", "date", "homework_type_id"}:
                    need_rebuild = False
                    break
        if need_rebuild:
            db.executescript("""
                CREATE TABLE homework_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    grade TEXT NOT NULL DEFAULT 'X',
                    tag TEXT DEFAULT '',
                    homework_type_id INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE(student_id, date, homework_type_id)
                );
                INSERT INTO homework_new (student_id, date, grade, tag, homework_type_id, updated_at)
                    SELECT student_id, date, grade, tag, homework_type_id, MAX(updated_at)
                    FROM homework
                    GROUP BY student_id, date, homework_type_id;
                DROP TABLE homework;
                ALTER TABLE homework_new RENAME TO homework;
            """)
            # 重建索引
            db.execute("CREATE INDEX IF NOT EXISTS idx_homework_date ON homework(date)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_homework_student ON homework(student_id)")
            print("[v2.2] homework UNIQUE 约束已更新为 (student_id, date, homework_type_id)")
    finally:
        db.execute("PRAGMA foreign_keys=ON")

    # 记录迁移版本
    db.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES ('schema_version', '2.2')")
    print("[v2.2] 迁移完成")


# ============================================================
# 辅助函数
# ============================================================
def get_active_class_id() -> int:
    """获取当前活跃班级ID"""
    db = get_db()
    row = db.execute(
        "SELECT value FROM app_config WHERE key='active_class_id'"
    ).fetchone()
    return int(row["value"]) if row else 1


def get_class_id_from_request() -> int:
    """从请求参数或默认值获取class_id"""
    cid = request.args.get("class_id") or request.get_json(silent=True) or {}
    if isinstance(cid, dict):
        cid = cid.get("class_id", 0)
    cid = int(cid) if cid else 0
    return cid if cid > 0 else get_active_class_id()


def parse_excel_students(file_path: str) -> list:
    """解析Excel文件中的学生名单，返回 [{name, code}]"""
    file_ext = Path(file_path).suffix.lower()
    try:
        if file_ext == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
        elif file_ext == ".xls":
            df = pd.read_excel(file_path, engine="xlrd", dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)
    except Exception:
        df = pd.read_excel(file_path, dtype=str, engine=None)
    if df.empty:
        return []

    # 查找姓名列
    name_col = None
    for col in df.columns:
        if any(kw in str(col).lower().strip() for kw in
               ["姓名", "名字", "学生", "name", "学生姓名"]):
            name_col = col
            break
    if name_col is None:
        name_col = df.columns[0]

    # 查找学号列
    code_col = None
    for col in df.columns:
        if any(kw in str(col).lower().strip() for kw in
               ["学号", "编号", "id", "code", "工号"]):
            code_col = col
            break
    # 如果没找到命名列，检查第一列是否全是数字（自动识别为学号）
    if code_col is None and len(df.columns) >= 2:
        first_col = df.columns[0]
        try:
            numeric_count = 0
            total = 0
            for v in df[first_col]:
                vs = str(v).strip() if pd.notna(v) else ""
                if vs and vs not in ("nan", "None", ""):
                    total += 1
                    if vs.isdigit():
                        numeric_count += 1
            # 如果超过80%是纯数字，认为是学号列
            if total > 0 and numeric_count / total >= 0.8:
                code_col = first_col
        except Exception:
            pass

    results = []
    seen_names = set()
    for idx, row in df.iterrows():
        vs = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        if not vs or vs in ("nan", "None", ""):
            continue
        if vs in ("姓名", "名字", "学生姓名", "学生", "name", "序号", "编号"):
            continue
        if vs in seen_names:
            continue
        seen_names.add(vs)
        code = ""
        if code_col and pd.notna(row[code_col]):
            code = str(row[code_col]).strip()
            if code in ("nan", "None"):
                code = ""
        results.append({"name": vs, "code": code})
    return results


def parse_text_names(text: str) -> list:
    """解析纯文字学生名单（仅用作后端兜底——前端已解析，正常不应走此路径）
    按换行/逗号/顿号分割，但不用空格分割（避免把"001 张三"拆成两个人）"""
    import re
    # 只按换行、逗号、顿号、中文逗号分割，不按空格分割
    parts = re.split(r'[\n\r,，、]+', text.strip())
    names = []
    for p in parts:
        p = p.strip()
        if p and p not in names:
            names.append(p)
    return names


def get_group_color(group_index: int) -> str:
    return GROUP_COLORS[group_index % len(GROUP_COLORS)]


def grade_label(grade: str) -> str:
    return {"A": "A", "B": "B", "C": "C", "L": "请假", "X": "未交"}.get(grade, "未交")


# ============================================================
# 班级管理 API
# ============================================================
@app.route("/api/classes", methods=["GET"])
def api_get_classes():
    db = get_db()
    rows = db.execute("SELECT * FROM classes ORDER BY id").fetchall()
    active_id = get_active_class_id()
    return jsonify({
        "code": 0,
        "data": [{"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
                 for r in rows],
        "active_id": active_id
    })


@app.route("/api/classes", methods=["POST"])
def api_create_class():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"code": 1, "msg": "班级名称不能为空"}), 400
    db = get_db()
    db.execute("INSERT INTO classes (name) VALUES (?)", (name,))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({"code": 0, "msg": f"班级「{name}」已创建", "data": {"id": new_id}})


@app.route("/api/classes/<int:cid>", methods=["PUT"])
def api_rename_class(cid: int):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"code": 1, "msg": "名称不能为空"}), 400
    db = get_db()
    db.execute("UPDATE classes SET name=? WHERE id=?", (name, cid))
    db.commit()
    return jsonify({"code": 0, "msg": "已重命名"})


@app.route("/api/classes/<int:cid>", methods=["DELETE"])
def api_delete_class(cid: int):
    db = get_db()
    # 至少保留一个班级
    count = db.execute("SELECT COUNT(*) as c FROM classes").fetchone()["c"]
    if count <= 1:
        return jsonify({"code": 1, "msg": "至少保留一个班级"}), 400
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
        db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)",
                   (str(first["id"]),))
    db.commit()
    return jsonify({"code": 0, "msg": "班级已删除"})


@app.route("/api/classes/<int:cid>/activate", methods=["POST"])
def api_activate_class(cid: int):
    db = get_db()
    cls = db.execute("SELECT id FROM classes WHERE id=?", (cid,)).fetchone()
    if not cls:
        return jsonify({"code": 1, "msg": "班级不存在"}), 404
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)",
               (str(cid),))
    db.commit()
    return jsonify({"code": 0, "msg": "已切换班级"})


# ============================================================
# 学生管理 API (带 class_id 过滤)
# ============================================================
@app.route("/api/students", methods=["GET"])
def api_get_students():
    cid = get_class_id_from_request()
    db = get_db()
    rows = db.execute(
        "SELECT s.*, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id AND g.class_id = ? "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order, s.id",
        (cid, cid)
    ).fetchall()
    students = [{
        "id": r["id"], "name": r["name"], "student_code": r["student_code"] or "",
        "group_id": r["group_id"] or 0,
        "group_name": r["group_name"] or "", "group_color": r["group_color"] or "",
        "sort_order": r["sort_order"], "class_id": r["class_id"]
    } for r in rows]
    return jsonify({"code": 0, "data": students})


@app.route("/api/students/<int:sid>", methods=["DELETE"])
def api_delete_student(sid: int):
    db = get_db()
    db.execute("DELETE FROM students WHERE id = ?", (sid,))
    db.commit()
    return jsonify({"code": 0, "msg": "已删除"})


@app.route("/api/students/clear", methods=["DELETE"])
def api_clear_students():
    cid = get_class_id_from_request()
    db = get_db()
    student_ids = [r[0] for r in db.execute(
        "SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
    for sid in student_ids:
        db.execute("DELETE FROM homework WHERE student_id=?", (sid,))
    db.execute("DELETE FROM students WHERE class_id=?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id=?", (cid,))
    db.commit()
    return jsonify({"code": 0, "msg": "已清空当前班级数据"})


# ============================================================
# 导入 API (Excel + 纯文字)
# ============================================================
@app.route("/api/students/batch-delete", methods=["POST"])
def api_batch_delete_students():
    """批量删除学生及其作业记录"""
    data = request.get_json() or {}
    student_ids = data.get("student_ids", [])
    if not student_ids:
        return jsonify({"code": 1, "msg": "未选择学生"}), 400
    if len(student_ids) > 200:
        return jsonify({"code": 1, "msg": "单次最多删除200人"}), 400
    db = get_db()
    placeholders = ",".join("?" * len(student_ids))
    db.execute(f"DELETE FROM homework WHERE student_id IN ({placeholders})", student_ids)
    db.execute(f"DELETE FROM students WHERE id IN ({placeholders})", student_ids)
    db.commit()
    return jsonify({"code": 0, "msg": f"已删除 {len(student_ids)} 名学生"})


@app.route("/api/students/clear-unassigned", methods=["POST"])
def api_clear_unassigned():
    """清除当前班级所有未分组学生"""
    cid = get_class_id_from_request()
    db = get_db()
    unassigned = db.execute(
        "SELECT id FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=?",
        (cid,)
    ).fetchall()
    if not unassigned:
        return jsonify({"code": 0, "msg": "没有未分组的学生"})
    ids = [r[0] for r in unassigned]
    placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM homework WHERE student_id IN ({placeholders})", ids)
    db.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
    db.commit()
    return jsonify({"code": 0, "msg": f"已清除 {len(ids)} 名未分组学生", "data": {"count": len(ids)}})


@app.route("/api/import", methods=["POST"])
def api_import_students():
    cid = get_class_id_from_request()
    if "file" not in request.files:
        return jsonify({"code": 1, "msg": "未选择文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"code": 1, "msg": "文件名为空"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return jsonify({"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}), 400
    filename = secure_filename(file.filename)
    file_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(str(file_path))
    try:
        records = parse_excel_students(str(file_path))
    except Exception as e:
        return jsonify({"code": 1, "msg": f"解析Excel失败: {str(e)}"}), 400
    if not records:
        return jsonify({"code": 1, "msg": "未在表格中找到有效学生姓名"}), 400
    if len(records) > 200:
        return jsonify({"code": 1, "msg": f"学生数量({len(records)})超过上限(200人)"}), 400
    db = get_db()
    imported, skipped = 0, 0
    for r in records:
        try:
            db.execute("INSERT INTO students (name, student_code, class_id) VALUES (?, ?, ?)",
                       (r["name"], r["code"], cid))
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    db.commit()
    try:
        file_path.unlink()
    except Exception:
        pass
    return jsonify({
        "code": 0,
        "msg": f"导入完成：新增 {imported} 人，跳过重复 {skipped} 人",
        "data": {"imported": imported, "skipped": skipped}
    })


@app.route("/api/import/text", methods=["POST"])
def api_import_text():
    """纯文字导入学生名单（v1.2: 支持学号识别）"""
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    text = data.get("text", "")
    # v1.2: 前端已解析学号，直接使用 parsed_records
    parsed_records = data.get("parsed_records", None)
    if parsed_records:
        # 使用前端解析结果 [{name, code}]
        records = [(r.get("name", "").strip(), r.get("code", "").strip()) for r in parsed_records]
        records = [(n, c) for n, c in records if n]
    else:
        # 兼容旧版：后端自行解析姓名
        names = parse_text_names(text)
        records = [(n, "") for n in names if n]
    if not records:
        return jsonify({"code": 1, "msg": "未能解析出有效姓名"}), 400
    if len(records) > 200:
        return jsonify({"code": 1, "msg": f"学生数量({len(records)})超过上限(200人)"}), 400
    db = get_db()
    imported, skipped = 0, 0
    for name, code in records:
        try:
            db.execute("INSERT INTO students (name, student_code, class_id) VALUES (?, ?, ?)",
                       (name, code, cid))
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1
    db.commit()
    return jsonify({
        "code": 0,
        "msg": f"导入完成：新增 {imported} 人，跳过重复 {skipped} 人",
        "data": {"imported": imported, "skipped": skipped, "parsed": [n for n, _ in records]}
    })


# ============================================================
# 分组管理 API (带 class_id 过滤)
# ============================================================
@app.route("/api/groups", methods=["GET"])
def api_get_groups():
    cid = get_class_id_from_request()
    db = get_db()
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
        "AND class_id = ? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    return jsonify({
        "code": 0,
        "data": {
            "groups": result,
            "unassigned": [{"id": s["id"], "name": s["name"]} for s in unassigned]
        }
    })


def _class_is_locked(db, cid: int) -> bool:
    """当前班级的分组是否已锁定"""
    row = db.execute(
        "SELECT 1 FROM groups_info WHERE class_id=? AND is_locked=1 LIMIT 1", (cid,)
    ).fetchone()
    return row is not None


def _lock_error():
    return jsonify({"code": 1, "msg": "分组已锁定，请先点击「解锁分组」后再调整"}), 400


@app.route("/api/groups/init", methods=["POST"])
def api_init_groups():
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    count = int(data.get("count", 6))
    if count < 2 or count > 20:
        return jsonify({"code": 1, "msg": "分组数量需在2-20之间"}), 400
    db = get_db()
    if _class_is_locked(db, cid):
        return _lock_error()
    existing = db.execute(
        "SELECT id FROM groups_info WHERE class_id = ? ORDER BY sort_order", (cid,)
    ).fetchall()
    existing_ids = [r["id"] for r in existing]
    if len(existing) > count:
        for gid in existing_ids[count:]:
            db.execute("UPDATE students SET group_id = 0 WHERE group_id = ? AND class_id = ?",
                       (gid, cid))
            db.execute("DELETE FROM groups_info WHERE id = ?", (gid,))
        existing_ids = existing_ids[:count]
    for i in range(count):
        group_name = f"第{i+1}组"
        color = get_group_color(i)
        if i < len(existing_ids):
            db.execute("UPDATE groups_info SET name=?, color=?, sort_order=? WHERE id=?",
                       (group_name, color, i, existing_ids[i]))
        else:
            db.execute(
                "INSERT INTO groups_info (name, color, sort_order, class_id) VALUES (?,?,?,?)",
                (group_name, color, i, cid))
    db.commit()
    return jsonify({"code": 0, "msg": f"已设置为 {count} 个分组"})


@app.route("/api/groups/save", methods=["POST"])
def api_save_groups():
    """
    一次性保存整张分组表（单事务，替代前端并发发多个 batch-move 请求）。
    请求体: { groups: [{group_id: 0, student_ids: [1,2,3]}, ...] }
    group_id=0 表示未分组名单池。
    """
    cid = get_class_id_from_request()
    data = request.get_json(silent=True) or {}
    groups = data.get("groups", None)
    if not isinstance(groups, list):
        return jsonify({"code": 1, "msg": "参数格式错误"}), 400
    db = get_db()
    if _class_is_locked(db, cid):
        return _lock_error()
    # 校验所有非零 group_id 都属于当前班级
    gids = {int(g.get("group_id", 0) or 0) for g in groups}
    gids.discard(0)
    if gids:
        placeholders = ",".join("?" * len(gids))
        rows = db.execute(
            f"SELECT id FROM groups_info WHERE class_id=? AND id IN ({placeholders})",
            [cid] + list(gids)).fetchall()
        found = {r["id"] for r in rows}
        missing = gids - found
        if missing:
            return jsonify({"code": 1, "msg": f"分组不存在: {sorted(missing)}"}), 404
    moved = 0
    try:
        for g in groups:
            gid = int(g.get("group_id", 0) or 0)
            sids = [int(s) for s in (g.get("student_ids") or [])]
            if not sids:
                continue
            placeholders = ",".join("?" * len(sids))
            db.execute(
                f"UPDATE students SET group_id=? WHERE id IN ({placeholders}) AND class_id=?",
                [gid] + sids + [cid])
            moved += len(sids)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify({"code": 0, "msg": f"分组已保存（{moved} 名学生）"})


@app.route("/api/students/<int:sid>/move", methods=["PUT"])
def api_move_student(sid: int):
    data = request.get_json() or {}
    group_id = int(data.get("group_id", 0))
    db = get_db()
    student = db.execute("SELECT id, class_id FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404
    if _class_is_locked(db, student["class_id"]):
        return _lock_error()
    if group_id > 0:
        group = db.execute("SELECT id FROM groups_info WHERE id = ?", (group_id,)).fetchone()
        if not group:
            return jsonify({"code": 1, "msg": "分组不存在"}), 404
    db.execute("UPDATE students SET group_id = ? WHERE id = ?", (group_id, sid))
    db.commit()
    return jsonify({"code": 0, "msg": "移动成功"})


@app.route("/api/students/batch-move", methods=["PUT"])
def api_batch_move_students():
    """批量移动学生到指定分组"""
    data = request.get_json() or {}
    student_ids = data.get("student_ids", [])
    group_id = int(data.get("group_id", 0))
    if not student_ids:
        return jsonify({"code": 1, "msg": "未选择学生"}), 400
    db = get_db()
    if _class_is_locked(db, get_class_id_from_request()):
        return _lock_error()
    if group_id > 0:
        group = db.execute("SELECT id FROM groups_info WHERE id = ?", (group_id,)).fetchone()
        if not group:
            return jsonify({"code": 1, "msg": "分组不存在"}), 404
    placeholders = ",".join("?" * len(student_ids))
    db.execute(
        f"UPDATE students SET group_id = ? WHERE id IN ({placeholders})",
        [group_id] + student_ids)
    db.commit()
    return jsonify({"code": 0, "msg": f"已移动 {len(student_ids)} 名学生"})


@app.route("/api/groups/lock", methods=["POST"])
def api_lock_groups():
    cid = get_class_id_from_request()
    db = get_db()
    db.execute("UPDATE groups_info SET is_locked = 1 WHERE class_id = ?", (cid,))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('last_lock_time',?)", (now,))
    db.commit()
    return jsonify({"code": 0, "msg": "分组已锁定", "data": {"lock_time": now}})


@app.route("/api/groups/unlock", methods=["POST"])
def api_unlock_groups():
    """解锁分组，允许继续调整"""
    cid = get_class_id_from_request()
    db = get_db()
    db.execute("UPDATE groups_info SET is_locked = 0 WHERE class_id = ?", (cid,))
    db.commit()
    return jsonify({"code": 0, "msg": "分组已解锁，可以自由调整"})


@app.route("/api/groups/reset", methods=["POST"])
def api_reset_groups():
    cid = get_class_id_from_request()
    db = get_db()
    if _class_is_locked(db, cid):
        return _lock_error()
    db.execute("UPDATE students SET group_id = 0 WHERE class_id = ?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id = ?", (cid,))
    db.commit()
    return jsonify({"code": 0, "msg": "分组已重置"})


# ============================================================
# 作业登记 API (带 class_id 过滤)
# ============================================================
@app.route("/api/homework", methods=["GET"])
def api_get_homework():
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()
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
    records = {}
    for r in rows:
        records[r["student_id"]] = {
            "id": r["id"], "student_id": r["student_id"],
            "student_name": r["student_name"], "date": r["date"],
            "grade": r["grade"], "group_id": r["group_id"],
            "group_name": r["group_name"], "group_color": r["group_color"],
        }
    return jsonify({"code": 0, "data": records})


@app.route("/api/homework", methods=["POST"])
def api_save_homework():
    data = request.get_json() or {}
    student_id = int(data.get("student_id", 0))
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    grade = data.get("grade", "X")
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if grade not in ("A", "B", "C", "L", "X"):
        return jsonify({"code": 1, "msg": "无效等级"}), 400
    db = get_db()
    student = db.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404
    db.execute("""
        INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET
            grade = excluded.grade,
            updated_at = datetime('now','localtime')
    """, (student_id, date, grade, hw_type_id))
    db.commit()
    return jsonify({"code": 0, "msg": "登记成功"})


@app.route("/api/homework/batch", methods=["POST"])
def api_batch_homework():
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    grade = data.get("grade", "X")
    group_id = int(data.get("group_id", 0))
    student_ids = data.get("student_ids", [])
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    if grade not in ("A", "B", "C", "L", "X"):
        return jsonify({"code": 1, "msg": "无效等级"}), 400
    db = get_db()
    if student_ids:
        placeholders = ",".join("?" * len(student_ids))
        db.execute(f"DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN ({placeholders})",
                   [date, hw_type_id] + student_ids)
        db.execute(f"""INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE id IN ({placeholders})""",
                   [date, grade, hw_type_id] + student_ids)
    elif group_id > 0:
        db.execute("DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
                   "(SELECT id FROM students WHERE group_id=? AND class_id=?)",
                   (date, hw_type_id, group_id, cid))
        db.execute("""INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE group_id=? AND class_id=?""",
                   (date, grade, hw_type_id, group_id, cid))
    else:
        db.execute("DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
                   "(SELECT id FROM students WHERE class_id=?)", (date, hw_type_id, cid))
        db.execute("""INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
                   SELECT id, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE class_id=?""", (date, grade, hw_type_id, cid))
    db.commit()
    return jsonify({"code": 0, "msg": "批量登记成功"})


@app.route("/api/homework/range", methods=["GET"])
def api_get_homework_range():
    cid = get_class_id_from_request()
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    if not start or not end:
        return jsonify({"code": 1, "msg": "请指定起始和结束日期"}), 400
    db = get_db()
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
    return jsonify({"code": 0, "data": records, "total": len(records)})


@app.route("/api/homework/missing", methods=["GET"])
def api_get_missing_homework():
    """获取指定日期未交作业的学生列表（催交用）"""
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()
    # 获取该班级所有学生
    all_students = db.execute(
        "SELECT s.id, s.name, s.group_id, g.name as group_name "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order",
        (cid,)
    ).fetchall()
    # 获取已有记录（非X的）
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
    return jsonify({"code": 0, "data": missing, "total": len(missing)})


# ============================================================
# 作业种类管理 API
# ============================================================
@app.route("/api/homework-types", methods=["GET"])
def api_get_homework_types():
    """获取所有作业种类（全局，不区分班级）"""
    db = get_db()
    rows = db.execute(
        "SELECT id, name, sort_order FROM homework_types ORDER BY sort_order, id"
    ).fetchall()
    types = [{"id": r["id"], "name": r["name"], "sort_order": r["sort_order"]} for r in rows]
    return jsonify({"code": 0, "data": types})


@app.route("/api/homework-types", methods=["POST"])
def api_create_homework_type():
    """创建新的作业种类（全局）"""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"code": 1, "msg": "名称不能为空"}), 400
    db = get_db()
    # 获取最大 sort_order
    max_sort = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) as m FROM homework_types"
    ).fetchone()["m"]
    db.execute(
        "INSERT INTO homework_types (name, sort_order) VALUES (?,?)",
        (name, max_sort + 1)
    )
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({"code": 0, "msg": "已添加作业种类", "data": {"id": new_id, "name": name}})


@app.route("/api/homework-types/<int:tid>", methods=["PUT"])
def api_rename_homework_type(tid: int):
    """重命名作业种类"""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"code": 1, "msg": "名称不能为空"}), 400
    db = get_db()
    row = db.execute("SELECT id FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "作业种类不存在"}), 404
    db.execute("UPDATE homework_types SET name=? WHERE id=?", (name, tid))
    db.commit()
    return jsonify({"code": 0, "msg": "已重命名"})


@app.route("/api/homework-types/<int:tid>", methods=["DELETE"])
def api_delete_homework_type(tid: int):
    """删除作业种类"""
    db = get_db()
    row = db.execute("SELECT id FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": "作业种类不存在"}), 404
    # 检查是否只剩一个（全局）
    count = db.execute("SELECT COUNT(*) as c FROM homework_types").fetchone()["c"]
    if count <= 1:
        return jsonify({"code": 1, "msg": "至少保留一个作业种类"}), 400
    db.execute("DELETE FROM homework_types WHERE id=?", (tid,))
    db.commit()
    return jsonify({"code": 0, "msg": "已删除"})


# ============================================================
# 考试成绩管理 API (v2.1 新增)
# ============================================================
@app.route("/api/exam-scores/exams", methods=["GET"])
def api_get_exams():
    """获取当前班级的所有考试列表（去重 exam_name + date）"""
    cid = get_class_id_from_request()
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT exam_name, date, total_score FROM exam_scores "
        "WHERE class_id=? ORDER BY date DESC",
        (cid,)
    ).fetchall()
    exams = []
    seen = set()
    for r in rows:
        key = (r["exam_name"], r["date"])
        if key not in seen:
            seen.add(key)
            exams.append({
                "exam_name": r["exam_name"], "date": r["date"],
                "total_score": r["total_score"],
            })
    return jsonify({"code": 0, "data": exams})


@app.route("/api/exam-scores", methods=["GET"])
def api_get_exam_scores():
    """获取某次考试的所有学生成绩"""
    cid = get_class_id_from_request()
    exam_name = request.args.get("exam_name", "")
    date = request.args.get("date", "")
    if not exam_name or not date:
        return jsonify({"code": 1, "msg": "请指定考试名称和日期"}), 400
    db = get_db()
    rows = db.execute("""
        SELECT e.id, e.student_id, e.date, e.exam_name, e.score,
               e.total_score, e.grade, s.name as student_name,
               s.student_code, s.group_id, g.name as group_name, g.color as group_color
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
        ORDER BY s.group_id, s.sort_order
    """, (exam_name, date, cid)).fetchall()
    records = {}
    for r in rows:
        records[r["student_id"]] = {
            "id": r["id"], "student_id": r["student_id"],
            "student_name": r["student_name"],
            "student_code": r["student_code"] or "",
            "date": r["date"], "exam_name": r["exam_name"],
            "score": r["score"], "total_score": r["total_score"],
            "grade": r["grade"],
            "group_id": r["group_id"],
            "group_name": r["group_name"] or "",
            "group_color": r["group_color"] or "",
        }
    return jsonify({"code": 0, "data": records})


@app.route("/api/exam-scores", methods=["POST"])
def api_save_exam_score():
    """保存/更新单条考试成绩"""
    data = request.get_json() or {}
    student_id = int(data.get("student_id", 0))
    exam_name = data.get("exam_name", "").strip()
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    score = float(data.get("score", 0))
    total_score = float(data.get("total_score", 100))
    cid = get_class_id_from_request()
    if not exam_name:
        return jsonify({"code": 1, "msg": "考试名称不能为空"}), 400
    db = get_db()
    student = db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404
    # 自动计算等第
    grade = ""
    if total_score > 0:
        pct = score / total_score * 100
        if pct >= 90:
            grade = "A"
        elif pct >= 75:
            grade = "B"
        elif pct >= 60:
            grade = "C"
        else:
            grade = "D"
    db.execute("""
        INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT DO UPDATE SET
            score=excluded.score, total_score=excluded.total_score,
            grade=excluded.grade, updated_at=datetime('now','localtime')
    """, (student_id, cid, date, exam_name, score, total_score, grade))
    db.commit()
    return jsonify({"code": 0, "msg": "成绩已保存"})


@app.route("/api/exam-scores/batch", methods=["POST"])
def api_batch_exam_scores():
    """批量录入考试成绩"""
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    exam_name = data.get("exam_name", "").strip()
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    total_score = float(data.get("total_score", 100))
    group_id = int(data.get("group_id", 0))
    student_ids = data.get("student_ids", [])
    score = float(data.get("score", 0))
    if not exam_name:
        return jsonify({"code": 1, "msg": "考试名称不能为空"}), 400
    db = get_db()
    # 自动计算等第
    pct = score / total_score * 100 if total_score > 0 else 0
    grade = ""
    if pct >= 90:
        grade = "A"
    elif pct >= 75:
        grade = "B"
    elif pct >= 60:
        grade = "C"
    else:
        grade = "D"

    if student_ids:
        placeholders = ",".join("?" * len(student_ids))
        db.execute(f"DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN ({placeholders})",
                   [exam_name, date] + student_ids)
        db.execute(f"""INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, ?, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE id IN ({placeholders})""",
                   [cid, date, exam_name, score, total_score, grade] + student_ids)
    elif group_id > 0:
        db.execute("DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN "
                   "(SELECT id FROM students WHERE group_id=? AND class_id=?)",
                   (exam_name, date, group_id, cid))
        db.execute("""INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, ?, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE group_id=? AND class_id=?""",
                   (cid, date, exam_name, score, total_score, grade, group_id, cid))
    else:
        db.execute("DELETE FROM exam_scores WHERE exam_name=? AND date=? AND student_id IN "
                   "(SELECT id FROM students WHERE class_id=?)", (exam_name, date, cid))
        db.execute("""INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                   SELECT id, ?, ?, ?, ?, ?, ?, datetime('now','localtime')
                   FROM students WHERE class_id=?""",
                   (cid, date, exam_name, score, total_score, grade, cid))
    db.commit()
    return jsonify({"code": 0, "msg": f"已批量录入「{exam_name}」成绩"})


@app.route("/api/exam-scores/<int:eid>", methods=["DELETE"])
def api_delete_exam_score(eid: int):
    """删除单条考试成绩"""
    db = get_db()
    db.execute("DELETE FROM exam_scores WHERE id=?", (eid,))
    db.commit()
    return jsonify({"code": 0, "msg": "已删除"})


@app.route("/api/exam-scores/import", methods=["POST"])
def api_import_exam_scores():
    """上传考试 Excel 并导入到 exam_scores 表"""
    cid = get_class_id_from_request()
    if "file" not in request.files:
        return jsonify({"code": 1, "msg": "请选择 Excel 文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"code": 1, "msg": "文件名为空"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return jsonify({"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}), 400
    filename = secure_filename(file.filename)
    file_path = UPLOAD_DIR / f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(str(file_path))
    try:
        result = _parse_exam_excel(str(file_path))
    except Exception as e:
        try: file_path.unlink()
        except Exception: pass
        return jsonify({"code": 1, "msg": f"解析失败: {str(e)}"}), 400
    if "error" in result:
        try: file_path.unlink()
        except Exception: pass
        return jsonify({"code": 1, "msg": result["error"]}), 400
    try: file_path.unlink()
    except Exception: pass

    data = request.get_json() or {} if request.is_json else {}
    exam_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    if request.is_json:
        exam_date = data.get("date", exam_date)

    db = get_db()
    all_students = db.execute(
        "SELECT id, name, student_code FROM students WHERE class_id=?", (cid,)
    ).fetchall()
    # 建立查找映射：name → id, code → id
    name_map = {s["name"].strip(): s["id"] for s in all_students}
    code_map = {}
    for s in all_students:
        if s["student_code"]:
            code_map[s["student_code"].strip()] = s["id"]

    imported, skipped = 0, 0
    for cls_data in result.get("classes", []):
        exam_name = cls_data.get("name", "") or filename.rsplit(".", 1)[0]
        for stu in cls_data.get("students", []):
            name = stu.get("name", "").strip()
            sid = name_map.get(name)
            if not sid and stu.get("code"):
                sid = code_map.get(stu.get("code", "").strip())
            if not sid:
                skipped += 1
                continue
            score = float(stu.get("score", 0)) if stu.get("score") is not None else 0
            total = float(cls_data.get("total_score", 100))
            grade = stu.get("grade", "")
            if not grade and total > 0:
                pct = score / total * 100
                if pct >= 90: grade = "A"
                elif pct >= 75: grade = "B"
                elif pct >= 60: grade = "C"
                else: grade = "D"
            db.execute("""
                INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT DO UPDATE SET
                    score=excluded.score, total_score=excluded.total_score,
                    grade=excluded.grade, updated_at=datetime('now','localtime')
            """, (sid, cid, exam_date, exam_name, score, total, grade))
            imported += 1
    db.commit()
    return jsonify({
        "code": 0, "msg": f"导入完成：{imported} 条，跳过(未匹配) {skipped} 条",
        "data": {"imported": imported, "skipped": skipped}
    })


@app.route("/api/analytics/exam-overview", methods=["GET"])
def api_analytics_exam_overview():
    """考试成绩概览统计"""
    cid = get_class_id_from_request()
    exam_name = request.args.get("exam_name", "")
    date = request.args.get("date", "")
    if not exam_name or not date:
        return jsonify({"code": 1, "msg": "请指定考试名称和日期"}), 400
    db = get_db()
    rows = db.execute("""
        SELECT e.score, e.grade, s.group_id, g.name as group_name, g.color as group_color
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
    """, (exam_name, date, cid)).fetchall()
    if not rows:
        return jsonify({"code": 0, "data": {"total": 0, "avg_score": 0, "max_score": 0, "min_score": 0, "group_stats": []}})

    scores = [r["score"] for r in rows]
    total = len(scores)
    avg_score = round(sum(scores) / total, 1)
    max_score = max(scores)
    min_score = min(scores)
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rows:
        g = r["grade"]
        if g in grade_counts:
            grade_counts[g] += 1

    # 分组统计
    group_map = {}
    for r in rows:
        gname = r["group_name"] or "未分组"
        if gname not in group_map:
            group_map[gname] = {"name": gname, "color": r["group_color"] or "", "scores": [], "count": 0}
        group_map[gname]["scores"].append(r["score"])
        group_map[gname]["count"] += 1
    group_stats = []
    for gn, gd in group_map.items():
        gs = gd["scores"]
        group_stats.append({
            "group_name": gn, "color": gd["color"], "count": gd["count"],
            "avg_score": round(sum(gs) / len(gs), 1),
            "max_score": max(gs), "min_score": min(gs),
        })
    group_stats.sort(key=lambda x: x["avg_score"], reverse=True)

    return jsonify({"code": 0, "data": {
        "exam_name": exam_name, "date": date, "total": total,
        "avg_score": avg_score, "max_score": max_score, "min_score": min_score,
        "grade_counts": grade_counts, "group_stats": group_stats,
    }})


@app.route("/api/export/exam-scores", methods=["GET"])
def api_export_exam_scores():
    """导出考试成绩为 Excel"""
    cid = get_class_id_from_request()
    exam_name = request.args.get("exam_name", "")
    date = request.args.get("date", "")
    if not exam_name or not date:
        return jsonify({"code": 1, "msg": "请指定考试名称和日期"}), 400
    db = get_db()
    rows = db.execute("""
        SELECT s.name as student_name, s.student_code, e.score, e.total_score, e.grade,
               g.name as group_name
        FROM exam_scores e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE e.exam_name=? AND e.date=? AND e.class_id=?
        ORDER BY g.name, s.sort_order
    """, (exam_name, date, cid)).fetchall()
    export_df = pd.DataFrame([{
        "学生姓名": r["student_name"], "学号": r["student_code"] or "",
        "所属分组": r["group_name"] or "未分组",
        "分数": r["score"], "满分": r["total_score"], "等第": r["grade"],
    } for r in rows])
    if export_df.empty:
        export_df = pd.DataFrame([{"学生姓名": "暂无数据"}])
    cls_name = db.execute("SELECT name FROM classes WHERE id=?", (cid,)).fetchone()["name"]
    safe_exam = exam_name.replace("/", "_").replace("\\", "_")
    file_path = TEMP_DIR / f"考试成绩_{cls_name}_{safe_exam}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="考试成绩", index=False)
        ws = writer.sheets["考试成绩"]
        for col, w in zip(["A", "B", "C", "D", "E", "F"], [18, 14, 14, 10, 10, 8]):
            ws.column_dimensions[col].width = w
    return send_file(str(file_path), as_attachment=True,
                     download_name=f"考试成绩_{cls_name}_{safe_exam}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================
# 数据分析 API (图表用)
# ============================================================
@app.route("/api/analytics/overview", methods=["GET"])
def api_analytics_overview():
    """数据概览：当天统计 + 分组对比"""
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()

    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""

    # 当天各等级人数 — 子查询按学生去重取最优等级，避免多作业种类重复计数
    grades_params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    grades = db.execute(f"""
        SELECT best_grade, COUNT(*) as cnt FROM (
            SELECT MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                    WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END) as grade_rank,
                   CASE MIN(CASE h.grade WHEN 'A' THEN 1 WHEN 'B' THEN 2
                                         WHEN 'C' THEN 3 WHEN 'L' THEN 4 WHEN 'X' THEN 5 ELSE 6 END)
                       WHEN 1 THEN 'A' WHEN 2 THEN 'B' WHEN 3 THEN 'C' WHEN 4 THEN 'L' ELSE 'X'
                   END as best_grade
            FROM homework h JOIN students s ON h.student_id = s.id
            WHERE h.date = ? AND s.class_id = ?{hw_filter}
            GROUP BY h.student_id
        ) GROUP BY best_grade
    """, grades_params).fetchall()
    grade_counts = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for g in grades:
        grade_counts[g["best_grade"]] = g["cnt"]

    # 总人数
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    # 未登记人数（当天没有homework记录的学生）
    recorded_params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    recorded = db.execute(f"""
        SELECT COUNT(DISTINCT h.student_id) as c
        FROM homework h JOIN students s ON h.student_id = s.id
        WHERE h.date = ? AND s.class_id = ?{hw_filter}
    """, recorded_params).fetchone()["c"]
    unrecorded = total - recorded

    # 分组对比
    groups = db.execute(
        "SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order", (cid,)
    ).fetchall()
    group_comparison = []
    for g in groups:
        gstudents = db.execute(
            "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (g["id"], cid)
        ).fetchone()["c"]
        ga_params = (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)
        g_a = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, ga_params).fetchone()["c"]
        # 已提交(A/B/C)人数，用于计算 missing
        g_submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade IN ('A','B','C','L') AND s.group_id=? AND s.class_id=?{hw_filter}
        """, (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)).fetchone()["c"]
        group_comparison.append({
            "group_id": g["id"], "group_name": g["name"], "color": g["color"],
            "total": gstudents, "a_count": g_a,
            "missing": gstudents - g_submitted,
            "a_rate": round(g_a / gstudents * 100, 1) if gstudents > 0 else 0,
        })

    return jsonify({
        "code": 0,
        "data": {
            "date": date, "total_students": total,
            "grade_counts": grade_counts, "unrecorded": unrecorded,
            "group_comparison": group_comparison,
        }
    })


@app.route("/api/analytics/trend", methods=["GET"])
def api_analytics_trend():
    """近期趋势：最近N天作业提交率"""
    cid = get_class_id_from_request()
    days = int(request.args.get("days", 14))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    trend = []
    for i in range(days - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        trend_params = (d, cid) if hw_type_id == 0 else (d, cid, hw_type_id)
        submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
            JOIN students s ON h.student_id = s.id
            WHERE h.date=? AND h.grade!='X' AND s.class_id=?{hw_filter}
        """, trend_params).fetchone()["c"]
        rate = round(submitted / total * 100, 1) if total > 0 else 0
        trend.append({"date": d, "submitted": submitted, "total": total, "rate": rate})
    return jsonify({"code": 0, "data": trend})


# ============================================================
# 报表导出 API (带 class_id 过滤)
# ============================================================
@app.route("/api/export/groups", methods=["GET"])
def api_export_groups():
    """导出分组名单 Excel"""
    cid = get_class_id_from_request()
    db = get_db()
    groups = db.execute(
        "SELECT id, name FROM groups_info WHERE class_id=? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    rows = []
    for g in groups:
        students = db.execute(
            "SELECT name FROM students WHERE group_id=? AND class_id=? ORDER BY sort_order, id",
            (g["id"], cid)
        ).fetchall()
        for s in students:
            rows.append({"学生姓名": s["name"], "所属分组": g["name"]})
    # 未分组学生
    unassigned = db.execute(
        "SELECT name FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=? ORDER BY sort_order, id",
        (cid,)
    ).fetchall()
    for s in unassigned:
        rows.append({"学生姓名": s["name"], "所属分组": "未分组"})

    export_df = pd.DataFrame(rows) if rows else pd.DataFrame([{"学生姓名": "暂无学生", "所属分组": ""}])
    cls_name = db.execute("SELECT name FROM classes WHERE id=?", (cid,)).fetchone()["name"]
    file_path = TEMP_DIR / f"分组名单_{cls_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="分组名单", index=False)
        ws = writer.sheets["分组名单"]
        for col, w in zip(["A", "B"], [18, 18]):
            ws.column_dimensions[col].width = w
    return send_file(str(file_path), as_attachment=True,
                     download_name=f"分组名单_{cls_name}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/analytics/submitted", methods=["GET"])
def api_analytics_submitted():
    """获取今日已交学生名单"""
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()
    grade_filter = request.args.get("grade", "").strip().upper()
    grade_condition = ""
    hw_type_condition = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    params = [date, cid]
    if grade_filter in ("A", "B", "C"):
        grade_condition = " AND h.grade = ?"
        params.insert(1, grade_filter)
    if hw_type_id > 0:
        params.append(hw_type_id)
    rows = db.execute(f"""
        SELECT h.student_id, s.name as student_name, s.student_code, h.grade,
               g.name as group_name, g.color as group_color
        FROM homework h
        JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE h.date = ?{grade_condition} AND h.grade != 'X' AND s.class_id = ?{hw_type_condition}
        ORDER BY s.group_id, s.sort_order
    """, params).fetchall()
    return jsonify({"code": 0, "data": [{
        "student_id": r["student_id"], "student_name": r["student_name"],
        "student_code": r["student_code"] or "",
        "grade": r["grade"], "grade_label": grade_label(r["grade"]),
        "group_name": r["group_name"] or "未分组", "group_color": r["group_color"] or "",
    } for r in rows], "total": len(rows)})


@app.route("/api/analytics/missing", methods=["GET"])
def api_analytics_missing():
    """获取今日未交学生名单（含未登记）"""
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    db = get_db()
    all_students = db.execute(
        "SELECT s.id, s.name, s.student_code, s.group_id, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order",
        (cid,)
    ).fetchall()
    submitted_ids = set()
    missing_params = (date, cid) if hw_type_id == 0 else (date, cid, hw_type_id)
    rows = db.execute(
        f"SELECT h.student_id FROM homework h "
        f"JOIN students s ON h.student_id = s.id "
        f"WHERE h.date = ? AND h.grade != 'X' AND s.class_id = ?{hw_filter}",
        missing_params
    ).fetchall()
    for r in rows:
        submitted_ids.add(r["student_id"])
    missing = [{
        "student_id": s["id"], "student_name": s["name"],
        "student_code": s["student_code"] or "",
        "group_name": s["group_name"] or "未分组", "group_color": s["group_color"] or "",
    } for s in all_students if s["id"] not in submitted_ids]
    return jsonify({"code": 0, "data": missing, "total": len(missing)})


# ---- 新增分析 API (v1.4) ----
@app.route("/api/analytics/group-ranking", methods=["GET"])
def api_analytics_group_ranking():
    """小组排行榜：按A率降序"""
    cid = get_class_id_from_request()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    db = get_db()
    groups = db.execute(
        "SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order",
        (cid,)
    ).fetchall()
    ranking = []
    for g in groups:
        gstudents = db.execute(
            "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (g["id"], cid)
        ).fetchone()["c"]
        if gstudents == 0:
            continue
        ga_params = (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)
        a_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, ga_params).fetchone()[0]
        gb_params = (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)
        b_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='B' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, gb_params).fetchone()[0]
        gc_params = (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)
        c_cnt = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade='C' AND s.group_id=? AND s.class_id=?{hw_filter}
        """, gc_params).fetchone()[0]
        # 已提交人数：至少有1条 A/B/C 记录的学生（去重）
        submitted = db.execute(f"""
            SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id
            WHERE h.date=? AND h.grade IN ('A','B','C','L') AND s.group_id=? AND s.class_id=?{hw_filter}
        """, (date, g["id"], cid) if hw_type_id == 0 else (date, g["id"], cid, hw_type_id)).fetchone()[0]
        total_x = gstudents - submitted
        submit_cnt = submitted
        ranking.append({
            "group_id": g["id"], "group_name": g["name"], "color": g["color"],
            "total": gstudents, "a_count": a_cnt, "b_count": b_cnt, "c_count": c_cnt, "x_count": total_x,
            "submit_count": submit_cnt,
            "a_rate": round(a_cnt / gstudents * 100, 1) if gstudents > 0 else 0,
            "submit_rate": round(submit_cnt / gstudents * 100, 1) if gstudents > 0 else 0,
            "avg_score": round((a_cnt * 3 + b_cnt * 2 + c_cnt * 1) / gstudents, 1) if gstudents > 0 else 0,
        })
    ranking.sort(key=lambda x: x["a_rate"], reverse=True)
    return jsonify({"code": 0, "data": ranking, "date": date})


@app.route("/api/analytics/trend-compare", methods=["GET"])
def api_analytics_trend_compare():
    """环比趋势对比：本周vs上周 或 本月vs上月"""
    cid = get_class_id_from_request()
    period = request.args.get("period", "week")
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]

    days = 7 if period == "week" else 30
    today = datetime.now().date()

    def build_trend(offset_days):
        result = []
        for i in range(days - 1, -1, -1):
            d = (today - timedelta(days=offset_days + i)).strftime("%Y-%m-%d")
            trend_params = (d, cid) if hw_type_id == 0 else (d, cid, hw_type_id)
            submitted = db.execute(f"""
                SELECT COUNT(DISTINCT h.student_id) FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade!='X' AND s.class_id=?{hw_filter}
            """, trend_params).fetchone()[0]
            rate = round(submitted / total * 100, 1) if total > 0 else 0
            result.append({"date": d[5:], "rate": rate})
        return result

    current = build_trend(0)
    previous = build_trend(days)
    current_avg = round(sum(d["rate"] for d in current) / len(current), 1) if current else 0
    previous_avg = round(sum(d["rate"] for d in previous) / len(previous), 1) if previous else 0
    change = round(current_avg - previous_avg, 1)

    return jsonify({"code": 0, "data": {
        "current": current, "previous": previous,
        "current_avg": current_avg, "previous_avg": previous_avg, "change": change,
        "period": period, "total_students": total,
    }})


@app.route("/api/analytics/student-alerts", methods=["GET"])
def api_analytics_student_alerts():
    """学生预警：连续未交 + 进步追踪"""
    cid = get_class_id_from_request()
    days = int(request.args.get("days", 14))
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    db = get_db()

    students = db.execute(
        "SELECT s.id, s.name, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id=g.id WHERE s.class_id=? ORDER BY s.id",
        (cid,)
    ).fetchall()

    at_risk = []
    improving = []

    for s in students:
        alert_params = (s["id"], days) if hw_type_id == 0 else (s["id"], days, hw_type_id)
        rows = db.execute(f"""
            SELECT h.date, h.grade FROM homework h
            WHERE h.student_id=?{hw_filter} ORDER BY h.date DESC LIMIT ?
        """, alert_params).fetchall()
        if len(rows) < 3:
            continue
        grades = [r["grade"] for r in rows]  # most recent first

        # 连续未交检测
        consecutive_x = 0
        for g in grades:
            if g == "X":
                consecutive_x += 1
            else:
                break
        if consecutive_x >= 3:
            at_risk.append({
                "student_id": s["id"], "student_name": s["name"],
                "group_name": s["group_name"] or "未分组",
                "consecutive_x": consecutive_x,
                "last_grades": grades[:consecutive_x],
            })

        # 进步检测：近5次记录趋势上升
        if len(grades) >= 5:
            recent5 = grades[:5]
            # 将等级转为数值 (X/请假未参与进步判断)
            def grade_num(g):
                return {"A": 3, "B": 2, "C": 1}.get(g, 0)
            nums = [grade_num(g) for g in recent5 if g not in ("X", "L")]
            if len(nums) >= 3 and nums[0] > nums[-1] and nums[0] >= 2:
                improving.append({
                    "student_id": s["id"], "student_name": s["name"],
                    "group_name": s["group_name"] or "未分组",
                    "from_grade": recent5[-1], "to_grade": recent5[0],
                    "recent_grades": recent5,
                })

    improving.sort(key=lambda x: grade_num(x["to_grade"]) - grade_num(x["from_grade"]), reverse=True)

    return jsonify({"code": 0, "data": {"at_risk": at_risk, "improving": improving[:10]}})


@app.route("/api/student/<int:sid>/report", methods=["GET"])
def api_student_report(sid: int):
    """获取学生个人作业报表（所有日期的等级记录）"""
    db = get_db()
    student = db.execute("SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404
    rows = db.execute("""
        SELECT h.date, h.grade FROM homework h
        WHERE h.student_id = ? ORDER BY h.date DESC
    """, (sid,)).fetchall()
    records = [{"date": r["date"], "grade": r["grade"], "grade_label": grade_label(r["grade"])} for r in rows]
    stats = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for r in rows:
        stats[r["grade"]] = stats.get(r["grade"], 0) + 1
    return jsonify({"code": 0, "data": {
        "student_id": student["id"], "student_name": student["name"],
        "records": records, "stats": stats,
        "total": len(records),
    }})


@app.route("/api/export/student/<int:sid>", methods=["GET"])
def api_export_student(sid: int):
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    db = get_db()
    student = db.execute("SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404
    if start and end:
        rows = db.execute("""
            SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ? AND h.date >= ? AND h.date <= ?
            ORDER BY h.date
        """, (sid, start, end)).fetchall()
    else:
        rows = db.execute("""
            SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ? ORDER BY h.date
        """, (sid,)).fetchall()

    export_df = pd.DataFrame([{
        "学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
        "登记日期": r["date"], "作业评级": grade_label(r["grade"]),
    } for r in rows])
    if export_df.empty:
        export_df = pd.DataFrame([{"学生姓名": student["name"], "所属分组": "", "登记日期": "", "作业评级": "暂无记录"}])
    if rows:
        stats = {}
        for r in rows:
            stats[r["grade"]] = stats.get(r["grade"], 0) + 1
        summary = pd.DataFrame([
            {"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""},
            {"学生姓名": "统计汇总", "所属分组": "", "登记日期": "",
             "作业评级": f"A:{stats.get('A',0)}次 B:{stats.get('B',0)}次 C:{stats.get('C',0)}次 请假:{stats.get('L',0)}次 未交:{stats.get('X',0)}次"},
        ])
        export_df = pd.concat([export_df, summary], ignore_index=True)

    file_path = TEMP_DIR / f"学生台账_{student['name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="作业台账", index=False)
        ws = writer.sheets["作业台账"]
        for col, w in zip(["A", "B", "C", "D"], [18, 14, 14, 25]):
            ws.column_dimensions[col].width = w
    return send_file(str(file_path), as_attachment=True,
                     download_name=f"学生台账_{student['name']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/export/class", methods=["GET"])
def api_export_class():
    cid = get_class_id_from_request()
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    db = get_db()
    base_sql = """
        SELECT h.date, h.grade, s.name as student_name, g.name as group_name
        FROM homework h JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE s.class_id = ?
    """
    if start and end:
        rows = db.execute(base_sql + " AND h.date >= ? AND h.date <= ? ORDER BY s.group_id, s.sort_order, h.date",
                          (cid, start, end)).fetchall()
    else:
        rows = db.execute(base_sql + " ORDER BY s.group_id, s.sort_order, h.date",
                          (cid,)).fetchall()

    export_data = [{"学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
                    "登记日期": r["date"], "作业评级": grade_label(r["grade"])} for r in rows]
    export_df = pd.DataFrame(export_data)
    if export_df.empty:
        export_df = pd.DataFrame([{"学生姓名": "暂无记录", "所属分组": "", "登记日期": "", "作业评级": ""}])
    if rows:
        student_stats = {}
        for r in rows:
            n = r["student_name"]
            if n not in student_stats:
                student_stats[n] = {"group": r["group_name"] or "未分组", "A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
            student_stats[n][r["grade"]] += 1
        summary_data = [
            {"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""},
            {"学生姓名": "=== 全班统计汇总 ===", "所属分组": "", "登记日期": "",
             "作业评级": f"共 {len(student_stats)} 名学生"},
        ]
        for name, stats in student_stats.items():
            total = stats["A"] + stats["B"] + stats["C"] + stats["L"] + stats["X"]
            summary_data.append({
                "学生姓名": name, "所属分组": stats["group"],
                "登记日期": f"共{total}次",
                "作业评级": f"A:{stats['A']} B:{stats['B']} C:{stats['C']} 请假:{stats['L']} 未交:{stats['X']}",
            })
        export_df = pd.concat([export_df, pd.DataFrame(summary_data)], ignore_index=True)

    file_path = TEMP_DIR / f"全班台账_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="全班作业汇总", index=False)
        ws = writer.sheets["全班作业汇总"]
        for col, w in zip(["A", "B", "C", "D"], [18, 14, 14, 35]):
            ws.column_dimensions[col].width = w
    return send_file(str(file_path), as_attachment=True,
                     download_name=f"全班作业汇总_{start}_{end}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================
# 扫码 & 手机联动 API (v1.2 YRL)
# ============================================================
@app.route("/api/student/by-code/<code>", methods=["GET"])
def api_student_by_code(code: str):
    """通过学号查找学生"""
    cid = get_class_id_from_request()
    db = get_db()
    row = db.execute(
        "SELECT s.*, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.student_code = ? AND s.class_id = ?",
        (code.strip(), cid)
    ).fetchone()
    if not row:
        return jsonify({"code": 1, "msg": f"未找到学号 {code} 对应的学生", "external": True})
    return jsonify({"code": 0, "data": {
        "id": row["id"], "name": row["name"], "student_code": row["student_code"] or "",
        "group_id": row["group_id"] or 0, "group_name": row["group_name"] or "",
        "group_color": row["group_color"] or "",
    }})


@app.route("/api/scan/batch", methods=["POST"])
def api_scan_batch():
    """批量提交扫码结果（使用 executemany 批量写入）"""
    data = request.get_json() or {}
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    records = data.get("records", [])  # [{student_code, grade}, ...]
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    cid = get_class_id_from_request()
    if not records:
        return jsonify({"code": 1, "msg": "无扫码记录"}), 400
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 批量查询所有学号对应的 student_id
    codes = [r.get("student_code", "").strip() for r in records]
    placeholders = ",".join(["?" for _ in codes])
    rows = db.execute(
        f"SELECT id, student_code FROM students WHERE student_code IN ({placeholders}) AND class_id=?",
        (*codes, cid)
    ).fetchall()
    code_to_id = {r["student_code"]: r["id"] for r in rows}
    # 批量写入（executemany 比逐条 INSERT 快 10 倍+）
    batch = []
    for rec in records:
        code = rec.get("student_code", "").strip()
        grade = rec.get("grade", "X")
        if grade not in ("A", "B", "C", "L", "X"):
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
    return jsonify({"code": 0, "msg": f"已保存 {len(batch)} 条记录", "data": {"saved": len(batch)}})


@app.route("/api/scan/single", methods=["POST"])
def api_scan_single():
    """单点扫码录入"""
    data = request.get_json() or {}
    code = data.get("student_code", "").strip()
    grade = data.get("grade", "X")
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    hw_type_id = int(data.get("homework_type_id", 0) or 0)
    cid = get_class_id_from_request()
    if grade not in ("A", "B", "C", "L", "X"):
        return jsonify({"code": 1, "msg": "无效等级"}), 400
    db = get_db()
    student = db.execute(
        "SELECT id FROM students WHERE student_code=? AND class_id=?",
        (code, cid)).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": f"未找到学号 {code}", "external": True})
    db.execute("""
        INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET
            grade = excluded.grade,
            updated_at = datetime('now','localtime')
    """, (student["id"], date, grade, hw_type_id))
    db.commit()
    return jsonify({"code": 0, "msg": "登记成功"})


# ---- 手机联动 ----
@app.route("/api/mobile/pair", methods=["GET"])
def api_mobile_pair():
    """返回配对信息（移动端使用 HTTPS 才能调用摄像头）"""
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
    return jsonify({
        "code": 0,
        "data": {
            "ip": host, "port": port,
            "url": f"https://{host}:{port}/mobile",
            "ssl": True,
        }
    })


@app.route("/api/mobile/scan/batch", methods=["POST"])
def api_mobile_scan_batch():
    """手机端批量提交扫码（一次请求提交 N 个学号）"""
    data = request.get_json() or {}
    codes = data.get("codes", [])
    if not codes or not isinstance(codes, list):
        return jsonify({"code": 1, "msg": "无效的学号列表"}), 400
    # 去重 + 清洗
    unique = list(dict.fromkeys([c.strip() for c in codes if c and c.strip()]))
    if not unique:
        return jsonify({"code": 1, "msg": "无有效学号"}), 400
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 批量 INSERT（比逐条快 10x+）
    db.executemany(
        "INSERT INTO mobile_scans (student_code, scanned_at) VALUES (?, ?)",
        [(c, now) for c in unique]
    )
    db.commit()
    return jsonify({"code": 0, "msg": f"已接收 {len(unique)} 条", "data": {"count": len(unique)}})


@app.route("/api/mobile/scan", methods=["POST"])
def api_mobile_scan():
    """手机端提交扫码（单条，保留兼容旧版）"""
    data = request.get_json() or {}
    code = data.get("student_code", "").strip()
    if not code:
        return jsonify({"code": 1, "msg": "未识别到学号"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO mobile_scans (student_code, scanned_at) VALUES (?, ?)",
        (code, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    return jsonify({"code": 0, "msg": "已接收"})


@app.route("/api/mobile/scans", methods=["GET"])
def api_mobile_scans():
    """电脑端轮询获取手机扫码"""
    since = request.args.get("since", "1970-01-01 00:00:00")
    db = get_db()
    rows = db.execute(
        "SELECT id, student_code, scanned_at FROM mobile_scans "
        "WHERE scanned_at > ? AND processed = 0 ORDER BY scanned_at",
        (since,)
    ).fetchall()
    scans = []
    cid = get_class_id_from_request()
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
    return jsonify({"code": 0, "data": scans, "since": max_ts, "total": len(scans)})


@app.route("/api/mobile/clear", methods=["POST"])
def api_mobile_clear():
    """清空待处理扫码"""
    db = get_db()
    db.execute("DELETE FROM mobile_scans")
    db.commit()
    return jsonify({"code": 0, "msg": "已清空"})


# ---- 二维码生成（服务端 Python 生成，无需 CDN，离线可用） ----
@app.route("/api/qrcode", methods=["GET"])
def api_qrcode():
    """生成真实二维码（PNG 格式），可通过 ?data=URL&size=200 调整尺寸"""
    data = request.args.get("data", "")
    size = int(request.args.get("size", 150))
    if not data:
        return jsonify({"code": 1, "msg": "缺少 data 参数"}), 400
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
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---- 手机扫码页面 ----
@app.route("/mobile")
def page_mobile():
    """手机扫码端"""
    return render_template("mobile.html")


# ---- 二维码打印页面 ----
@app.route("/print")
def page_print():
    """二维码批量打印"""
    return render_template("print.html")


# ---- CA 证书下载（供手机安装信任） ----
@app.route("/api/cert/download")
def api_cert_download():
    """下载 CA 根证书，供手机等设备安装信任"""
    ca_cert_file = DATA_DIR / "ca-cert.pem"
    if not ca_cert_file.exists():
        return jsonify({"code": 1, "msg": "CA 证书尚未生成，请先在电脑端启动一次程序"}), 404
    return send_file(
        str(ca_cert_file),
        as_attachment=True,
        download_name="ClassTrack_CA_Certificate.crt",
        mimetype="application/x-x509-ca-cert",
    )


# ============================================================
# 系统 API
# ============================================================
@app.route("/api/config", methods=["GET"])
def api_get_config():
    db = get_db()
    rows = db.execute("SELECT key, value FROM app_config").fetchall()
    return jsonify({"code": 0, "data": {r["key"]: r["value"] for r in rows}})


@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json() or {}
    db = get_db()
    for key, value in data.items():
        db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES (?,?)",
                   (str(key), str(value)))
    db.commit()
    return jsonify({"code": 0, "msg": "配置已保存"})


@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    cid = get_class_id_from_request()
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()
    total_students = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    total_groups = db.execute(
        "SELECT COUNT(*) as c FROM groups_info WHERE class_id=?", (cid,)).fetchone()["c"]
    grouped = db.execute(
        "SELECT COUNT(*) as c FROM students WHERE group_id > 0 AND class_id=?", (cid,)
    ).fetchone()["c"]
    hw_filter = " AND h.homework_type_id = ?" if hw_type_id > 0 else ""
    rec_params = (cid,) if hw_type_id == 0 else (cid, hw_type_id)
    total_records = db.execute(
        f"SELECT COUNT(*) as c FROM homework h JOIN students s ON h.student_id=s.id WHERE s.class_id=?{hw_filter}",
        rec_params).fetchone()["c"]
    last_lock = db.execute("SELECT value FROM app_config WHERE key='last_lock_time'").fetchone()
    cls = db.execute("SELECT name FROM classes WHERE id=?", (cid,)).fetchone()
    return jsonify({
        "code": 0,
        "data": {
            "total_students": total_students, "total_groups": total_groups,
            "grouped_students": grouped, "unassigned_students": total_students - grouped,
            "total_homework_records": total_records,
            "last_lock_time": last_lock["value"] if last_lock else "尚未锁定",
            "is_locked": _class_is_locked(db, cid),
            "class_name": cls["name"] if cls else "",
        }
    })


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """安全关闭服务器（配合 PyInstaller windowed 模式）"""
    import signal
    os._exit(0)
    return jsonify({"code": 0})


# ============================================================
# 激活校验 API (v1.5 新增 — 纯离线，不侵入原有业务代码)
# ============================================================
@app.route("/api/activation/fingerprint", methods=["GET"])
def api_activation_fingerprint():
    """获取本机硬件指纹和机器码"""
    if not _ACTIVATION_AVAILABLE:
        return jsonify({"code": 1, "msg": "激活模块未加载"}), 500
    try:
        info = get_full_hardware_fingerprint()
        fp_export = export_fingerprint()
        return jsonify({
            "code": 0,
            "data": {
                "machine_code": info["machine_code"],
                "fingerprint_export": fp_export,
                "cpu": info["cpu"],
                "disk": info["disk"],
            }
        })
    except Exception as e:
        return jsonify({"code": 1, "msg": f"采集失败: {str(e)}"}), 500


@app.route("/api/activation/verify", methods=["POST"])
def api_activation_verify():
    """校验并保存激活文件"""
    if not _ACTIVATION_AVAILABLE:
        return jsonify({"code": 1, "msg": "激活模块未加载"}), 500
    data = request.get_json(silent=True) or {}
    file_content = data.get("file_content", "")
    if not file_content:
        return jsonify({"code": 1, "msg": "未提供激活文件内容"}), 400

    # 先保存文件，再校验
    if not save_activation_file(file_content):
        return jsonify({"code": 1, "msg": "激活文件保存失败"}), 500

    # 执行完整校验
    result = verify_activation()
    return jsonify({
        "code": 0 if result.activated else 1,
        "msg": result.reason,
        "data": result.to_dict(),
    })


@app.route("/api/activation/status", methods=["GET"])
def api_activation_status():
    """查询当前激活状态（供前端轮询使用）"""
    if not _ACTIVATION_AVAILABLE:
        return jsonify({"code": 0, "data": {"activated": True}})
    result = verify_activation()
    return jsonify({
        "code": 0,
        "data": result.to_dict(),
    })


@app.route("/activation")
@app.route("/activation/")
def page_activation():
    """激活登录页面（支持有无尾部斜杠）"""
    return render_template("activation.html")


# ============================================================
# 激活校验中间件: 未激活时锁定全部功能
# ============================================================
# 白名单路由（无需激活即可访问）
_ACTIVATION_WHITELIST = {
    "/activation",
    "/api/activation/fingerprint",
    "/api/activation/verify",
    "/api/activation/status",
    "/api/shutdown",
    "/api/cert/download",
    "/api/qrcode",
    "/mobile",
    "/print",
}


@app.before_request
def activation_guard():
    """每次请求前校验激活状态，未激活时强制跳转激活页"""
    if not _ACTIVATION_AVAILABLE:
        return None  # 激活模块不可用时放行（开发/降级模式）

    try:
        path = (request.path or "/").rstrip("/") or "/"

        # 静态文件始终放行
        if path.startswith("/static/"):
            return None

        # 白名单路由放行（含尾部斜杠变体）
        if path in _ACTIVATION_WHITELIST:
            return None

        # favicon / robots.txt 等无伤大雅的请求放行
        if path in ("/favicon.ico", "/robots.txt"):
            return None

        result = verify_activation()
        if not result.activated:
            if path.startswith("/api/"):
                return jsonify({
                    "code": 403,
                    "msg": "软件未激活，请先完成激活登录",
                    "data": {"activated": False, "machine_code": result.machine_code}
                }), 403
            # 页面请求：展示激活登录页（URL保持不变）
            return page_activation()

        return None
    except Exception:
        # 防止 before_request 本身异常导致 500
        import traceback
        traceback.print_exc()
        return None  # 异常时放行，避免全部请求卡死


# ============================================================
# AI 助手模块 (v2.0)
# ============================================================

# ---- AI 配置加密/解密 ----
def _ai_key_encode(raw: str) -> str:
    """Base64 编码 API Key（本地混淆，非强加密）"""
    if not raw:
        return ""
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def _ai_key_decode(encoded: str) -> str:
    """Base64 解码 API Key"""
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return encoded  # 兼容旧数据（可能未编码）


def _get_ai_config() -> dict:
    """从 app_config 读取 AI 配置"""
    db = get_db()
    rows = db.execute(
        "SELECT key, value FROM app_config WHERE key LIKE 'ai_%'"
    ).fetchall()
    config = {r["key"]: r["value"] for r in rows}
    return {
        "provider": config.get("ai_provider", "deepseek"),
        "api_key": _ai_key_decode(config.get("ai_api_key", "")),
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
    import json as _json
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
    grade_json = _json.dumps({
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
        groups_json = _json.dumps({
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
        trend_json = _json.dumps({
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
        import json as _json2
        exam_json = _json2.dumps({
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


# ---- AI 配置 API ----
@app.route("/api/ai/config", methods=["GET"])
def api_get_ai_config():
    """获取 AI 配置（API Key 脱敏）"""
    config = _get_ai_config()
    raw_key = config.get("api_key", "")
    masked = ""
    if raw_key:
        if len(raw_key) > 4:
            masked = raw_key[:4] + "*" * (len(raw_key) - 4)
        else:
            masked = raw_key[:2] + "**"
    return jsonify({
        "code": 0,
        "data": {
            "provider": config["provider"],
            "api_key_masked": masked,
            "has_key": bool(raw_key),
            "base_url": config.get("base_url", ""),
            "model": config["model"],
        }
    })


@app.route("/api/ai/config", methods=["POST"])
def api_save_ai_config():
    """保存 AI 配置"""
    data = request.get_json() or {}
    provider = data.get("provider", "deepseek").strip()
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "").strip()

    if provider not in ("deepseek", "openai", "qwen", "custom"):
        return jsonify({"code": 1, "msg": "无效的 AI 服务商"}), 400
    if provider == "custom" and not base_url:
        return jsonify({"code": 1, "msg": "自定义服务商需填写 Base URL"}), 400
    if not api_key:
        return jsonify({"code": 1, "msg": "API Key 不能为空"}), 400
    if not model:
        return jsonify({"code": 1, "msg": "模型名称不能为空"}), 400

    db = get_db()
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_provider',?)", (provider,))
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_api_key',?)",
               (_ai_key_encode(api_key),))
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_base_url',?)", (base_url,))
    db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('ai_model',?)", (model,))
    db.commit()

    return jsonify({"code": 0, "msg": "AI 配置已保存"})


@app.route("/api/ai/test", methods=["POST"])
def api_ai_test():
    """测试 AI 连接"""
    data = request.get_json() or {}
    # 可用前端传的临时配置测试，未传则用已保存配置
    provider = data.get("provider", "").strip()
    api_key = data.get("api_key", "").strip()
    base_url = data.get("base_url", "").strip()
    model = data.get("model", "").strip()

    if provider:
        config = {
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }
    else:
        config = _get_ai_config()

    success, content = _call_llm(config, [
        {"role": "user", "content": "你好，请回复'连接成功'这两个字，不要其他内容。"}
    ], timeout=15)

    if success:
        return jsonify({"code": 0, "msg": "连接成功 🟢", "data": {"reply": content.strip()}})
    else:
        return jsonify({"code": 1, "msg": f"连接失败 🔴 {content}"}), 400


# ---- 图表自动构建引擎 ----
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


# ---- 动态提问建议 API ----
@app.route("/api/ai/suggestions", methods=["GET"])
def api_ai_suggestions():
    """返回基于当前数据的智能提问建议"""
    cid = get_class_id_from_request()
    hw_type_id = request.args.get("homework_type_id", 0, type=int) or 0
    db = get_db()

    today = datetime.now().strftime("%Y-%m-%d")
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]

    # 构建作业种类过滤条件
    hw_type_join = ""
    hw_type_where = ""
    hw_type_params_extra = ()
    if hw_type_id > 0:
        hw_type_join = " JOIN homework_types ht ON h.homework_type_id = ht.id"
        hw_type_where = " AND h.homework_type_id = ?"
        hw_type_params_extra = (hw_type_id,)

    # 基于数据动态生成建议
    suggestions = []

    # 基础问题
    suggestions.append({"text": "今天哪个组表现最好？", "icon": "🏆"})
    suggestions.append({"text": "最近一周的提交率趋势如何？", "icon": "📈"})
    suggestions.append({"text": "今天的作业等级分布是怎样的？", "icon": "🍩"})

    # 数据驱动的问题
    if total > 0:
        # 找到A率最高和最低的组
        groups = db.execute(
            "SELECT id, name FROM groups_info WHERE class_id=? ORDER BY sort_order", (cid,)
        ).fetchall()
        if groups:
            # 有分组数据时，生成具体问题
            best_name = None
            best_rate = -1
            worst_name = None
            worst_rate = 101
            for g in groups:
                gs = db.execute(
                    "SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (g["id"], cid)
                ).fetchone()["c"]
                if gs == 0:
                    continue
                ga = db.execute(f"""
                    SELECT COUNT(DISTINCT h.student_id) as c FROM homework h JOIN students s ON h.student_id=s.id
                    {hw_type_join}
                    WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=? {hw_type_where}
                """, (today, g["id"], cid) + hw_type_params_extra).fetchone()["c"]
                rate = round(ga / gs * 100, 1) if gs > 0 else 0
                if rate > best_rate:
                    best_rate = rate
                    best_name = g["name"]
                if rate < worst_rate:
                    worst_rate = rate
                    worst_name = g["name"]

            if best_name and worst_name and best_name != worst_name:
                suggestions.append({
                    "text": f"为什么{best_name}表现这么好？对比一下{worst_name}",
                    "icon": "🔍",
                })

        # 检查是否有连续未交的学生
        students = db.execute(
            "SELECT s.id, s.name FROM students s WHERE s.class_id=? ORDER BY s.id", (cid,)
        ).fetchall()
        at_risk_names = []
        for s in students:
            rows = db.execute(f"""
                SELECT h.grade FROM homework h
                {hw_type_join}
                WHERE h.student_id=? {hw_type_where}
                ORDER BY h.date DESC LIMIT 5
            """, (s["id"],) + hw_type_params_extra).fetchall()
            cx = 0
            for r in rows:
                if r["grade"] == "X":
                    cx += 1
                else:
                    break
            if cx >= 3:
                at_risk_names.append(s["name"])

        if at_risk_names:
            suggestions.append({
                "text": f"哪些学生需要特别关注？（如{at_risk_names[0]}）",
                "icon": "⚠️",
            })
        else:
            suggestions.append({"text": "对比本周和上周的作业表现", "icon": "📉"})

    # 学生个体问题
    if total > 0:
        suggestions.append({"text": "帮我分析一下整体学情，哪些学生进步最大？", "icon": "🌟"})

    # 去重并限制数量
    seen = set()
    unique = []
    for s in suggestions:
        if s["text"] not in seen:
            seen.add(s["text"])
            unique.append(s)
    suggestions = unique[:8]

    return jsonify({"code": 0, "data": {"suggestions": suggestions}})


# ---- AI 对话 API ----
@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    """AI 对话接口：分析问题 + 获取数据 + 调用 LLM + 返回图表"""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"code": 1, "msg": "请输入问题"}), 400

    cid = get_class_id_from_request()
    hw_type_id = data.get("homework_type_id", 0) or 0
    db = get_db()
    config = _get_ai_config()

    # 1. 提取意图和上下文数据
    context = _extract_intent(question, db, cid, hw_type_id)

    # 1.5 如果有缓存的考试数据，合并到上下文中
    exam_cache = _exam_data_cache.get(str(cid))
    if exam_cache:
        context["exam_data"] = exam_cache["data"]
        context["has_exam_data"] = True

    data_prompt = _build_data_prompt(context)

    # 2. 服务端自动构建图表兜底（当 LLM 无法生成 HTML 时使用）
    auto_chart = _build_chart_from_context(context)

    # 3. 构建 LLM prompt — LLM 自由生成 HTML 可视化面板
    system_prompt = """你是 ClassTrack 的 AI 教学助手。你必须严格遵守以下格式回复。

## 回复格式（不可违反）
你的每个回复必须包含两部分，用单独一行 `---VIZ---` 分隔：

第一段：文字分析（必填，2-5句话，中文）
- 直接回应老师的问题
- 引用具体数据（组名、数字、百分比）
- 给出可操作的建议

第二段：HTML 可视化面板
- 如果问题适合可视化（对比、分布、趋势、排名等），生成 HTML
- 如果只是闲聊或简单问答，第二段留空（但 `---VIZ---` 分隔符必须保留）

## HTML 可视化规范
- 使用 inline CSS，马卡龙配色：卡片 #fff，主色 #7EB5D6，强调 #E8A0BF，成功 #A8D5BA，警告 #F4C97E，背景 #f8f6f5
- 可以包含：统计卡片数字、ECharts图表、表格、进度条、标签
- ECharts 变量 `echarts` 已全局可用，图表容器用 id="viz_chart_1"、id="viz_chart_2" 等
- 每个图表容器必须有明确的 width 和 height（如 style="width:100%;height:280px"）
- 使用 `<script>` 标签初始化 ECharts，放在 HTML 末尾
- ★ ECharts 初始化必须监听 'echartsReady' 事件（或直接用 DOMContentLoaded），不要使用 window.onload 赋值！
- 可视化要突出关键发现（最好/最差高亮、趋势箭头、异常标注）
- 示例脚本写法（二选一）：

  方式1（推荐，等待 echarts 就绪）：
  <script>
  window.addEventListener('echartsReady', function() {
    var dom = document.getElementById('viz_chart_1');
    if (dom && typeof echarts !== 'undefined') {
      var chart = echarts.init(dom);
      chart.setOption({ ... });
    }
  });
  </script>

  方式2（echarts 已在脚本之前注入，直接执行）：
  <script>
  (function() {
    var dom = document.getElementById('viz_chart_1');
    if (dom && typeof echarts !== 'undefined') {
      var chart = echarts.init(dom);
      chart.setOption({ ... });
    }
  })();
  </script>"""

    user_prompt = f"""以下是当前班级数据：

{data_prompt}

老师的问题是：{question}

请严格遵守格式回复（文字分析 + ---VIZ--- + HTML面板）。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 4. 调用 LLM
    success, content = _call_llm(config, messages)

    # 5. 解析回复：文字 + HTML 可视化
    import re
    reply = ""
    viz_html = None
    chart = auto_chart  # 兜底

    if success:
        # 按 ---VIZ--- 分隔
        viz_split = re.split(r'\n?---VIZ---\n?', content, maxsplit=1)

        if len(viz_split) == 2:
            reply = viz_split[0].strip()
            viz_raw = viz_split[1].strip()

            # 提取 HTML（支持有/无 ```html 包裹）
            html_match = re.search(r'```html?\s*\n(.*?)\n```', viz_raw, re.DOTALL)
            if html_match:
                viz_html = html_match.group(1).strip()
            elif viz_raw and viz_raw[0] == '<':
                viz_html = viz_raw
        else:
            # LLM 没有用 ---VIZ--- 分隔，整体作为回复
            reply = content.strip()

        # 兜底：如果回复为空，根据数据生成自动摘要
        if not reply:
            reply = _generate_fallback_reply(context, question)

        # 如果 LLM 没生成 HTML，用服务端图表
        if viz_html and len(viz_html) > 50:
            chart = None  # 用 viz_html 替代 chart
        elif not viz_html and chart:
            pass  # 用服务端图表

        # 兼容旧图表格式
        chart_match = re.search(r'```chart\s*\n(.*?)\n```', content, re.DOTALL)
        if chart_match:
            try:
                chart = json.loads(chart_match.group(1))
                if not reply:
                    reply = content[:chart_match.start()].strip()
            except json.JSONDecodeError:
                pass
    else:
        reply = f"❌ {content}"

    # 确保 reply 至少有一段文字
    if not reply:
        reply = _generate_fallback_reply(context, question)

    return jsonify({
        "code": 0 if success else 1,
        "data": {
            "reply": reply,
            "chart": chart,
            "viz_html": viz_html,
            "follow_ups": _generate_follow_ups(context, question),
            "export_data": {
                "class_name": context.get("class_name", ""),
                "date": context.get("date", ""),
                "grade_counts": context.get("grade_counts", {}),
                "group_data": context.get("group_data", []),
                "trend": context.get("trend", []),
                "total_students": context.get("total_students", 0),
            },
            "context": {
                "intents": context.get("intents", []),
                "date": context["date"],
            }
        }
    })


# ---- AI 数据导出 API ----
@app.route("/api/ai/export/excel", methods=["POST"])
def api_ai_export_excel():
    """将当前 AI 对话的数据导出为 Excel"""
    data = request.get_json() or {}
    export_data = data.get("export_data", {})
    title = data.get("title", "AI分析报告")

    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")
    grade_counts = export_data.get("grade_counts", {})
    group_data = export_data.get("group_data", [])
    trend = export_data.get("trend", [])

    # 构建 Excel
    file_path = TEMP_DIR / f"AI分析报告_{class_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    with pd.ExcelWriter(str(file_path), engine="openpyxl") as writer:
        # Sheet 1: 概览
        overview_data = {
            "班级": [class_name],
            "统计日期": [date_str],
            "A(优秀)": [grade_counts.get("A", 0)],
            "B(良好)": [grade_counts.get("B", 0)],
            "C(待改进)": [grade_counts.get("C", 0)],
            "未交": [grade_counts.get("X", 0)],
            "未登记": [grade_counts.get("未登记", 0)],
        }
        pd.DataFrame(overview_data).to_excel(writer, sheet_name="作业概览", index=False)

        # Sheet 2: 小组对比
        if group_data:
            gd = [{
                "小组": g["name"], "人数": g["total"],
                "A人数": g.get("a_count", 0), "A率(%)": g.get("a_rate", 0),
                "未交人数": g.get("missing", 0),
            } for g in group_data]
            pd.DataFrame(gd).to_excel(writer, sheet_name="小组对比", index=False)

        # Sheet 3: 趋势
        if trend:
            td = [{"日期": t["date"], "提交率(%)": t["rate"]} for t in trend]
            pd.DataFrame(td).to_excel(writer, sheet_name="趋势数据", index=False)

        # 调整列宽
        for ws in writer.sheets.values():
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)

    return send_file(str(file_path), as_attachment=True,
                     download_name=f"AI分析报告_{class_name}_{date_str}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/ai/export/word", methods=["POST"])
def api_ai_export_word():
    """将当前 AI 对话的数据导出为 Word（HTML格式，Word可直接打开）"""
    data = request.get_json() or {}
    export_data = data.get("export_data", {})
    reply = data.get("reply", "")
    viz_html = data.get("viz_html", "")

    class_name = export_data.get("class_name", "")
    date_str = export_data.get("date", "")
    grade_counts = export_data.get("grade_counts", {})
    group_data = export_data.get("group_data", [])
    trend = export_data.get("trend", [])
    total = export_data.get("total_students", 0)

    # 构建 Word 兼容的 HTML 文档
    html_parts = ["""<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:w="urn:schemas-microsoft-com:office:word"
xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="UTF-8">
<style>
body { font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; color: #333; padding: 20px; }
h1 { color: #7EB5D6; border-bottom: 2px solid #7EB5D6; padding-bottom: 8px; }
h2 { color: #5D5A5A; margin-top: 20px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; }
th { background: #7EB5D6; color: #fff; padding: 8px; text-align: left; }
td { padding: 6px 8px; border: 1px solid #ddd; }
.stat-box { display: inline-block; padding: 10px 16px; margin: 6px;
  border-radius: 8px; background: #f0f7fb; text-align: center; }
.stat-num { font-size: 24px; font-weight: bold; color: #7EB5D6; }
.stat-label { font-size: 12px; color: #888; }
</style></head><body>"""]

    html_parts.append(f"<h1>📊 ClassTrack AI 分析报告</h1>")
    html_parts.append(f"<p><strong>班级：</strong>{class_name} &nbsp; <strong>日期：</strong>{date_str} &nbsp; <strong>学生总数：</strong>{total}人</p>")

    # 统计卡片
    html_parts.append('<div style="margin:16px 0">')
    for label, key, color in [("A 优秀", "A", "#7EB5D6"), ("B 良好", "B", "#A8D5BA"),
                               ("C 待改进", "C", "#F4C97E"), ("未交", "X", "#E8A0BF")]:
        html_parts.append(f'<div class="stat-box"><div class="stat-num" style="color:{color}">{grade_counts.get(key, 0)}</div><div class="stat-label">{label}</div></div>')
    html_parts.append('</div>')

    # 小组对比表
    if group_data:
        html_parts.append("<h2>📋 小组对比</h2>")
        html_parts.append('<table><tr><th>小组</th><th>人数</th><th>A人数</th><th>A率</th><th>未交</th></tr>')
        for g in group_data:
            html_parts.append(f'<tr><td>{g["name"]}</td><td>{g["total"]}</td><td>{g.get("a_count", 0)}</td><td>{g.get("a_rate", 0)}%</td><td>{g.get("missing", 0)}</td></tr>')
        html_parts.append('</table>')

    # 趋势表
    if trend:
        html_parts.append("<h2>📈 趋势数据</h2>")
        html_parts.append('<table><tr><th>日期</th><th>提交率</th></tr>')
        for t in trend:
            html_parts.append(f'<tr><td>{t["date"]}</td><td>{t["rate"]}%</td></tr>')
        html_parts.append('</table>')

    # AI 分析
    if reply:
        html_parts.append(f"<h2>🤖 AI 分析</h2><p>{reply}</p>")

    html_parts.append("<p style='margin-top:30px;color:#aaa;font-size:11px'>由 ClassTrack AI 助手自动生成</p>")
    html_parts.append("</body></html>")

    full_html = "\n".join(html_parts)
    file_path = TEMP_DIR / f"AI分析报告_{class_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.doc"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    return send_file(str(file_path), as_attachment=True,
                     download_name=f"AI分析报告_{class_name}_{date_str}.doc",
                     mimetype="application/msword")


# ---- 考试 Excel 导入 API ----

# 存储最近一次上传的考试数据（内存缓存，用于 AI 对话上下文）
_exam_data_cache = {}  # key: class_id -> parsed exam data

EXAM_GRADE_MAP = [
    (90, "A"),   # >= 90 → A
    (75, "B"),   # >= 75 → B
    (60, "C"),   # >= 60 → C
    (0, "X"),    # < 60  → X (未达标)
]


def _parse_exam_excel(file_path: str) -> dict:
    """
    智能解析考试 Excel，自动识别列结构。
    支持易卷通等常见阅卷平台的导出格式。
    返回: {classes: [{name, students: [{name, code, score, grade}]}], raw_rows, detected_columns}
    """
    file_ext = Path(file_path).suffix.lower()
    try:
        if file_ext == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
        elif file_ext == ".xls":
            df = pd.read_excel(file_path, engine="xlrd", dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)
    except Exception:
        df = pd.read_excel(file_path, dtype=str, engine=None)

    if df.empty:
        return {"error": "Excel 文件为空", "classes": [], "detected_columns": []}

    # 清理列名
    df.columns = [str(c).strip() for c in df.columns]

    # ---- 智能检测列 ----
    col_map = {"name": None, "code": None, "class_name": None, "score": None, "grade_letter": None}

    for col in df.columns:
        cl = col.lower().replace(" ", "")
        # 姓名列
        if not col_map["name"] and any(kw in cl for kw in ["姓名", "名字", "学生姓名", "学生", "name"]):
            col_map["name"] = col
        # 学号/考号列
        if not col_map["code"] and any(kw in cl for kw in ["学号", "考号", "编号", "id", "code", "准考证"]):
            col_map["code"] = col
        # 班级列
        if not col_map["class_name"] and any(kw in cl for kw in ["班级", "班", "class", "行政班", "教学班"]):
            col_map["class_name"] = col
        # 分数列
        if not col_map["score"] and any(kw in cl for kw in ["成绩", "分数", "得分", "总分", "score", "总成绩", "卷面"]):
            col_map["score"] = col
        # 等第列（可能已有 A/B/C/D 等）
        if not col_map["grade_letter"] and any(kw in cl for kw in ["等第", "等级", "grade", "评级", "档次"]):
            col_map["grade_letter"] = col

    # 兜底：如果没识别到姓名列，用第一列
    if not col_map["name"] and len(df.columns) > 0:
        col_map["name"] = df.columns[0]
    # 兜底：如果没识别到分数列，尝试找纯数字列
    if not col_map["score"]:
        for col in df.columns:
            if col == col_map["name"]:
                continue
            try:
                numeric_count = sum(1 for v in df[col] if str(v).strip().replace(".", "").replace("-", "").isdigit())
                if numeric_count > len(df) * 0.5:
                    col_map["score"] = col
                    break
            except Exception:
                pass

    # ---- 解析数据 ----
    students = []
    for _, row in df.iterrows():
        name = str(row[col_map["name"]]).strip() if col_map["name"] and pd.notna(row[col_map["name"]]) else ""
        if not name or name in ("nan", "None", "", "姓名", "学生姓名", "名字"):
            continue

        code = ""
        if col_map["code"] and pd.notna(row[col_map["code"]]):
            code = str(row[col_map["code"]]).strip()
            if code in ("nan", "None"):
                code = ""

        class_name = ""
        if col_map["class_name"] and pd.notna(row[col_map["class_name"]]):
            class_name = str(row[col_map["class_name"]]).strip()
            if class_name in ("nan", "None"):
                class_name = ""
            # 统一班级格式：去掉"班"字，如 "高一1班" → "高一1"
            class_name = class_name.replace(" ", "")

        # 解析分数
        score = None
        if col_map["score"] and pd.notna(row[col_map["score"]]):
            try:
                score_str = str(row[col_map["score"]]).strip()
                score = float(score_str)
            except (ValueError, TypeError):
                score = None

        # 解析等第
        letter = ""
        if col_map["grade_letter"] and pd.notna(row[col_map["grade_letter"]]):
            letter = str(row[col_map["grade_letter"]]).strip().upper()
            if letter in ("nan", "NONE"):
                letter = ""

        # 根据分数映射等第
        if not letter and score is not None:
            for threshold, g in EXAM_GRADE_MAP:
                if score >= threshold:
                    letter = g
                    break

        students.append({
            "name": name,
            "code": code,
            "class_name": class_name,
            "score": score,
            "score_display": str(int(score)) if score is not None and score == int(score) else (
                str(score) if score is not None else ""),
            "grade": letter,
        })

    if not students:
        return {"error": "未能从 Excel 中识别出有效学生数据", "classes": [], "detected_columns": list(df.columns)}

    # ---- 按班级分组 ----
    class_groups = {}
    for s in students:
        cn = s["class_name"] or "未识别班级"
        if cn not in class_groups:
            class_groups[cn] = []
        class_groups[cn].append(s)

    classes_result = []
    for cn, sts in class_groups.items():
        # 统计
        stats = {"A": 0, "B": 0, "C": 0, "X": 0, "total": len(sts)}
        scores_list = []
        for s in sts:
            if s["grade"] in stats:
                stats[s["grade"]] += 1
            if s["score"] is not None:
                scores_list.append(s["score"])
        avg_score = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
        max_score = max(scores_list) if scores_list else 0
        min_score = min(scores_list) if scores_list else 0

        classes_result.append({
            "class_name": cn,
            "student_count": len(sts),
            "stats": stats,
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "students": sts,
        })

    # 按总人数排序（最多的班级排前面）
    classes_result.sort(key=lambda c: c["student_count"], reverse=True)

    return {
        "classes": classes_result,
        "total_students": len(students),
        "detected_columns": list(df.columns),
        "column_mapping": {k: v for k, v in col_map.items() if v},
    }


@app.route("/api/ai/import-exam", methods=["POST"])
def api_ai_import_exam():
    """上传考试 Excel 并智能解析"""
    if "file" not in request.files:
        return jsonify({"code": 1, "msg": "请选择 Excel 文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"code": 1, "msg": "文件名为空"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        return jsonify({"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}), 400

    filename = secure_filename(file.filename)
    file_path = UPLOAD_DIR / f"exam_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(str(file_path))

    try:
        result = _parse_exam_excel(str(file_path))
    except Exception as e:
        try:
            file_path.unlink()
        except Exception:
            pass
        return jsonify({"code": 1, "msg": f"解析 Excel 失败: {str(e)}"}), 400

    if "error" in result:
        try:
            file_path.unlink()
        except Exception:
            pass
        return jsonify({"code": 1, "msg": result["error"]}), 400

    # 缓存到内存
    cid = get_class_id_from_request()
    _exam_data_cache[str(cid)] = {
        "source_file": filename,
        "data": result,
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 清理临时文件
    try:
        file_path.unlink()
    except Exception:
        pass

    return jsonify({
        "code": 0,
        "msg": f"已识别 {result['total_students']} 名学生，{len(result['classes'])} 个班级/组别",
        "data": result,
    })


@app.route("/api/ai/exam-data", methods=["GET"])
def api_ai_exam_data():
    """获取当前缓存的考试数据"""
    cid = get_class_id_from_request()
    cached = _exam_data_cache.get(str(cid))
    if not cached:
        return jsonify({"code": 0, "data": None, "msg": "暂无考试数据"})
    return jsonify({"code": 0, "data": cached})


@app.route("/api/ai/exam-data/clear", methods=["POST"])
def api_ai_exam_data_clear():
    """清除缓存的考试数据"""
    cid = get_class_id_from_request()
    _exam_data_cache.pop(str(cid), None)
    return jsonify({"code": 0, "msg": "考试数据已清除"})


@app.route("/api/ai/import-exam/apply", methods=["POST"])
def api_ai_import_exam_apply():
    """将解析好的考试数据导入到 exam_scores 表（根据学号或姓名匹配学生）"""
    cid = get_class_id_from_request()
    db = get_db()
    cached = _exam_data_cache.get(str(cid))
    if not cached:
        return jsonify({"code": 1, "msg": "没有缓存的考试数据，请先上传 Excel"}), 400

    data = request.get_json() or {}
    target_class_name = data.get("class_name", "").strip()
    exam_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    exam_data = cached["data"]

    # 获取当前班级的所有学生
    all_students = db.execute(
        "SELECT id, name, student_code FROM students WHERE class_id=?", (cid,)
    ).fetchall()

    # 建立匹配索引：学号 → id, 姓名 → id
    code_to_id = {}
    name_to_id = {}
    for s in all_students:
        if s["student_code"]:
            code_to_id[s["student_code"].strip()] = s["id"]
        name_to_id[s["name"].strip()] = s["id"]

    matched = 0
    unmatched = []
    total = 0

    for cls in exam_data["classes"]:
        if target_class_name and cls.get("name", "") != target_class_name:
            continue
        exam_name = cls.get("name", "") or cached.get("source_file", "考试").rsplit(".", 1)[0]
        total_score = float(cls.get("total_score", 100))

        for s in cls["students"]:
            total += 1
            student_id = None

            # 优先用学号匹配
            if s.get("code") and s["code"] in code_to_id:
                student_id = code_to_id[s["code"]]
            elif s.get("name") in name_to_id:
                student_id = name_to_id[s["name"]]
            else:
                clean_name = s.get("name", "").replace(" ", "").replace("\t", "")
                for name, sid in name_to_id.items():
                    if name.replace(" ", "") == clean_name:
                        student_id = sid
                        break

            if student_id:
                score = float(s.get("score", 0)) if s.get("score") is not None else 0
                grade = s.get("grade", "")
                if not grade and total_score > 0:
                    pct = score / total_score * 100
                    if pct >= 90: grade = "A"
                    elif pct >= 75: grade = "B"
                    elif pct >= 60: grade = "C"
                    else: grade = "D"
                db.execute("""
                    INSERT INTO exam_scores (student_id, class_id, date, exam_name, score, total_score, grade, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ON CONFLICT DO UPDATE SET
                        score=excluded.score, total_score=excluded.total_score,
                        grade=excluded.grade, updated_at=datetime('now','localtime')
                """, (student_id, cid, exam_date, exam_name, score, total_score, grade))
                matched += 1
            else:
                unmatched.append({"name": s.get("name", ""),
                                  "reason": "未在系统中找到该学生（学号或姓名不匹配）"})

    db.commit()

    return jsonify({
        "code": 0,
        "msg": f"已导入 {matched} 条成绩（{exam_date}），{len(unmatched)} 条未匹配",
        "data": {
            "matched": matched,
            "unmatched_count": len(unmatched),
            "unmatched_preview": unmatched[:10],
            "total_processed": total,
            "date": exam_date,
        }
    })


# ---- AI 评语生成 ----
@app.route("/api/ai/comment/<int:sid>", methods=["GET"])
def api_ai_comment(sid: int):
    """为学生生成 AI 评语"""
    cid = get_class_id_from_request()
    db = get_db()
    config = _get_ai_config()

    # 获取学生信息
    student = db.execute(
        "SELECT s.*, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.id = ? AND s.class_id = ?",
        (sid, cid)
    ).fetchone()
    if not student:
        return jsonify({"code": 1, "msg": "学生不存在"}), 404

    # 获取近30天作业记录
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = db.execute("""
        SELECT h.date, h.grade FROM homework h
        WHERE h.student_id = ? AND h.date >= ?
        ORDER BY h.date DESC
    """, (sid, start_date)).fetchall()

    stats = {"A": 0, "B": 0, "C": 0, "L": 0, "X": 0}
    for r in rows:
        stats[r["grade"]] = stats.get(r["grade"], 0) + 1
    total = sum(stats.values())
    a_rate = round(stats["A"] / total * 100, 1) if total > 0 else 0
    submit_rate = round((total - stats["X"]) / total * 100, 1) if total > 0 else 0

    # 检测连续未交
    grades_list = [r["grade"] for r in rows]
    consecutive_x = 0
    for g in grades_list:
        if g == "X":
            consecutive_x += 1
        else:
            break

    # 构建 prompt
    student_info = f"""学生姓名: {student['name']}
所属分组: {student['group_name'] or '未分组'}
近30天记录数: {total} 次
A: {stats['A']}次, B: {stats['B']}次, C: {stats['C']}次, 请假: {stats['L']}次, 未交: {stats['X']}次
提交率: {submit_rate}%, A率: {a_rate}%"""

    if consecutive_x >= 2:
        student_info += f"\n⚠️ 已连续 {consecutive_x} 天未交作业"

    prompt = f"""请为以下学生写一段期末评语（50-80字），语气鼓励、建设性：

{student_info}

要求：使用中文，包含学生姓名，肯定优点，提出1-2条改进建议，适合发给家长。"""

    success, content = _call_llm(config, [
        {"role": "user", "content": prompt}
    ])

    if not success:
        return jsonify({"code": 1, "msg": content}), 500

    return jsonify({
        "code": 0,
        "data": {
            "student_name": student["name"],
            "comment": content.strip(),
            "stats": {
                "total": total, "A": stats["A"], "B": stats["B"],
                "C": stats["C"], "X": stats["X"],
                "a_rate": a_rate, "submit_rate": submit_rate,
                "consecutive_x": consecutive_x,
            }
        }
    })


# ---- 智能预警 API ----
@app.route("/api/ai/alerts", methods=["GET"])
def api_ai_alerts():
    """获取智能预警信息"""
    cid = get_class_id_from_request()
    db = get_db()

    alerts = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 连续未交 ≥3 天检测
    students = db.execute(
        "SELECT s.id, s.name, g.name as group_name FROM students s "
        "LEFT JOIN groups_info g ON s.group_id=g.id WHERE s.class_id=?",
        (cid,)
    ).fetchall()

    consecutive_missing = []
    for s in students:
        rows = db.execute("""
            SELECT h.date, h.grade FROM homework h
            WHERE h.student_id=?
            ORDER BY h.date DESC LIMIT 10
        """, (s["id"],)).fetchall()
        if len(rows) < 3:
            continue
        grades = [r["grade"] for r in rows]
        cx = 0
        for g in grades:
            if g == "X":
                cx += 1
            else:
                break
        if cx >= 3:
            consecutive_missing.append({
                "student_id": s["id"],
                "student_name": s["name"],
                "group_name": s["group_name"] or "未分组",
                "consecutive_days": cx,
            })

    if consecutive_missing:
        alerts.append({
            "level": "danger",
            "title": f"⚠️ {len(consecutive_missing)} 名学生连续未交作业 ≥3 天",
            "detail": f"包括: {', '.join(m['student_name'] for m in consecutive_missing[:5])}"
                       + ("..." if len(consecutive_missing) > 5 else ""),
            "type": "consecutive_missing",
            "students": consecutive_missing,
        })

    # 2. 近3天 A 率较前3天下降超30%
    total = db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (cid,)).fetchone()["c"]
    if total > 0:
        recent_a, recent_total = 0, 0
        prev_a, prev_total = 0, 0
        for i in range(3):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            a_cnt = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade='A' AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            day_total = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            recent_a += a_cnt
            recent_total += day_total
        for i in range(3, 6):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            a_cnt = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND h.grade='A' AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            day_total = db.execute("""
                SELECT COUNT(DISTINCT h.student_id) as c FROM homework h
                JOIN students s ON h.student_id=s.id
                WHERE h.date=? AND s.class_id=?
            """, (d, cid)).fetchone()["c"]
            prev_a += a_cnt
            prev_total += day_total

        recent_rate = recent_a / recent_total * 100 if recent_total > 0 else 0
        prev_rate = prev_a / prev_total * 100 if prev_total > 0 else 0

        if prev_rate > 0 and (prev_rate - recent_rate) / prev_rate > 0.3:
            drop_pct = round((prev_rate - recent_rate) / prev_rate * 100, 1)
            alerts.append({
                "level": "warning",
                "title": f"📉 近3天A率({recent_rate:.1f}%)较前3天({prev_rate:.1f}%)下降 {drop_pct}%",
                "detail": f"A率从 {prev_rate:.1f}% 降至 {recent_rate:.1f}%，降幅超过30%",
                "type": "a_rate_drop",
                "data": {"recent_rate": round(recent_rate, 1), "prev_rate": round(prev_rate, 1),
                         "drop_pct": drop_pct},
            })

    return jsonify({
        "code": 0,
        "data": {
            "has_alerts": len(alerts) > 0,
            "alerts": alerts,
            "checked_at": today,
        }
    })


# ---- 智能分组 API ----
@app.route("/api/ai/smart-groups", methods=["POST"])
def api_ai_smart_groups():
    """AI 智能均衡分组（基于近30天平均等级）"""
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    group_count = int(data.get("group_count", 6))
    if group_count < 2 or group_count > 20:
        return jsonify({"code": 1, "msg": "分组数量需在2-20之间"}), 400

    db = get_db()

    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # 获取所有学生及其近30天作业记录
    students = db.execute(
        "SELECT id, name FROM students WHERE class_id=? ORDER BY id", (cid,)
    ).fetchall()

    # 计算每个学生的平均得分
    student_scores = []
    for s in students:
        rows = db.execute("""
            SELECT h.grade FROM homework h
            WHERE h.student_id=? AND h.date >= ?
        """, (s["id"], start_date)).fetchall()
        if not rows:
            student_scores.append({
                "id": s["id"], "name": s["name"], "avg_score": 0, "count": 0,
            })
            continue
        score_map = {"A": 3, "B": 2, "C": 1, "X": 0}
        # 请假(L)不计入均分：请假当天不交作业属正常，不应拉低均分
        scores = [score_map.get(r["grade"], 0) for r in rows if r["grade"] != "L"]
        avg = round(sum(scores) / len(scores), 2) if scores else 0
        student_scores.append({
            "id": s["id"], "name": s["name"], "avg_score": avg, "count": len(scores),
        })

    # 按平均分降序排列
    student_scores.sort(key=lambda x: x["avg_score"], reverse=True)

    # 贪心算法：蛇形分配（S形）确保均衡
    groups = [[] for _ in range(group_count)]
    group_scores = [0.0] * group_count
    group_counts = [0] * group_count

    # 使用蛇形（zigzag）分配
    direction = 1
    idx = 0
    for student in student_scores:
        groups[idx].append(student)
        group_scores[idx] += student["avg_score"]
        group_counts[idx] += 1
        idx += direction
        if idx >= group_count:
            idx = group_count - 1
            direction = -1
        elif idx < 0:
            idx = 0
            direction = 1

    # 构建结果
    result_groups = []
    for i, g in enumerate(groups):
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        avg = round(group_scores[i] / group_counts[i], 2) if group_counts[i] > 0 else 0
        result_groups.append({
            "name": f"第{i+1}组",
            "color": color,
            "sort_order": i,
            "student_count": len(g),
            "avg_score": avg,
            "students": [{"id": s["id"], "name": s["name"], "avg_score": s["avg_score"]}
                         for s in g],
        })

    # 统计均衡程度
    if group_count > 0 and all(gs > 0 for gs in group_counts):
        max_avg = max(group_scores[i] / group_counts[i] for i in range(group_count) if group_counts[i] > 0)
        min_avg = min(group_scores[i] / group_counts[i] for i in range(group_count) if group_counts[i] > 0)
        balance = round(max_avg - min_avg, 2)
    else:
        balance = 0

    return jsonify({
        "code": 0,
        "msg": f"智能分组完成：{group_count} 个组，均衡度差异 {balance}",
        "data": {
            "group_count": group_count,
            "balance_score": balance,
            "groups": result_groups,
            "student_count": len(student_scores),
        }
    })


# ---- AI 分组应用 API（将智能分组应用到实际数据库） ----
@app.route("/api/ai/smart-groups/apply", methods=["POST"])
def api_ai_smart_groups_apply():
    """将智能分组结果应用到数据库"""
    cid = get_class_id_from_request()
    data = request.get_json() or {}
    groups = data.get("groups", [])
    if not groups:
        return jsonify({"code": 1, "msg": "缺少分组数据"}), 400

    db = get_db()

    # 清除旧分组
    db.execute("UPDATE students SET group_id = 0 WHERE class_id = ?", (cid,))
    db.execute("DELETE FROM groups_info WHERE class_id = ?", (cid,))

    # 创建新分组并分配学生
    for g in groups:
        db.execute(
            "INSERT INTO groups_info (name, color, sort_order, class_id) VALUES (?,?,?,?)",
            (g["name"], g["color"], g["sort_order"], cid)
        )
        new_gid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for s in g.get("students", []):
            db.execute("UPDATE students SET group_id = ? WHERE id = ? AND class_id = ?",
                       (new_gid, s["id"], cid))

    db.commit()
    return jsonify({"code": 0, "msg": f"智能分组已应用（{len(groups)} 组）"})


# ============================================================
# 页面路由
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# 启动入口
# ============================================================
def _ensure_single_instance():
    """Windows 命名互斥锁：防止用户重复双击启动多个实例抢端口/写库。
    返回 True 表示本进程是唯一实例；False 表示已有实例在运行。"""
    if not getattr(sys, 'frozen', False):
        return True  # 开发模式允许多实例，方便调试
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW(None, False, "ClassTrack_SingleInstance_Mutex")
        # use_last_error=True 时 get_last_error 才是可靠的（ctypes 调用间会覆盖）
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def main():
    print("=" * 60)
    print("  🎒 ClassTrack v1.5 - 班级作业分组管理系统")
    print("  面向中小学教师的班级作业管理工具")
    print("=" * 60)

    # ---- 单实例保护 ----
    if not _ensure_single_instance():
        import webbrowser
        webbrowser.open("https://localhost:5088")
        print("  ⚠️ ClassTrack 已在运行，本次启动已退出（请查看已打开的浏览器窗口）")
        if getattr(sys, 'frozen', False):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0, "ClassTrack 已经在运行中。\n\n请查看已打开的浏览器窗口继续使用。",
                    "ClassTrack", 0x40)
            except Exception:
                pass
        return

    # ---- 数据目录准备（含旧版数据自动迁移，放在 init_db 之前） ----
    try:
        if LEGACY_DATA_DIR is not None and LEGACY_DATA_DIR.exists():
            migrate_legacy_data(DATA_DIR, LEGACY_DATA_DIR)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  📁 数据目录: {DATA_DIR}")
    except Exception as e:
        _fatal(f"无法创建数据目录: {DATA_DIR}\n{e}\n\n"
               f"请将 ClassTrack.exe 移动到可写位置（如桌面）后重试。")
        return

    try:
        init_db()
        print(f"  ✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:

        print(f"  ❌ 数据库初始化失败: {e}")
        sys.exit(1)

    # ---- 激活状态检测 ----
    activation_ok = False
    if _ACTIVATION_AVAILABLE:
        try:
            result = verify_activation()
            activation_ok = result.activated
            if activation_ok:
                print(f"  ✅ 激活校验通过")
                print(f"  💻 机器码: {result.machine_code}")
            else:
                print(f"  🔒 未激活 — 需要导入激活文件解锁全部功能")
                print(f"  💻 机器码: {result.machine_code}")
                print(f"  ℹ️  原因: {result.reason}")
        except Exception as e:
            print(f"  ⚠️ 激活校验异常: {e}")
    else:
        print(f"  ⚠️ 激活模块未加载（开发模式）")
        activation_ok = True  # 模块不可用时放行

    port = 5088
    # ---- 证书管理：CA 根证书 + 服务器证书 ----
    ca_cert_file = DATA_DIR / "ca-cert.pem"
    ca_key_file = DATA_DIR / "ca-key.pem"
    cert_file = DATA_DIR / "cert.pem"
    key_file = DATA_DIR / "key.pem"

    def _get_local_ip():
        """获取本机局域网 IP"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _generate_ca():
        """生成 CA 根证书"""
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Root CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack"),
        ])
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                key_cert_sign=True, crl_sign=True, digital_signature=False,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        with open(ca_key_file, "wb") as f:
            f.write(ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        with open(ca_cert_file, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        return ca_key, ca_cert

    def _sign_server_cert(ca_key, ca_cert):
        """用 CA 签发服务器证书"""
        import ipaddress
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        local_ip = _get_local_ip()
        server_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Server"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack"),
        ])
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(server_subject)
            .issuer_name(ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    x509.IPAddress(ipaddress.IPv4Address(local_ip)),
                ]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        with open(key_file, "wb") as f:
            f.write(server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        with open(cert_file, "wb") as f:
            f.write(server_cert.public_bytes(serialization.Encoding.PEM))

    def _trust_ca_on_windows():
        """将 CA 证书添加到当前用户的 Windows 受信任根证书存储"""
        import subprocess
        try:
            result = subprocess.run(
                ["certutil", "-addstore", "-user", "Root", str(ca_cert_file)],
                capture_output=True, text=True, timeout=15,
            )
            return result.returncode == 0
        except Exception:
            return False

    if cert_file.exists() and key_file.exists():
        ssl_context = (str(cert_file), str(key_file))
        print(f"  🔒 HTTPS 已启用（使用已有证书）")
    else:
        try:
            # 生成或加载 CA
            if ca_cert_file.exists() and ca_key_file.exists():
                from cryptography import x509
                from cryptography.hazmat.primitives import serialization
                with open(ca_key_file, "rb") as f:
                    ca_key = serialization.load_pem_private_key(f.read(), password=None)
                with open(ca_cert_file, "rb") as f:
                    ca_cert = x509.load_pem_x509_certificate(f.read())
                print(f"  🔑 使用已有 CA 根证书签发服务器证书")
            else:
                ca_key, ca_cert = _generate_ca()
                print(f"  🔑 已生成 CA 根证书")

            _sign_server_cert(ca_key, ca_cert)
            print(f"  📜 已签发服务器证书（含 localhost + 本机IP）")

            # 自动信任 CA（Windows）
            if _trust_ca_on_windows():
                print(f"  ✅ CA 证书已添加到 Windows 受信任列表")
            else:
                print(f"  ⚠️ 未能自动信任 CA，桌面浏览器可能仍显示不安全")

            ssl_context = (str(cert_file), str(key_file))
        except ImportError:
            ssl_context = "adhoc"
            print(f"  ⚠️ 证书生成失败，使用临时证书")
        except Exception as e:
            ssl_context = "adhoc"
            print(f"  ⚠️ 证书生成失败: {e}")
    print(f"  📱 手机扫码地址: https://<本机IP>:{port}/mobile")
    print(f"  🌐 本地地址: https://localhost:{port}")
    print(f"  📋 按 Ctrl+C 停止服务")
    print("=" * 60)
    import webbrowser
    import threading
    def open_browser():
        import time
        time.sleep(1.5)
        if activation_ok:
            webbrowser.open(f"https://localhost:{port}")
        else:
            webbrowser.open(f"https://localhost:{port}/activation")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True, ssl_context=ssl_context)


if __name__ == "__main__":
    main()
