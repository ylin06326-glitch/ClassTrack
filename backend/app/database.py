# -*- coding: utf-8 -*-
"""
数据库连接与 schema 管理
========================
SQLite 本地嵌入式数据库。包含:
- 每请求连接管理(依赖注入)
- 初始建表(classes/students/groups_info/homework/homework_types/exam_scores/app_config/mobile_scans)
- 历史版本自动迁移(v1.0 无 class_id、v1.2 学号、v2.1 扁平化、v2.2 作业种类全局化)

与旧版 Flask 实现保持 schema/迁移逻辑完全一致,确保旧 data/ 目录可直接复用。
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import get_db_path

DB_PATH = get_db_path()

# 分组循环色(12 色马卡龙,与前端 --group-colors 一致)
GROUP_COLORS = [
    "#7EB5D6", "#E8A0BF", "#A8D5BA", "#F4C97E",
    "#C4B5D6", "#F0B8A0", "#8EC8C0", "#D4A8C8",
    "#9DC8E0", "#F2C8DA", "#B8D8C8", "#F8DCA0",
]


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """新建数据库连接(请求级)"""
    db = sqlite3.connect(
        str(db_path or DB_PATH),
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=5,
        # FastAPI 中同步依赖(get_db)在线程池线程创建连接,
        # 而 async 端点在事件循环线程使用它,关闭同线程检查避免
        # "SQLite objects created in a thread can only be used in that same thread"
        check_same_thread=False,
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


@contextmanager
def db_session():
    """上下文管理器:自动 commit/close,异常时回滚"""
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库 + 自动迁移(启动时调用一次)"""
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    # WAL 只在初始化时设置一次(每个连接都执行 journal_mode 会在并发下抢写锁)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")

    # 基础表结构(v2.2: homework_types 全局化)
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

    # ---- 自动迁移:兼容 v1.0 数据库 ----
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

    # v2.1: 数据结构扁平化 —— 移除 homework_type_id,合并重复记录
    # 仅对 v2.1 之前的旧数据库生效(v2.2+ 已用新 schema,跳过)
    schema_ver = _get_schema_version(db)
    cols_hw = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "homework_type_id" in cols_hw and schema_ver < "2.2":
        # 合并同一 (student_id, date) 的多条记录(不同 homework_type),保留最新
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

    # 确保 homework.tag 列存在(新建或迁移后的表都应有)
    cols_hw2 = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "tag" not in cols_hw2:
        db.execute("ALTER TABLE homework ADD COLUMN tag TEXT DEFAULT ''")

    # v2.1: homework_types 表(如果不存在则创建,兼容旧数据库;v2.2+ 跳过)
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

    # 给 homework 表添加 homework_type_id 列(如果不存在,v2.2+ 已包含在初始建表)
    cols_hw3 = [r[1] for r in db.execute("PRAGMA table_info(homework)").fetchall()]
    if "homework_type_id" not in cols_hw3:
        db.execute("ALTER TABLE homework ADD COLUMN homework_type_id INTEGER DEFAULT 0")

    # ---- v2.2 自动迁移:作业种类全局化 + 支持多类型同日记录 ----
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


def _get_schema_version(db) -> str:
    """读取当前数据库 schema 版本号"""
    try:
        row = db.execute(
            "SELECT value FROM app_config WHERE key='schema_version'"
        ).fetchone()
        return row["value"] if row else "0"
    except Exception:
        return "0"


def _migrate_v2_2(db) -> None:
    """v2.2 迁移:作业种类全局化 + homework 支持多类型同日记录"""
    # 检查是否需要迁移(homework_types 表是否有 class_id 列)
    try:
        cols_ht = [r[1] for r in db.execute("PRAGMA table_info(homework_types)").fetchall()]
    except Exception:
        return  # 表不存在,初始创建会处理
    types_migrated = "class_id" not in cols_ht

    db.execute("PRAGMA foreign_keys=OFF")
    try:
        if not types_migrated:
            print("[v2.2] 开始迁移:作业种类全局化...")

            # Step 1: 合并同名作业种类(保留最小 id)
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

            # Step 2: 重建 homework_types 表(移除 class_id)
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

        # Step 3: 修正 homework UNIQUE 约束(加入 homework_type_id)。
        # 注意不能用 sqlite_master.sql 判断——ALTER TABLE ADD COLUMN 会把列名
        # 追加进存储的 SQL,但 UNIQUE 约束仍是旧的,导致新库/旧库都可能带着
        # 错误的 UNIQUE(student_id, date) 逃过检测。改用 PRAGMA index_list
        # 检查真实约束;且 Step 3 独立于 homework_types 状态执行(历史版本
        # 存在「种类已迁移但约束未修复」的库,需单独补救)。
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
