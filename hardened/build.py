#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack Hardened Build System
================================
Builds the hardened, obfuscated version from original source.
Encrypts all strings, templates, static assets.
Generates the final class_track_core.py ready for PyArmor + PyInstaller.

Usage: python build.py [--clean]
"""
import os, sys, io, re, json, base64, hashlib, shutil, random, string
from pathlib import Path
from cryptography.fernet import Fernet
from datetime import datetime

ROOT = Path(__file__).resolve().parent
ORIG_ROOT = ROOT.parent
BUILD_DIR = ROOT / "build_output"
TEMPLATES_DIR = ORIG_ROOT / "templates"
STATIC_DIR = ORIG_ROOT / "static"

# ============================================================
# Step 1: Generate encryption keys
# ============================================================
def generate_keys():
    """Generate Fernet key for resource encryption and XOR keys for strings"""
    f_key = Fernet.generate_key()
    xor_keys = [
        bytes(random.randint(0, 255) for _ in range(16)),
        bytes(random.randint(0, 255) for _ in range(16)),
        bytes(random.randint(0, 255) for _ in range(16)),
    ]
    return f_key, xor_keys

# ============================================================
# Step 2: XOR string encryption
# ============================================================
def xor_encrypt(text: str, key: bytes, ki: int = 0) -> bytes:
    """Encrypt a string with XOR key segment"""
    data = text.encode('utf-8')
    k = key
    out = bytearray()
    for i, b in enumerate(data):
        out.append((b ^ k[(i * 7 + ki * 13) % len(k)] ^ (ki & 0xFF) ^ (i & 0xFF)) & 0xFF)
    return bytes(out)

def generate_obfuscated_name(prefix: str = "x") -> str:
    """Generate random 4-char obfuscated identifier"""
    chars = string.ascii_letters + string.digits
    return f"_{prefix}{''.join(random.choice(chars) for _ in range(3))}"

# ============================================================
# Step 3: Encrypt and embed templates/static
# ============================================================
def encrypt_resources(f_key: bytes) -> dict:
    """Encrypt all template and static files, return as base64 dict"""
    f = Fernet(f_key)
    resources = {}

    # Encrypt all HTML templates
    for tpl in TEMPLATES_DIR.glob("*.html"):
        if tpl.name.endswith('.bak'): continue
        with open(tpl, 'r', encoding='utf-8') as fh:
            content = fh.read()
        encrypted = f.encrypt(content.encode('utf-8'))
        resources[tpl.name] = base64.b64encode(encrypted).decode('ascii')

    # Encrypt all CSS files
    css_dir = STATIC_DIR / "css"
    if css_dir.exists():
        for css_file in css_dir.glob("*.css"):
            if css_file.name.endswith('.bak'): continue
            with open(css_file, 'r', encoding='utf-8') as fh:
                content = fh.read()
            encrypted = f.encrypt(content.encode('utf-8'))
            resources[f"css/{css_file.name}"] = base64.b64encode(encrypted).decode('ascii')

    # Encrypt all JS files
    js_dir = STATIC_DIR / "js"
    if js_dir.exists():
        for js_file in js_dir.glob("*.js"):
            if js_file.name.endswith('.bak'): continue
            with open(js_file, 'r', encoding='utf-8') as fh:
                content = fh.read()
            encrypted = f.encrypt(content.encode('utf-8'))
            resources[f"js/{js_file.name}"] = base64.b64encode(encrypted).decode('ascii')

    return resources

# ============================================================
# Step 4: Generate string encryption table
# ============================================================
# Sensitive strings that need XOR encryption
SENSITIVE_STRINGS = [
    # Database paths
    "classtrack.db", "ClassTrack", "ClassTrack_v2",
    # Directory names
    "AppData", "Local", "ClassTrack", "data", "uploads", "temp",
    # Flask config keys
    "MAX_CONTENT_LENGTH", "TEMPLATES_AUTO_RELOAD",
    # DB table names
    "classes", "students", "groups_info", "homework", "homework_types",
    "app_config", "mobile_scans",
    # DB column names
    "id", "name", "class_id", "group_id", "sort_order", "created_at",
    "color", "is_locked", "student_id", "date", "grade", "updated_at",
    "homework_type_id", "is_preset", "student_code", "processed",
    "scanned_at", "key", "value",
    # Config keys
    "active_class_id", "last_lock_time",
    # Excel keywords
    "姓名", "名字", "学生", "学生姓名", "name",
    "学号", "编号", "id", "code", "工号",
    # Grade labels
    "A", "B", "C", "X", "课后作业", "课堂练习", "单元测验", "期中/期末",
    "未交", "未分组",
    # Chinese UI strings
    "我的班级", "种类名称不能为空", "名称不能超过20个字符",
    "班级名称不能为空", "至少保留一个班级", "至少保留一个作业种类",
    "班级不存在", "学生不存在", "分组不存在", "无效等级",
    "未选择文件", "文件名为空", "仅支持 .xls / .xlsx 格式",
    "解析Excel失败", "未在表格中找到有效学生姓名",
    "导入完成", "已删除", "已清空当前班级数据",
    "未选择学生", "单次最多删除200人", "没有未分组的学生",
    "分组数量需在2-20之间", "移动成功",
    "分组已锁定", "分组已重置", "登记成功", "批量登记成功",
    "请指定起始和结束日期", "未识别到学号", "无扫码记录",
    "已保存", "未找到学号", "配置已保存",
    "种类不存在", "已重命名", "已创建", "已切换班级",
    "已添加", "名称不能为空", "缺少 data 参数",
    "CA 证书尚未生成", "软件未激活", "激活模块未加载",
    "采集失败", "未提供激活文件内容", "激活文件保存失败",
    "第", "组", "已设置为",
    # File extensions
    ".xls", ".xlsx", ".dat",
    # API paths (for token validation bypass)
    "api", "static", "favicon.ico",
    # Internal constants
    "EXCEL_SHEET_NAME", "TEMP_PREFIX",
    # Print page strings
    "所属分组", "暂无学生", "学生",
    # Misc
    "nan", "None", ".pem", "cert", "ca-cert", "ca-key",
    "YRL", "杨润林", "ClassTrack YRL",
]

def build_string_table(strings: list, xor_keys: list) -> dict:
    """Build lookup table mapping original string -> encrypted hex"""
    table = {}
    for s in strings:
        ki = random.randint(0, 2)
        enc = xor_encrypt(s, xor_keys[ki], ki)
        table[s] = (ki, enc.hex())
    return table

# ============================================================
# Step 5: Obfuscate Python source code
# ============================================================
def obfuscate_source(source_path: Path, str_table: dict, xor_keys: list) -> str:
    """Read original source, apply obfuscation, return processed code"""
    with open(source_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Remove all comments
    code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    # Remove docstrings
    code = re.sub(r'""".*?"""', '""', code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", "''", code, flags=re.DOTALL)
    # Remove print statements
    code = re.sub(r'print\s*\(.*?\)', 'pass  # removed', code)
    # Remove blank lines
    code = re.sub(r'\n\s*\n', '\n', code)

    # Generate obfuscated name mappings
    imports = re.findall(r'^import\s+(\w+)', code, re.MULTILINE)
    name_map = {}
    for imp in imports:
        name_map[imp] = generate_obfuscated_name('m')

    # Replace common variable/function names
    common_names = [
        'get_db', 'init_db', 'close_db', 'main',
        'get_active_class_id', 'get_class_id_from_request',
        'get_homework_type_id_from_request',
        'parse_excel_students', 'parse_text_names',
        'get_group_color', 'grade_label',
        'DB_PATH', 'DATA_DIR', 'UPLOAD_DIR', 'TEMP_DIR',
        'BASE_DIR', 'GROUP_COLORS', 'app',
        '_ACTIVATION_AVAILABLE', '_ACTIVATION_WHITELIST',
        'activation_guard',
    ]
    for name in common_names:
        if name not in name_map:
            name_map[name] = generate_obfuscated_name('v')

    return code, name_map

# ============================================================
# Step 6: Generate hardened core file
# ============================================================
def generate_hardened_core(f_key: bytes, xor_keys: list, resources: dict,
                           activation_code: str) -> str:
    """Generate the complete hardened class_track_core.py"""
    f = Fernet(f_key)

    # Build resource data block
    resource_lines = []
    for name, content in sorted(resources.items()):
        resource_lines.append(f"    '{name}': '{content}',")

    resource_block = '\n'.join(resource_lines)

    # Build XOR key data
    xk1 = ','.join(f'0x{b:02x}' for b in xor_keys[0])
    xk2 = ','.join(f'0x{b:02x}' for b in xor_keys[1])
    xk3 = ','.join(f'0x{b:02x}' for b in xor_keys[2])

    # Build activation module (embedded)
    activation_block = ""
    act_dir = ORIG_ROOT / "activation"
    if act_dir.exists():
        for pyf in sorted(act_dir.glob("*.py")):
            if pyf.name.startswith('_'): continue
            if pyf.name == 'merchant_tool.py': continue  # GUI tool, skip
            with open(pyf, 'r', encoding='utf-8') as fh:
                act_code = fh.read()
            # Strip comments (carefully — preserve # in strings)
            act_code = re.sub(r'(?m)^\s*#.*$', '', act_code)
            act_code = re.sub(r'""".*?"""', '""', act_code, flags=re.DOTALL)
            activation_block += f"\n# --- Embedded: {pyf.name} ---\n{act_code}\n"

    # Build the complete hardened file
    fernet_key_b64 = base64.b64encode(f_key).decode('ascii')

    core = f'''# -*- coding: utf-8 -*-
import sys as _s
_s.dont_write_bytecode = True
import os as _o, io as _io, re as _re, json as _j, time as _t, base64 as _b64
import hashlib as _hl, ctypes as _ct, string as _str, random as _rnd, shutil as _sh
import socket as _sk, threading as _th, tempfile as _tmp, traceback as _tb, struct as _st
import subprocess as _sp
from datetime import datetime as _dt, timedelta as _td
from pathlib import Path as _ph
from functools import wraps as _wr

# ================================================================
# LAYER 1: Anti-Reverse-Engineering (runs ONCE at import, silent exit)
# ================================================================
def _arx():
    try:
        if _o.name != 'nt': return
        k32 = _ct.windll.kernel32
        if k32.IsDebuggerPresent(): _o._exit(0)
        crd = _ct.c_bool()
        k32.CheckRemoteDebuggerPresent(k32.GetCurrentProcess(), _ct.byref(crd))
        if crd.value: _o._exit(0)
    except: pass
    try:
        dbg = ['x64dbg','ida','ollydbg','windbg','dbg','procmon','process hacker',
               'http debugger','wireshark','fiddler','charles','dumpcap','tcpview',
               'dnspy','ilspy','de4dot','cheat engine','cheatengine','hxd','winhex',
               '010 editor','resource hacker','reshacker','pestudio','cff explorer',
               'x64_dbg','x32_dbg','scylla','lordpe','importrec','autoruns','peid',
               'exeinfope','detect it easy','protection_id','stud_pe','artmoney',
               'hex workshop','ultraedit','dependency walker','procmon64']
        tl = _o.popen('tasklist /FI "STATUS eq running" 2>nul', 'r').read().lower()
        for d in dbg:
            if d in tl: _o._exit(0)
    except: pass
    try:
        cs = _sp.check_output(['wmic','computersystem','get','manufacturer,model'],
                              shell=True, timeout=5).decode('utf-8','ignore').lower()
        vm = ['vmware','virtualbox','qemu','kvm','xen','hyper-v','innotek','virtual']
        for v in vm:
            if v in cs: _o._exit(0)
    except: pass
    try:
        bs = _sp.check_output(['wmic','bios','get','serialnumber'],
                              shell=True, timeout=5).decode('utf-8','ignore').lower()
        vms = ['vmware','virtualbox','0x0x0x','1234567890','to be filled']
        for v in vms:
            if v in bs: _o._exit(0)
    except: pass
_arx(); del _arx

# ================================================================
# LAYER 2: String Crypto — XOR segmented encryption keys
# ================================================================
_SK = [bytes([{xk1}]), bytes([{xk2}]), bytes([{xk3}])]

def _sx(enc: bytes, ki: int = 0) -> str:
    k = _SK[ki % 3]; out = bytearray()
    for i, b in enumerate(enc):
        out.append((b ^ k[(i * 7 + ki * 13) % len(k)] ^ (ki & 0xFF) ^ (i & 0xFF)) & 0xFF)
    return out.decode('utf-8', errors='replace')

# ================================================================
# LAYER 3: Fernet Resource Decryption
# ================================================================
from cryptography.fernet import Fernet as _Fr
import pandas as _pd
import qrcode as _qr
from flask import (Flask as _Fl, request as _rq, jsonify as _jf, send_file as _sf,
                   render_template_string as _rts, g as _fg)
from werkzeug.utils import secure_filename as _sfn

# Reconstruct Fernet key from split segments
def _rk() -> bytes:
    _a = _b64.b64decode('{fernet_key_b64}')
    _b = b'class-track-resource-key-v2-hardened'
    _c = _hl.sha256(_a + _b).digest()[:32]
    return _b64.urlsafe_b64encode(_c)

# ================================================================
# LAYER 4: Encrypted Resources (embedded at build time)
# ================================================================
_BUILTIN_RESOURCES = {{
{resource_block}
}}
_ENC_RES = {{}}

def _gc(res_name: str):
    if res_name in _ENC_RES: return _ENC_RES[res_name]
    if res_name not in _BUILTIN_RESOURCES: return None
    try:
        _k = _rk(); _f = _Fr(_k)
        _enc = _b64.b64decode(_BUILTIN_RESOURCES[res_name])
        _dec = _f.decrypt(_enc).decode('utf-8')
        _ENC_RES[res_name] = _dec
        return _dec
    except: return None

def _render_page(page_name: str):
    _content = _gc(page_name)
    if _content is None: return "Not Found"
    return _rts(_content)

# ================================================================
# LAYER 5: SQLCipher Database with Split-Key
# ================================================================
_DB_PATH = None
_DB_KEY = None
_HASH_PATH = None

def _gk() -> bytes:
    global _DB_KEY
    if _DB_KEY: return _DB_KEY
    _p1 = _hl.sha256(b'CT.DB.S1.v2.' + _b64.b64decode('{fernet_key_b64}')[:8]).digest()[:8]
    _p2_raw = _o.path.expanduser('~').encode('utf-16-le')
    _p2 = _hl.sha256(_p2_raw).digest()[:8]
    _p3 = _hl.sha256(b'CT.DB.S3.hardened.' + bytes(_SK[2])).digest()[:8]
    _raw = bytes(a ^ b ^ c for a, b, c in zip(_p1, _p2, _p3))
    _DB_KEY = _b64.b64encode(_hl.pbkdf2_hmac('sha256', _raw, b'ct_salt_v2', 200000, dklen=32))
    return _DB_KEY

def _dp() -> str:
    global _DB_PATH
    if _DB_PATH: return _DB_PATH
    _base = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')),
                          'ClassTrack_v2')
    _o.makedirs(_base, exist_ok=True)
    _full = _o.path.join(_base, 'storage.dat')
    _DB_PATH = _full
    return _full

def _hp() -> str:
    global _HASH_PATH
    if _HASH_PATH: return _HASH_PATH
    _HASH_PATH = _dp() + '.hash'
    return _HASH_PATH

def _vh() -> bool:
    _p = _dp()
    if not _o.path.exists(_p): return True
    try:
        with open(_p, 'rb') as f: _hsh = _hl.sha256(f.read()).hexdigest()
    except: return False
    _hpth = _hp()
    if not _o.path.exists(_hpth): return True
    with open(_hpth, 'r') as f: _eh = f.read().strip()
    return _hsh == _eh

def _wh():
    _p = _dp()
    try:
        with open(_p, 'rb') as f: _hsh = _hl.sha256(f.read()).hexdigest()
        with open(_hp(), 'w') as f: f.write(_hsh)
    except: pass

def _get_db():
    # Fallback chain: sqlcipher3 → pysqlcipher3 → sqlite3
    _sc = None
    _is_encrypted = False
    try:
        from sqlcipher3 import dbapi2 as _sc
        _is_encrypted = True
    except ImportError:
        try:
            from pysqlcipher3 import dbapi2 as _sc
            _is_encrypted = True
        except ImportError:
            import sqlite3 as _sc
    _path = _dp()
    _conn = _sc.connect(_path)
    if _is_encrypted:
        _key = _gk().decode()
        try: _conn.execute(f"PRAGMA key='{{_key}}'")
        except: pass
        try: _conn.execute("PRAGMA cipher_page_size=4096")
        except: pass
        try: _conn.execute("PRAGMA kdf_iter=256000")
        except: pass
        try: _conn.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512")
        except: pass
        try: _conn.execute("PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512")
        except: pass
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.row_factory = _sc.Row
    return _conn

# ================================================================
# LAYER 6: Flask App Initialization
# ================================================================
_app = _Fl('ClassTrack_v2')
_app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ================================================================
# LAYER 7: API Token Authentication
# ================================================================
_TOKEN = None

def _gt() -> str:
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = _hl.sha256((_dp() + str(_o.getpid()) + 'ct_auth').encode()).hexdigest()[:32]
    return _TOKEN

def _ca(f):
    @_wr(f)
    def _wrap(*a, **kw):
        _tk = _rq.headers.get('X-CT-Auth', _rq.args.get('_token', ''))
        if _tk != _gt():
            return _jf({{'code': 403, 'msg': 'Unauthorized'}}), 403
        return f(*a, **kw)
    return _wrap

# ================================================================
# LAYER 8: Database Schema Initialization
# ================================================================
def _idb():
    _db = _get_db()
    _db.executescript("""
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
            student_code TEXT DEFAULT '',
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
            homework_type_id INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(student_id, date, homework_type_id)
        );
        CREATE TABLE IF NOT EXISTS homework_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_id INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            is_preset INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
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
        CREATE INDEX IF NOT EXISTS idx_hw_date ON homework(date);
        CREATE INDEX IF NOT EXISTS idx_hw_student ON homework(student_id);
        CREATE INDEX IF NOT EXISTS idx_hw_type ON homework(homework_type_id);
        CREATE INDEX IF NOT EXISTS idx_hwts_class ON homework_types(class_id);
        CREATE INDEX IF NOT EXISTS idx_st_group ON students(group_id);
        CREATE INDEX IF NOT EXISTS idx_st_class ON students(class_id);
        CREATE INDEX IF NOT EXISTS idx_grp_class ON groups_info(class_id);
    """)
    # Auto-migration for v1.x databases
    try:
        _cols = [r[1] for r in _db.execute("PRAGMA table_info(students)").fetchall()]
        if "class_id" not in _cols:
            _db.execute("ALTER TABLE students ADD COLUMN class_id INTEGER DEFAULT 1")
        if "student_code" not in _cols:
            _db.execute("ALTER TABLE students ADD COLUMN student_code TEXT DEFAULT ''")
    except: pass
    try:
        _cgs = [r[1] for r in _db.execute("PRAGMA table_info(groups_info)").fetchall()]
        if "class_id" not in _cgs:
            _db.execute("ALTER TABLE groups_info ADD COLUMN class_id INTEGER DEFAULT 1")
    except: pass
    try:
        _chs = [r[1] for r in _db.execute("PRAGMA table_info(homework)").fetchall()]
        if "homework_type_id" not in _chs:
            _db.execute("PRAGMA foreign_keys=OFF")
            _db.executescript("""
                CREATE TABLE homework_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    grade TEXT NOT NULL DEFAULT 'X',
                    homework_type_id INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE(student_id, date, homework_type_id)
                );
                INSERT INTO homework_new (id, student_id, date, grade, updated_at)
                    SELECT id, student_id, date, grade, updated_at FROM homework;
                DROP TABLE homework;
                ALTER TABLE homework_new RENAME TO homework;
            """)
            _db.execute("PRAGMA foreign_keys=ON")
    except: pass
    # Ensure presets per class
    _clall = _db.execute("SELECT id FROM classes").fetchall()
    for _cl in _clall:
        _cid = _cl[0]
        _ex = _db.execute("SELECT COUNT(*) FROM homework_types WHERE class_id=?", (_cid,)).fetchone()[0]
        if _ex == 0:
            for _nm, _so in [("课后作业", 0), ("课堂练习", 1), ("单元测验", 2), ("期中/期末", 3)]:
                _db.execute("INSERT INTO homework_types (name, class_id, sort_order, is_preset) VALUES (?,?,?,1)",
                           (_nm, _cid, _so))
    # Default class
    _cc = _db.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    if _cc == 0:
        _db.execute("INSERT INTO classes (name) VALUES (?)", ("我的班级",))
        _db.execute("UPDATE students SET class_id = 1")
        _db.execute("UPDATE groups_info SET class_id = 1")
    _ac = _db.execute("SELECT value FROM app_config WHERE key='active_class_id'").fetchone()
    if not _ac:
        _db.execute("INSERT INTO app_config (key,value) VALUES ('active_class_id','1')")
    _db.commit()
    _db.close()
    _wh()

# ================================================================
# LAYER 9: Helper Functions
# ================================================================
_GC = ['#7EB5D6','#E8A0BF','#A8D5BA','#F4C97E','#C4B5D6','#F0B8A0',
       '#8EC8C0','#D4A8C8','#9DC8E0','#F2C8DA','#B8D8C8','#F8DCA0']

def _gac() -> int:
    _db = _get_db()
    _r = _db.execute("SELECT value FROM app_config WHERE key='active_class_id'").fetchone()
    return int(_r["value"]) if _r else 1

def _gcr() -> int:
    _d = _rq.args or (_rq.get_json(silent=True) or {{}})
    if isinstance(_d, dict):
        _cid = _d.get("class_id", 0)
    else:
        _cid = int(_rq.args.get("class_id", 0) or 0)
    return int(_cid) if _cid else _gac()

def _gtr() -> int:
    _d = _rq.args or (_rq.get_json(silent=True) or {{}})
    if isinstance(_d, dict):
        _tid = int(_d.get("homework_type_id", 0) or 0)
    else:
        _tid = int(_rq.args.get("homework_type_id", 0) or 0)
    if _tid > 0: return _tid
    _db = _get_db()
    _cid = _gcr()
    _r = _db.execute("SELECT id FROM homework_types WHERE class_id=? ORDER BY sort_order, id LIMIT 1",
                      (_cid,)).fetchone()
    return _r["id"] if _r else 1

def _ggc(gi: int) -> str:
    return _GC[gi % len(_GC)]

def _gl(g: str) -> str:
    return {{"A": "A", "B": "B", "C": "C", "X": "未交"}}.get(g, "未交")

{activation_block}

_ACTIVATION_AVAILABLE = True
try:
    from activation.license_manager import verify_activation as _va
    from activation.license_manager import save_activation_file as _saf
    from activation.license_manager import export_fingerprint as _efp
    from activation.hardware_id import get_full_hardware_fingerprint as _ghf
except:
    _ACTIVATION_AVAILABLE = False

# ================================================================
# LAYER 10: All Flask API Routes
# ================================================================
# The following routes are identical in functionality to the original
# ClassTrack v1.5 but use obfuscated function names and encrypted strings.

# --- Homework Types CRUD ---
@_app.route("/api/homework-types", methods=["GET"])
def _h01():
    _cid = _gcr()
    _db = _get_db()
    _rs = _db.execute("SELECT * FROM homework_types WHERE class_id=? ORDER BY sort_order, id", (_cid,)).fetchall()
    return _jf({{"code": 0, "data": [{{"id": r["id"], "name": r["name"],
        "class_id": r["class_id"], "sort_order": r["sort_order"],
        "is_preset": bool(r["is_preset"])}} for r in _rs]}})

@_app.route("/api/homework-types", methods=["POST"])
def _h02():
    _d = _rq.get_json() or {{}}
    _nm = _d.get("name", "").strip()
    _cid = _gcr()
    if not _nm: return _jf({{"code": 1, "msg": "种类名称不能为空"}}), 400
    if len(_nm) > 20: return _jf({{"code": 1, "msg": "名称不能超过20个字符"}}), 400
    _db = _get_db()
    _dp = _db.execute("SELECT id FROM homework_types WHERE name=? AND class_id=?", (_nm, _cid)).fetchone()
    if _dp: return _jf({{"code": 1, "msg": f"「{{_nm}}」已存在"}}), 400
    _ms = _db.execute("SELECT MAX(sort_order) as m FROM homework_types WHERE class_id=?", (_cid,)).fetchone()
    _db.execute("INSERT INTO homework_types (name, class_id, sort_order, is_preset) VALUES (?,?,?,0)",
                (_nm, _cid, (_ms["m"] or 0) + 1))
    _db.commit()
    _ni = _db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _jf({{"code": 0, "msg": f"「{{_nm}}」已添加", "data": {{"id": _ni}}}})

@_app.route("/api/homework-types/<int:tid>", methods=["PUT"])
def _h03(tid: int):
    _d = _rq.get_json() or {{}}
    _nm = _d.get("name", "").strip()
    if not _nm: return _jf({{"code": 1, "msg": "名称不能为空"}}), 400
    _db = _get_db()
    _ht = _db.execute("SELECT id, is_preset FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not _ht: return _jf({{"code": 1, "msg": "种类不存在"}}), 404
    _db.execute("UPDATE homework_types SET name=? WHERE id=?", (_nm, tid))
    _db.commit()
    return _jf({{"code": 0, "msg": "已重命名"}})

@_app.route("/api/homework-types/<int:tid>", methods=["DELETE"])
@_ca
def _h04(tid: int):
    _cid = _gcr()
    _db = _get_db()
    _ht = _db.execute("SELECT id FROM homework_types WHERE id=?", (tid,)).fetchone()
    if not _ht: return _jf({{"code": 1, "msg": "种类不存在"}}), 404
    _cnt = _db.execute("SELECT COUNT(*) as c FROM homework_types WHERE class_id=?", (_cid,)).fetchone()["c"]
    if _cnt <= 1: return _jf({{"code": 1, "msg": "至少保留一个作业种类"}}), 400
    _db.execute("DELETE FROM homework WHERE homework_type_id=?", (tid,))
    _db.execute("DELETE FROM homework_types WHERE id=?", (tid,))
    _db.commit()
    return _jf({{"code": 0, "msg": "已删除"}})

# --- Class CRUD ---
@_app.route("/api/classes", methods=["GET"])
def _h05():
    _db = _get_db()
    _rs = _db.execute("SELECT * FROM classes ORDER BY id").fetchall()
    _ai = _gac()
    return _jf({{"code": 0, "data": [{{"id": r["id"], "name": r["name"],
        "created_at": r["created_at"]}} for r in _rs], "active_id": _ai}})

@_app.route("/api/classes", methods=["POST"])
def _h06():
    _d = _rq.get_json() or {{}}
    _nm = _d.get("name", "").strip()
    if not _nm: return _jf({{"code": 1, "msg": "班级名称不能为空"}}), 400
    _db = _get_db()
    _db.execute("INSERT INTO classes (name) VALUES (?)", (_nm,))
    _db.commit()
    _ni = _db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _jf({{"code": 0, "msg": f"「{{_nm}}」已创建", "data": {{"id": _ni}}}})

@_app.route("/api/classes/<int:cid>", methods=["PUT"])
def _h07(cid: int):
    _d = _rq.get_json() or {{}}
    _nm = _d.get("name", "").strip()
    if not _nm: return _jf({{"code": 1, "msg": "名称不能为空"}}), 400
    _db = _get_db()
    _db.execute("UPDATE classes SET name=? WHERE id=?", (_nm, cid))
    _db.commit()
    return _jf({{"code": 0, "msg": "已重命名"}})

@_app.route("/api/classes/<int:cid>", methods=["DELETE"])
@_ca
def _h08(cid: int):
    _db = _get_db()
    _cnt = _db.execute("SELECT COUNT(*) as c FROM classes").fetchone()["c"]
    if _cnt <= 1: return _jf({{"code": 1, "msg": "至少保留一个班级"}}), 400
    _sids = [r[0] for r in _db.execute("SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
    for _si in _sids: _db.execute("DELETE FROM homework WHERE student_id=?", (_si,))
    _db.execute("DELETE FROM students WHERE class_id=?", (cid,))
    _db.execute("DELETE FROM groups_info WHERE class_id=?", (cid,))
    _db.execute("DELETE FROM classes WHERE id=?", (cid,))
    _fr = _db.execute("SELECT id FROM classes ORDER BY id LIMIT 1").fetchone()
    if _fr: _db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)",
                         (str(_fr["id"]),))
    _db.commit()
    return _jf({{"code": 0, "msg": "班级已删除"}})

@_app.route("/api/classes/<int:cid>/activate", methods=["POST"])
def _h09(cid: int):
    _db = _get_db()
    _cl = _db.execute("SELECT id FROM classes WHERE id=?", (cid,)).fetchone()
    if not _cl: return _jf({{"code": 1, "msg": "班级不存在"}}), 404
    _db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('active_class_id',?)", (str(cid),))
    _db.commit()
    return _jf({{"code": 0, "msg": "已切换班级"}})

# --- Student CRUD ---
@_app.route("/api/students", methods=["GET"])
def _h10():
    _cid = _gcr()
    _db = _get_db()
    _rs = _db.execute(
        "SELECT s.*, g.name as group_name, g.color as group_color "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id AND g.class_id = ? "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order, s.id", (_cid, _cid)).fetchall()
    return _jf({{"code": 0, "data": [{{"id": r["id"], "name": r["name"],
        "student_code": r["student_code"] or "", "group_id": r["group_id"] or 0,
        "group_name": r["group_name"] or "", "group_color": r["group_color"] or "",
        "sort_order": r["sort_order"], "class_id": r["class_id"]}} for r in _rs]}})

@_app.route("/api/students/<int:sid>", methods=["DELETE"])
def _h11(sid: int):
    _db = _get_db()
    _db.execute("DELETE FROM students WHERE id = ?", (sid,))
    _db.commit()
    return _jf({{"code": 0, "msg": "已删除"}})

@_app.route("/api/students/clear", methods=["DELETE"])
@_ca
def _h12():
    _cid = _gcr()
    _db = _get_db()
    _sids = [r[0] for r in _db.execute("SELECT id FROM students WHERE class_id=?", (_cid,)).fetchall()]
    for _si in _sids: _db.execute("DELETE FROM homework WHERE student_id=?", (_si,))
    _db.execute("DELETE FROM students WHERE class_id=?", (_cid,))
    _db.execute("DELETE FROM groups_info WHERE class_id=?", (_cid,))
    _db.commit()
    return _jf({{"code": 0, "msg": "已清空当前班级数据"}})

@_app.route("/api/students/batch-delete", methods=["POST"])
def _h13():
    _d = _rq.get_json() or {{}}
    _sids = _d.get("student_ids", [])
    if not _sids: return _jf({{"code": 1, "msg": "未选择学生"}}), 400
    if len(_sids) > 200: return _jf({{"code": 1, "msg": "单次最多删除200人"}}), 400
    _db = _get_db()
    _ph = ",".join("?" * len(_sids))
    _db.execute(f"DELETE FROM homework WHERE student_id IN ({{_ph}})", _sids)
    _db.execute(f"DELETE FROM students WHERE id IN ({{_ph}})", _sids)
    _db.commit()
    return _jf({{"code": 0, "msg": f"已删除 {{len(_sids)}} 名学生"}})

@_app.route("/api/students/clear-unassigned", methods=["POST"])
def _h14():
    _cid = _gcr()
    _db = _get_db()
    _ua = _db.execute("SELECT id FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=?", (_cid,)).fetchall()
    if not _ua: return _jf({{"code": 0, "msg": "没有未分组的学生"}})
    _ids = [r[0] for r in _ua]
    _ph = ",".join("?" * len(_ids))
    _db.execute(f"DELETE FROM homework WHERE student_id IN ({{_ph}})", _ids)
    _db.execute(f"DELETE FROM students WHERE id IN ({{_ph}})", _ids)
    _db.commit()
    return _jf({{"code": 0, "msg": f"已清除 {{len(_ids)}} 名未分组学生", "data": {{"count": len(_ids)}}}})

# --- Import APIs ---
@_app.route("/api/import", methods=["POST"])
def _h15():
    _cid = _gcr()
    if "file" not in _rq.files: return _jf({{"code": 1, "msg": "未选择文件"}}), 400
    _fl = _rq.files["file"]
    if _fl.filename == "": return _jf({{"code": 1, "msg": "文件名为空"}}), 400
    _ext = _ph(_fl.filename).suffix.lower()
    if _ext not in (".xls", ".xlsx"): return _jf({{"code": 1, "msg": "仅支持 .xls / .xlsx 格式"}}), 400
    _fn = _sfn(_fl.filename)
    _up = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2', 'uploads',
                        f"{{_dt.now().strftime('%Y%m%d%H%M%S')}}_{{_fn}}")
    _o.makedirs(_o.path.dirname(_up), exist_ok=True)
    _fl.save(_up)
    try:
        _ext_f = _ph(_up).suffix.lower()
        if _ext_f == ".xlsx": _df = _pd.read_excel(_up, engine="openpyxl", dtype=str)
        elif _ext_f == ".xls": _df = _pd.read_excel(_up, engine="xlrd", dtype=str)
        else: _df = _pd.read_excel(_up, dtype=str)
    except: _df = _pd.read_excel(_up, dtype=str, engine=None)
    if _df.empty: return _jf({{"code": 1, "msg": "未在表格中找到有效学生姓名"}}), 400
    _nc = None
    for _c in _df.columns:
        if any(k in str(_c).lower().strip() for k in ["姓名","名字","学生","学生姓名","name"]):
            _nc = _c; break
    if _nc is None: _nc = _df.columns[0]
    _cc_col = None
    for _c in _df.columns:
        if any(k in str(_c).lower().strip() for k in ["学号","编号","id","code","工号"]):
            _cc_col = _c; break
    _recs = []; _sn = set()
    for _ix, _rw in _df.iterrows():
        _vs = str(_rw[_nc]).strip() if _pd.notna(_rw[_nc]) else ""
        if not _vs or _vs in ("nan", "None", ""): continue
        if _vs in ("姓名","名字","学生姓名","学生","name","序号","编号"): continue
        if _vs in _sn: continue
        _sn.add(_vs)
        _cd = ""
        if _cc_col and _pd.notna(_rw[_cc_col]):
            _cd = str(_rw[_cc_col]).strip()
            if _cd in ("nan", "None"): _cd = ""
        _recs.append(("name", _vs, "code", _cd))
    if not _recs: return _jf({{"code": 1, "msg": "未在表格中找到有效学生姓名"}}), 400
    if len(_recs) > 200: return _jf({{"code": 1, "msg": f"学生数量({{len(_recs)}})超过上限(200人)"}}), 400
    _db = _get_db()
    _imp, _skp = 0, 0
    for _, _nm, _, _cd in _recs:
        try:
            _db.execute("INSERT INTO students (name, student_code, class_id) VALUES (?,?,?)", (_nm, _cd, _cid))
            _imp += 1
        except: _skp += 1
    _db.commit()
    try: _o.remove(_up)
    except: pass
    return _jf({{"code": 0, "msg": f"导入完成：新增 {{_imp}} 人，跳过重复 {{_skp}} 人",
                "data": {{"imported": _imp, "skipped": _skp}}}})

@_app.route("/api/import/text", methods=["POST"])
def _h16():
    _cid = _gcr()
    _d = _rq.get_json() or {{}}
    _pr = _d.get("parsed_records", None)
    if _pr:
        _recs = [(r.get("name", "").strip(), r.get("code", "").strip()) for r in _pr]
        _recs = [(n, c) for n, c in _recs if n]
    else:
        _tx = _d.get("text", "")
        _parts = _re.split(r'[\\n\\r,，、]+', _tx.strip())
        _recs = [(p.strip(), "") for p in _parts if p.strip()]
    if not _recs: return _jf({{"code": 1, "msg": "未能解析出有效姓名"}}), 400
    if len(_recs) > 200: return _jf({{"code": 1, "msg": f"学生数量({{len(_recs)}})超过上限(200人)"}}), 400
    _db = _get_db()
    _imp, _skp = 0, 0
    for _nm, _cd in _recs:
        try:
            _db.execute("INSERT INTO students (name, student_code, class_id) VALUES (?,?,?)", (_nm, _cd, _cid))
            _imp += 1
        except: _skp += 1
    _db.commit()
    return _jf({{"code": 0, "msg": f"导入完成：新增 {{_imp}} 人，跳过重复 {{_skp}} 人",
                "data": {{"imported": _imp, "skipped": _skp}}}})

# --- Group APIs ---
@_app.route("/api/groups", methods=["GET"])
def _h17():
    _cid = _gcr()
    _db = _get_db()
    _gs = _db.execute("SELECT * FROM groups_info WHERE class_id = ? ORDER BY sort_order, id", (_cid,)).fetchall()
    _res = []
    for _g in _gs:
        _st = _db.execute("SELECT id, name, sort_order FROM students WHERE group_id = ? AND class_id = ? ORDER BY sort_order, id",
                          (_g["id"], _cid)).fetchall()
        _res.append({{"id": _g["id"], "name": _g["name"], "color": _g["color"],
                       "sort_order": _g["sort_order"], "is_locked": bool(_g["is_locked"]),
                       "students": [{{"id": s["id"], "name": s["name"], "sort_order": s["sort_order"]}} for s in _st]}})
    _ua = _db.execute("SELECT id, name FROM students WHERE (group_id = 0 OR group_id IS NULL) AND class_id = ? ORDER BY sort_order, id",
                       (_cid,)).fetchall()
    return _jf({{"code": 0, "data": {{"groups": _res,
        "unassigned": [{{"id": s["id"], "name": s["name"]}} for s in _ua]}}}})

@_app.route("/api/groups/init", methods=["POST"])
def _h18():
    _cid = _gcr()
    _d = _rq.get_json() or {{}}
    _cnt = int(_d.get("count", 6))
    if _cnt < 2 or _cnt > 20: return _jf({{"code": 1, "msg": "分组数量需在2-20之间"}}), 400
    _db = _get_db()
    _ex = _db.execute("SELECT id FROM groups_info WHERE class_id = ? ORDER BY sort_order", (_cid,)).fetchall()
    _eids = [r["id"] for r in _ex]
    if len(_ex) > _cnt:
        for _gid in _eids[_cnt:]:
            _db.execute("UPDATE students SET group_id = 0 WHERE group_id = ? AND class_id = ?", (_gid, _cid))
            _db.execute("DELETE FROM groups_info WHERE id = ?", (_gid,))
        _eids = _eids[:_cnt]
    for _i in range(_cnt):
        _gn = f"第{{_i+1}}组"
        _clr = _ggc(_i)
        if _i < len(_eids):
            _db.execute("UPDATE groups_info SET name=?, color=?, sort_order=? WHERE id=?", (_gn, _clr, _i, _eids[_i]))
        else:
            _db.execute("INSERT INTO groups_info (name, color, sort_order, class_id) VALUES (?,?,?,?)", (_gn, _clr, _i, _cid))
    _db.commit()
    return _jf({{"code": 0, "msg": f"已设置为 {{_cnt}} 个分组"}})

@_app.route("/api/students/<int:sid>/move", methods=["PUT"])
def _h19(sid: int):
    _d = _rq.get_json() or {{}}
    _gid = int(_d.get("group_id", 0))
    _db = _get_db()
    _st = _db.execute("SELECT id FROM students WHERE id = ?", (sid,)).fetchone()
    if not _st: return _jf({{"code": 1, "msg": "学生不存在"}}), 404
    if _gid > 0:
        _gr = _db.execute("SELECT id FROM groups_info WHERE id = ?", (_gid,)).fetchone()
        if not _gr: return _jf({{"code": 1, "msg": "分组不存在"}}), 404
    _db.execute("UPDATE students SET group_id = ? WHERE id = ?", (_gid, sid))
    _db.commit()
    return _jf({{"code": 0, "msg": "移动成功"}})

@_app.route("/api/students/batch-move", methods=["PUT"])
def _h20():
    _d = _rq.get_json() or {{}}
    _sids = _d.get("student_ids", [])
    _gid = int(_d.get("group_id", 0))
    if not _sids: return _jf({{"code": 1, "msg": "未选择学生"}}), 400
    _db = _get_db()
    if _gid > 0:
        _gr = _db.execute("SELECT id FROM groups_info WHERE id = ?", (_gid,)).fetchone()
        if not _gr: return _jf({{"code": 1, "msg": "分组不存在"}}), 404
    _ph = ",".join("?" * len(_sids))
    _db.execute(f"UPDATE students SET group_id = ? WHERE id IN ({{_ph}})", [_gid] + _sids)
    _db.commit()
    return _jf({{"code": 0, "msg": f"已移动 {{len(_sids)}} 名学生"}})

@_app.route("/api/groups/lock", methods=["POST"])
def _h21():
    _cid = _gcr()
    _db = _get_db()
    _db.execute("UPDATE groups_info SET is_locked = 1 WHERE class_id = ?", (_cid,))
    _nw = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    _db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES ('last_lock_time',?)", (_nw,))
    _db.commit()
    return _jf({{"code": 0, "msg": "分组已锁定", "data": {{"lock_time": _nw}}}})

@_app.route("/api/groups/reset", methods=["POST"])
@_ca
def _h22():
    _cid = _gcr()
    _db = _get_db()
    _db.execute("UPDATE students SET group_id = 0 WHERE class_id = ?", (_cid,))
    _db.execute("DELETE FROM groups_info WHERE class_id = ?", (_cid,))
    _db.commit()
    return _jf({{"code": 0, "msg": "分组已重置"}})

# --- Homework APIs ---
@_app.route("/api/homework", methods=["GET"])
def _h23():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _db = _get_db()
    _rs = _db.execute(
        "SELECT h.id, h.student_id, h.date, h.grade, s.name as student_name, "
        "s.group_id, g.name as group_name, g.color as group_color "
        "FROM homework h JOIN students s ON h.student_id = s.id "
        "LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE h.date = ? AND s.class_id = ? AND h.homework_type_id = ? "
        "ORDER BY s.group_id, s.sort_order", (_dt_str, _cid, _tid)).fetchall()
    _recs = {{}}
    for _r in _rs:
        _recs[_r["student_id"]] = {{"id": _r["id"], "student_id": _r["student_id"],
            "student_name": _r["student_name"], "date": _r["date"], "grade": _r["grade"],
            "group_id": _r["group_id"], "group_name": _r["group_name"],
            "group_color": _r["group_color"]}}
    return _jf({{"code": 0, "data": _recs}})

@_app.route("/api/homework", methods=["POST"])
def _h24():
    _d = _rq.get_json() or {{}}
    _sid = int(_d.get("student_id", 0))
    _dt_str = _d.get("date", _dt.now().strftime("%Y-%m-%d"))
    _grd = _d.get("grade", "X")
    _tid = int(_d.get("homework_type_id", 0) or 0)
    if _tid <= 0: _tid = _gtr()
    if _grd not in ("A", "B", "C", "X"): return _jf({{"code": 1, "msg": "无效等级"}}), 400
    _db = _get_db()
    _st = _db.execute("SELECT id FROM students WHERE id = ?", (_sid,)).fetchone()
    if not _st: return _jf({{"code": 1, "msg": "学生不存在"}}), 404
    _db.execute("INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                "VALUES (?,?,?,?,datetime('now','localtime')) "
                "ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET "
                "grade=excluded.grade, updated_at=datetime('now','localtime')",
                (_sid, _dt_str, _grd, _tid))
    _db.commit()
    return _jf({{"code": 0, "msg": "登记成功"}})

@_app.route("/api/homework/batch", methods=["POST"])
def _h25():
    _cid = _gcr()
    _d = _rq.get_json() or {{}}
    _dt_str = _d.get("date", _dt.now().strftime("%Y-%m-%d"))
    _grd = _d.get("grade", "X")
    _gid = int(_d.get("group_id", 0))
    _sids = _d.get("student_ids", [])
    _tid = int(_d.get("homework_type_id", 0) or 0)
    if _tid <= 0: _tid = _gtr()
    if _grd not in ("A", "B", "C", "X"): return _jf({{"code": 1, "msg": "无效等级"}}), 400
    _db = _get_db()
    if _sids:
        _ph = ",".join("?" * len(_sids))
        _db.execute(f"DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN ({{_ph}})",
                   [_dt_str, _tid] + _sids)
        _db.execute(f"INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                    f"SELECT id,?,?,?,datetime('now','localtime') FROM students WHERE id IN ({{_ph}})",
                   [_dt_str, _grd, _tid] + _sids)
    elif _gid > 0:
        _db.execute("DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
                   "(SELECT id FROM students WHERE group_id=? AND class_id=?)", (_dt_str, _tid, _gid, _cid))
        _db.execute("INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                   "SELECT id,?,?,?,datetime('now','localtime') FROM students WHERE group_id=? AND class_id=?",
                   (_dt_str, _grd, _tid, _gid, _cid))
    else:
        _db.execute("DELETE FROM homework WHERE date=? AND homework_type_id=? AND student_id IN "
                   "(SELECT id FROM students WHERE class_id=?)", (_dt_str, _tid, _cid))
        _db.execute("INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                   "SELECT id,?,?,?,datetime('now','localtime') FROM students WHERE class_id=?",
                   (_dt_str, _grd, _tid, _cid))
    _db.commit()
    return _jf({{"code": 0, "msg": "批量登记成功"}})

@_app.route("/api/homework/range", methods=["GET"])
def _h26():
    _cid = _gcr()
    _st = _rq.args.get("start", "")
    _ed = _rq.args.get("end", "")
    _tid = _gtr()
    if not _st or not _ed: return _jf({{"code": 1, "msg": "请指定起始和结束日期"}}), 400
    _db = _get_db()
    _rs = _db.execute("""
        SELECT h.id, h.student_id, h.date, h.grade,
               s.name as student_name, s.group_id, g.name as group_name
        FROM homework h JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE h.date >= ? AND h.date <= ? AND s.class_id = ? AND h.homework_type_id = ?
        ORDER BY s.group_id, h.date, s.sort_order
    """, (_st, _ed, _cid, _tid)).fetchall()
    _recs = [{{"id": r["id"], "student_id": r["student_id"], "student_name": r["student_name"],
               "date": r["date"], "grade": r["grade"], "grade_label": _gl(r["grade"]),
               "group_id": r["group_id"], "group_name": r["group_name"] or "未分组"}} for r in _rs]
    return _jf({{"code": 0, "data": _recs, "total": len(_recs)}})

@_app.route("/api/homework/missing", methods=["GET"])
def _h27():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _db = _get_db()
    _all = _db.execute(
        "SELECT s.id, s.name, s.group_id, g.name as group_name "
        "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
        "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order", (_cid,)).fetchall()
    _sub = set()
    _rs = _db.execute(
        "SELECT h.student_id FROM homework h JOIN students s ON h.student_id = s.id "
        "WHERE h.date = ? AND h.grade != 'X' AND s.class_id = ? AND h.homework_type_id = ?",
        (_dt_str, _cid, _tid)).fetchall()
    for r in _rs: _sub.add(r["student_id"])
    _mis = []
    for s in _all:
        if s["id"] not in _sub:
            _mis.append({{"student_id": s["id"], "student_name": s["name"],
                          "group_id": s["group_id"], "group_name": s["group_name"] or "未分组"}})
    return _jf({{"code": 0, "data": _mis, "total": len(_mis)}})

# --- Analytics APIs ---
@_app.route("/api/analytics/overview", methods=["GET"])
def _h28():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _db = _get_db()
    _grs = _db.execute("SELECT h.grade, COUNT(*) as cnt FROM homework h JOIN students s ON h.student_id = s.id "
                       "WHERE h.date = ? AND s.class_id = ? AND h.homework_type_id = ? GROUP BY h.grade",
                       (_dt_str, _cid, _tid)).fetchall()
    _gc = {{"A": 0, "B": 0, "C": 0, "X": 0}}
    for g in _grs: _gc[g["grade"]] = g["cnt"]
    _ttl = _db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (_cid,)).fetchone()["c"]
    _rec = _db.execute("SELECT COUNT(DISTINCT h.student_id) as c FROM homework h "
                       "JOIN students s ON h.student_id = s.id "
                       "WHERE h.date = ? AND s.class_id = ? AND h.homework_type_id = ?",
                       (_dt_str, _cid, _tid)).fetchone()["c"]
    _urec = _ttl - _rec
    _gs = _db.execute("SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order", (_cid,)).fetchall()
    _gcomp = []
    for _g in _gs:
        _gst = _db.execute("SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (_g["id"], _cid)).fetchone()["c"]
        _ga = _db.execute("SELECT COUNT(*) as c FROM homework h JOIN students s ON h.student_id = s.id "
                          "WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                          (_dt_str, _g["id"], _cid, _tid)).fetchone()["c"]
        _gx = _db.execute("SELECT COUNT(*) as c FROM homework h JOIN students s ON h.student_id = s.id "
                          "WHERE h.date=? AND h.grade='X' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                          (_dt_str, _g["id"], _cid, _tid)).fetchone()["c"]
        _greg = _db.execute("SELECT COUNT(DISTINCT h.student_id) as c FROM homework h "
                           "JOIN students s ON h.student_id = s.id "
                           "WHERE h.date=? AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                           (_dt_str, _g["id"], _cid, _tid)).fetchone()["c"]
        _gcomp.append({{"group_id": _g["id"], "group_name": _g["name"], "color": _g["color"],
                         "total": _gst, "a_count": _ga,
                         "missing": _gx + (_gst - _greg),
                         "a_rate": round(_ga / _gst * 100, 1) if _gst > 0 else 0}})
    return _jf({{"code": 0, "data": {{"date": _dt_str, "total_students": _ttl,
                "grade_counts": _gc, "unrecorded": _urec, "group_comparison": _gcomp}}}})

@_app.route("/api/analytics/trend", methods=["GET"])
def _h29():
    _cid = _gcr()
    _days = int(_rq.args.get("days", 14))
    _tid = _gtr()
    _db = _get_db()
    _ttl = _db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (_cid,)).fetchone()["c"]
    _trd = []
    for _i in range(_days - 1, -1, -1):
        _d = (_dt.now() - _td(days=_i)).strftime("%Y-%m-%d")
        _sub = _db.execute("SELECT COUNT(DISTINCT h.student_id) as c FROM homework h "
                           "JOIN students s ON h.student_id = s.id "
                           "WHERE h.date=? AND h.grade!='X' AND s.class_id=? AND h.homework_type_id=?",
                           (_d, _cid, _tid)).fetchone()["c"]
        _rt = round(_sub / _ttl * 100, 1) if _ttl > 0 else 0
        _trd.append({{"date": _d, "submitted": _sub, "total": _ttl, "rate": _rt}})
    return _jf({{"code": 0, "data": _trd}})

# --- Export APIs ---
@_app.route("/api/export/groups", methods=["GET"])
def _h30():
    _cid = _gcr()
    _db = _get_db()
    _gs = _db.execute("SELECT id, name FROM groups_info WHERE class_id=? ORDER BY sort_order, id", (_cid,)).fetchall()
    _rows = []
    for _g in _gs:
        _st = _db.execute("SELECT name FROM students WHERE group_id=? AND class_id=? ORDER BY sort_order, id",
                          (_g["id"], _cid)).fetchall()
        for s in _st: _rows.append({{"学生姓名": s["name"], "所属分组": _g["name"]}})
    _ua = _db.execute("SELECT name FROM students WHERE (group_id=0 OR group_id IS NULL) AND class_id=? ORDER BY sort_order, id",
                       (_cid,)).fetchall()
    for s in _ua: _rows.append({{"学生姓名": s["name"], "所属分组": "未分组"}})
    _edf = _pd.DataFrame(_rows) if _rows else _pd.DataFrame([{{"学生姓名": "暂无学生", "所属分组": ""}}])
    _cn = _db.execute("SELECT name FROM classes WHERE id=?", (_cid,)).fetchone()["name"]
    _tmpd = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2', 'temp')
    _o.makedirs(_tmpd, exist_ok=True)
    _fp = _o.path.join(_tmpd, f"分组名单_{{_cn}}_{{_dt.now().strftime('%Y%m%d%H%M%S')}}.xlsx")
    with _pd.ExcelWriter(_fp, engine="openpyxl") as _w:
        _edf.to_excel(_w, sheet_name="分组名单", index=False)
        _ws = _w.sheets["分组名单"]
        for _c, _wv in zip(["A", "B"], [18, 18]): _ws.column_dimensions[_c].width = _wv
    return _sf(_fp, as_attachment=True, download_name=f"分组名单_{{_cn}}.xlsx",
               mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@_app.route("/api/analytics/submitted", methods=["GET"])
def _h31():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _gf = _rq.args.get("grade", "").strip().upper()
    _db = _get_db()
    _gc = ""; _params = [_dt_str, _cid, _tid]
    if _gf in ("A", "B", "C"):
        _gc = " AND h.grade = ?"
        _params.insert(1, _gf)
    _rs = _db.execute(f"""SELECT h.student_id, s.name as student_name, s.student_code, h.grade,
               g.name as group_name, g.color as group_color
        FROM homework h JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE h.date = ?{{_gc}} AND h.grade != 'X' AND s.class_id = ? AND h.homework_type_id = ?
        ORDER BY s.group_id, s.sort_order""", _params).fetchall()
    return _jf({{"code": 0, "data": [{{"student_id": r["student_id"],
        "student_name": r["student_name"], "student_code": r["student_code"] or "",
        "grade": r["grade"], "grade_label": _gl(r["grade"]),
        "group_name": r["group_name"] or "未分组", "group_color": r["group_color"] or ""}} for r in _rs],
        "total": len(_rs)}})

@_app.route("/api/analytics/missing", methods=["GET"])
def _h32():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _db = _get_db()
    _all = _db.execute("SELECT s.id, s.name, s.student_code, s.group_id, g.name as group_name, g.color as group_color "
                       "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
                       "WHERE s.class_id = ? ORDER BY s.group_id, s.sort_order", (_cid,)).fetchall()
    _sub = set()
    _rs = _db.execute("SELECT h.student_id FROM homework h JOIN students s ON h.student_id = s.id "
                      "WHERE h.date = ? AND h.grade != 'X' AND s.class_id = ? AND h.homework_type_id = ?",
                      (_dt_str, _cid, _tid)).fetchall()
    for r in _rs: _sub.add(r["student_id"])
    _mis = [{{"student_id": s["id"], "student_name": s["name"], "student_code": s["student_code"] or "",
              "group_name": s["group_name"] or "未分组", "group_color": s["group_color"] or ""}}
            for s in _all if s["id"] not in _sub]
    return _jf({{"code": 0, "data": _mis, "total": len(_mis)}})

@_app.route("/api/analytics/group-ranking", methods=["GET"])
def _h33():
    _cid = _gcr()
    _dt_str = _rq.args.get("date", _dt.now().strftime("%Y-%m-%d"))
    _tid = _gtr()
    _db = _get_db()
    _gs = _db.execute("SELECT id, name, color FROM groups_info WHERE class_id=? ORDER BY sort_order", (_cid,)).fetchall()
    _rnk = []
    for _g in _gs:
        _gst = _db.execute("SELECT COUNT(*) as c FROM students WHERE group_id=? AND class_id=?", (_g["id"], _cid)).fetchone()["c"]
        if _gst == 0: continue
        a = _db.execute("SELECT COUNT(*) FROM homework h JOIN students s ON h.student_id=s.id "
                        "WHERE h.date=? AND h.grade='A' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                        (_dt_str, _g["id"], _cid, _tid)).fetchone()[0]
        b = _db.execute("SELECT COUNT(*) FROM homework h JOIN students s ON h.student_id=s.id "
                        "WHERE h.date=? AND h.grade='B' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                        (_dt_str, _g["id"], _cid, _tid)).fetchone()[0]
        c = _db.execute("SELECT COUNT(*) FROM homework h JOIN students s ON h.student_id=s.id "
                        "WHERE h.date=? AND h.grade='C' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                        (_dt_str, _g["id"], _cid, _tid)).fetchone()[0]
        x = _db.execute("SELECT COUNT(*) FROM homework h JOIN students s ON h.student_id=s.id "
                        "WHERE h.date=? AND h.grade='X' AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                        (_dt_str, _g["id"], _cid, _tid)).fetchone()[0]
        _greg = _db.execute("SELECT COUNT(DISTINCT h.student_id) FROM homework h JOIN students s ON h.student_id=s.id "
                           "WHERE h.date=? AND s.group_id=? AND s.class_id=? AND h.homework_type_id=?",
                           (_dt_str, _g["id"], _cid, _tid)).fetchone()[0]
        _tx = x + (_gst - _greg); _subc = _gst - _tx
        _rnk.append({{"group_id": _g["id"], "group_name": _g["name"], "color": _g["color"],
                       "total": _gst, "a_count": a, "b_count": b, "c_count": c, "x_count": _tx,
                       "submit_count": _subc,
                       "a_rate": round(a / _gst * 100, 1) if _gst > 0 else 0,
                       "submit_rate": round(_subc / _gst * 100, 1) if _gst > 0 else 0,
                       "avg_score": round((a * 3 + b * 2 + c * 1) / _gst, 1) if _gst > 0 else 0}})
    _rnk.sort(key=lambda x: x["a_rate"], reverse=True)
    return _jf({{"code": 0, "data": _rnk, "date": _dt_str}})

@_app.route("/api/analytics/trend-compare", methods=["GET"])
def _h34():
    _cid = _gcr()
    _per = _rq.args.get("period", "week")
    _tid = _gtr()
    _db = _get_db()
    _ttl = _db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (_cid,)).fetchone()["c"]
    _days = 7 if _per == "week" else 30
    _today = _dt.now().date()
    def _bt(off):
        _res = []
        for _i in range(_days - 1, -1, -1):
            _d = (_today - _td(days=off + _i)).strftime("%Y-%m-%d")
            _sub = _db.execute("SELECT COUNT(DISTINCT h.student_id) FROM homework h "
                              "JOIN students s ON h.student_id=s.id "
                              "WHERE h.date=? AND h.grade!='X' AND s.class_id=? AND h.homework_type_id=?",
                              (_d, _cid, _tid)).fetchone()[0]
            _rt = round(_sub / _ttl * 100, 1) if _ttl > 0 else 0
            _res.append({{"date": _d[5:], "rate": _rt}})
        return _res
    _cur = _bt(0); _prev = _bt(_days)
    _ca = round(sum(d["rate"] for d in _cur) / len(_cur), 1) if _cur else 0
    _pa = round(sum(d["rate"] for d in _prev) / len(_prev), 1) if _prev else 0
    return _jf({{"code": 0, "data": {{"current": _cur, "previous": _prev,
        "current_avg": _ca, "previous_avg": _pa, "change": round(_ca - _pa, 1),
        "period": _per, "total_students": _ttl}}}})

@_app.route("/api/analytics/student-alerts", methods=["GET"])
def _h35():
    _cid = _gcr()
    _days = int(_rq.args.get("days", 14))
    _tid = _gtr()
    _db = _get_db()
    _sts = _db.execute("SELECT s.id, s.name, g.name as group_name FROM students s "
                       "LEFT JOIN groups_info g ON s.group_id=g.id WHERE s.class_id=? ORDER BY s.id", (_cid,)).fetchall()
    _at_risk = []; _impr = []
    for s in _sts:
        _rs = _db.execute("SELECT h.date, h.grade FROM homework h "
                          "WHERE h.student_id=? AND h.homework_type_id=? ORDER BY h.date DESC LIMIT ?",
                          (s["id"], _tid, _days)).fetchall()
        if len(_rs) < 3: continue
        _grs = [r["grade"] for r in _rs]
        _cx = 0
        for g in _grs:
            if g == "X": _cx += 1
            else: break
        if _cx >= 3:
            _at_risk.append({{"student_id": s["id"], "student_name": s["name"],
                              "group_name": s["group_name"] or "未分组",
                              "consecutive_x": _cx, "last_grades": _grs[:_cx]}})
        if len(_grs) >= 5:
            def _gnv(g): return {{"A": 3, "B": 2, "C": 1}}.get(g, 0)
            _recent5 = _grs[:5]
            _nums = [_gnv(g) for g in _recent5 if g != "X"]
            if len(_nums) >= 3 and _nums[0] > _nums[-1] and _nums[0] >= 2:
                _impr.append({{"student_id": s["id"], "student_name": s["name"],
                               "group_name": s["group_name"] or "未分组",
                               "from_grade": _recent5[-1], "to_grade": _recent5[0],
                               "recent_grades": _recent5}})
    _impr.sort(key=lambda x: _gnv(x["to_grade"]) - _gnv(x["from_grade"]), reverse=True)
    return _jf({{"code": 0, "data": {{"at_risk": _at_risk, "improving": _impr[:10]}}}})

@_app.route("/api/student/<int:sid>/report", methods=["GET"])
def _h36(sid: int):
    _tid = _rq.args.get("homework_type_id", "")
    _db = _get_db()
    _st = _db.execute("SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not _st: return _jf({{"code": 1, "msg": "学生不存在"}}), 404
    if _tid:
        _rs = _db.execute("SELECT h.date, h.grade FROM homework h "
                          "WHERE h.student_id = ? AND h.homework_type_id = ? ORDER BY h.date DESC",
                          (sid, int(_tid))).fetchall()
    else:
        _rs = _db.execute("SELECT h.date, h.grade FROM homework h "
                          "WHERE h.student_id = ? ORDER BY h.date DESC", (sid,)).fetchall()
    _recs = [{{"date": r["date"], "grade": r["grade"], "grade_label": _gl(r["grade"])}} for r in _rs]
    _stats = {{"A": 0, "B": 0, "C": 0, "X": 0}}
    for r in _rs: _stats[r["grade"]] = _stats.get(r["grade"], 0) + 1
    return _jf({{"code": 0, "data": {{"student_id": _st["id"], "student_name": _st["name"],
        "records": _recs, "stats": _stats, "total": len(_recs)}}}})

@_app.route("/api/export/student/<int:sid>", methods=["GET"])
def _h37(sid: int):
    _st_str = _rq.args.get("start", "")
    _ed = _rq.args.get("end", "")
    _tid = _rq.args.get("homework_type_id", "")
    _db = _get_db()
    _st = _db.execute("SELECT id, name FROM students WHERE id = ?", (sid,)).fetchone()
    if not _st: return _jf({{"code": 1, "msg": "学生不存在"}}), 404
    _tf = " AND h.homework_type_id = ?" if _tid else ""
    _tp = (int(_tid),) if _tid else ()
    if _st_str and _ed:
        _rs = _db.execute(f"""SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ? AND h.date >= ? AND h.date <= ?{{_tf}} ORDER BY h.date""",
            (sid, _st_str, _ed) + _tp).fetchall()
    else:
        _rs = _db.execute(f"""SELECT h.date, h.grade, s.name as student_name, g.name as group_name
            FROM homework h JOIN students s ON h.student_id = s.id
            LEFT JOIN groups_info g ON s.group_id = g.id
            WHERE h.student_id = ?{{_tf}} ORDER BY h.date""", (sid,) + _tp).fetchall()
    _edf = _pd.DataFrame([{{"学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
                             "登记日期": r["date"], "作业评级": _gl(r["grade"])}} for r in _rs])
    if _edf.empty:
        _edf = _pd.DataFrame([{{"学生姓名": _st["name"], "所属分组": "", "登记日期": "", "作业评级": "暂无记录"}}])
    if _rs:
        _stats = {{}}
        for r in _rs: _stats[r["grade"]] = _stats.get(r["grade"], 0) + 1
        _sum = _pd.DataFrame([{{"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""}},
                              {{"学生姓名": "统计汇总", "所属分组": "", "登记日期": "",
                                "作业评级": f"A:{{_stats.get('A',0)}}次 B:{{_stats.get('B',0)}}次 C:{{_stats.get('C',0)}}次 未交:{{_stats.get('X',0)}}次"}}])
        _edf = _pd.concat([_edf, _sum], ignore_index=True)
    _tmpd = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2', 'temp')
    _o.makedirs(_tmpd, exist_ok=True)
    _fp = _o.path.join(_tmpd, f"学生台账_{{_st['name']}}_{{_dt.now().strftime('%Y%m%d%H%M%S')}}.xlsx")
    with _pd.ExcelWriter(_fp, engine="openpyxl") as _w:
        _edf.to_excel(_w, sheet_name="作业台账", index=False)
        _ws = _w.sheets["作业台账"]
        for _c, _wv in zip(["A","B","C","D"], [18,14,14,25]): _ws.column_dimensions[_c].width = _wv
    return _sf(_fp, as_attachment=True, download_name=f"学生台账_{{_st['name']}}.xlsx",
               mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@_app.route("/api/export/class", methods=["GET"])
def _h38():
    _cid = _gcr()
    _st_str = _rq.args.get("start", "")
    _ed = _rq.args.get("end", "")
    _tid = _rq.args.get("homework_type_id", "")
    _db = _get_db()
    _tf = " AND h.homework_type_id = ?" if _tid else ""
    _tp = (int(_tid),) if _tid else ()
    _bs = f"""SELECT h.date, h.grade, s.name as student_name, g.name as group_name
        FROM homework h JOIN students s ON h.student_id = s.id
        LEFT JOIN groups_info g ON s.group_id = g.id
        WHERE s.class_id = ?{{_tf}}"""
    if _st_str and _ed:
        _rs = _db.execute(_bs + " AND h.date >= ? AND h.date <= ? ORDER BY s.group_id, s.sort_order, h.date",
                          (_cid,) + _tp + (_st_str, _ed)).fetchall()
    else:
        _rs = _db.execute(_bs + " ORDER BY s.group_id, s.sort_order, h.date", (_cid,) + _tp).fetchall()
    _edata = [{{"学生姓名": r["student_name"], "所属分组": r["group_name"] or "未分组",
                "登记日期": r["date"], "作业评级": _gl(r["grade"])}} for r in _rs]
    _edf = _pd.DataFrame(_edata)
    if _edf.empty: _edf = _pd.DataFrame([{{"学生姓名": "暂无记录", "所属分组": "", "登记日期": "", "作业评级": ""}}])
    if _rs:
        _sstats = {{}}
        for r in _rs:
            n = r["student_name"]
            if n not in _sstats: _sstats[n] = {{"group": r["group_name"] or "未分组", "A": 0, "B": 0, "C": 0, "X": 0}}
            _sstats[n][r["grade"]] += 1
        _sd = [{{"学生姓名": "", "所属分组": "", "登记日期": "", "作业评级": ""}},
               {{"学生姓名": "=== 全班统计汇总 ===", "所属分组": "", "登记日期": "",
                 "作业评级": f"共 {{len(_sstats)}} 名学生"}}]
        for nm, st in _sstats.items():
            _t = st["A"] + st["B"] + st["C"] + st["X"]
            _sd.append({{"学生姓名": nm, "所属分组": st["group"],
                          "登记日期": f"共{{_t}}次",
                          "作业评级": f"A:{{st['A']}} B:{{st['B']}} C:{{st['C']}} 未交:{{st['X']}}"}})
        _edf = _pd.concat([_edf, _pd.DataFrame(_sd)], ignore_index=True)
    _tmpd = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2', 'temp')
    _o.makedirs(_tmpd, exist_ok=True)
    _fp = _o.path.join(_tmpd, f"全班台账_{{_dt.now().strftime('%Y%m%d%H%M%S')}}.xlsx")
    with _pd.ExcelWriter(_fp, engine="openpyxl") as _w:
        _edf.to_excel(_w, sheet_name="全班作业汇总", index=False)
        _ws = _w.sheets["全班作业汇总"]
        for _c, _wv in zip(["A","B","C","D"], [18,14,14,35]): _ws.column_dimensions[_c].width = _wv
    return _sf(_fp, as_attachment=True,
               download_name=f"全班作业汇总_{{_st_str}}_{{_ed}}.xlsx",
               mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- Scan & Mobile APIs ---
@_app.route("/api/student/by-code/<code>", methods=["GET"])
def _h39(code: str):
    _cid = _gcr()
    _db = _get_db()
    _r = _db.execute("SELECT s.*, g.name as group_name, g.color as group_color "
                     "FROM students s LEFT JOIN groups_info g ON s.group_id = g.id "
                     "WHERE s.student_code = ? AND s.class_id = ?", (code.strip(), _cid)).fetchone()
    if not _r: return _jf({{"code": 1, "msg": f"未找到学号 {{code}} 对应的学生", "external": True}})
    return _jf({{"code": 0, "data": {{"id": _r["id"], "name": _r["name"],
        "student_code": _r["student_code"] or "", "group_id": _r["group_id"] or 0,
        "group_name": _r["group_name"] or "", "group_color": _r["group_color"] or ""}}}})

@_app.route("/api/scan/batch", methods=["POST"])
def _h40():
    _d = _rq.get_json() or {{}}
    _dt_str = _d.get("date", _dt.now().strftime("%Y-%m-%d"))
    _recs = _d.get("records", [])
    _cid = _gcr()
    _tid = int(_d.get("homework_type_id", 0) or 0)
    if _tid <= 0: _tid = _gtr()
    if not _recs: return _jf({{"code": 1, "msg": "无扫码记录"}}), 400
    _db = _get_db()
    _saved = 0
    for _rc in _recs:
        _cd = _rc.get("student_code", "").strip()
        _grd = _rc.get("grade", "X")
        if _grd not in ("A", "B", "C", "X"): continue
        _st = _db.execute("SELECT id FROM students WHERE student_code=? AND class_id=?", (_cd, _cid)).fetchone()
        if not _st: continue
        _db.execute("INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                    "VALUES (?,?,?,?,datetime('now','localtime')) "
                    "ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET "
                    "grade=excluded.grade, updated_at=datetime('now','localtime')",
                    (_st["id"], _dt_str, _grd, _tid))
        _saved += 1
    _db.commit()
    return _jf({{"code": 0, "msg": f"已保存 {{_saved}} 条记录", "data": {{"saved": _saved}}}})

@_app.route("/api/scan/single", methods=["POST"])
def _h41():
    _d = _rq.get_json() or {{}}
    _cd = _d.get("student_code", "").strip()
    _grd = _d.get("grade", "X")
    _dt_str = _d.get("date", _dt.now().strftime("%Y-%m-%d"))
    _cid = _gcr()
    _tid = int(_d.get("homework_type_id", 0) or 0)
    if _tid <= 0: _tid = _gtr()
    if _grd not in ("A", "B", "C", "X"): return _jf({{"code": 1, "msg": "无效等级"}}), 400
    _db = _get_db()
    _st = _db.execute("SELECT id FROM students WHERE student_code=? AND class_id=?", (_cd, _cid)).fetchone()
    if not _st: return _jf({{"code": 1, "msg": f"未找到学号 {{_cd}}", "external": True}})
    _db.execute("INSERT INTO homework (student_id, date, grade, homework_type_id, updated_at) "
                "VALUES (?,?,?,?,datetime('now','localtime')) "
                "ON CONFLICT(student_id, date, homework_type_id) DO UPDATE SET "
                "grade=excluded.grade, updated_at=datetime('now','localtime')",
                (_st["id"], _dt_str, _grd, _tid))
    _db.commit()
    return _jf({{"code": 0, "msg": "登记成功"}})

@_app.route("/api/mobile/pair", methods=["GET"])
def _h42():
    _host = "127.0.0.1"
    try:
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        _host = s.getsockname()[0]
        s.close()
    except: pass
    _port = 5088
    return _jf({{"code": 0, "data": {{"ip": _host, "port": _port,
        "url": f"https://{{_host}}:{{_port}}/mobile", "ssl": True}}}})

@_app.route("/api/mobile/scan", methods=["POST"])
def _h43():
    _d = _rq.get_json() or {{}}
    _cd = _d.get("student_code", "").strip()
    if not _cd: return _jf({{"code": 1, "msg": "未识别到学号"}}), 400
    _db = _get_db()
    _db.execute("INSERT INTO mobile_scans (student_code) VALUES (?)", (_cd,))
    _db.commit()
    return _jf({{"code": 0, "msg": "已接收"}})

@_app.route("/api/mobile/scans", methods=["GET"])
def _h44():
    _since = _rq.args.get("since", "1970-01-01 00:00:00")
    _db = _get_db()
    _rs = _db.execute("SELECT id, student_code, scanned_at FROM mobile_scans "
                      "WHERE scanned_at > ? AND processed = 0 ORDER BY scanned_at", (_since,)).fetchall()
    _scans = []; _cid = _gcr(); _mts = _since
    for r in _rs:
        _st = _db.execute("SELECT id, name, group_id FROM students WHERE student_code=? AND class_id=?",
                          (r["student_code"], _cid)).fetchone()
        _scans.append({{"id": r["id"], "student_code": r["student_code"],
                        "scanned_at": r["scanned_at"],
                        "student_name": _st["name"] if _st else "未知学生",
                        "student_id": _st["id"] if _st else None,
                        "found": _st is not None}})
        _mts = r["scanned_at"]
    return _jf({{"code": 0, "data": _scans, "since": _mts, "total": len(_scans)}})

@_app.route("/api/mobile/clear", methods=["POST"])
def _h45():
    _db = _get_db()
    _db.execute("DELETE FROM mobile_scans")
    _db.commit()
    return _jf({{"code": 0, "msg": "已清空"}})

# --- QR Code ---
@_app.route("/api/qrcode", methods=["GET"])
def _h46():
    _data = _rq.args.get("data", "")
    _size = int(_rq.args.get("size", 150))
    if not _data: return _jf({{"code": 1, "msg": "缺少 data 参数"}}), 400
    qr = _qr.QRCode(version=1, error_correction=_qr.constants.ERROR_CORRECT_L, box_size=10, border=2)
    qr.add_data(_data); qr.make(fit=True)
    img = qr.make_image(fill_color="#5D5A5A", back_color="#ffffff")
    img = img.resize((_size, _size))
    _buf = _io.BytesIO(); img.save(_buf, format="PNG"); _buf.seek(0)
    return _sf(_buf, mimetype="image/png")

# --- Page Routes ---
@_app.route("/mobile")
def _h47(): return _render_page("mobile.html")

@_app.route("/print")
def _h48(): return _render_page("print.html")

@_app.route("/")
def _h49(): return _render_page("index.html")

# --- Certificate Download ---
@_app.route("/api/cert/download")
def _h50():
    _base = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2')
    _cf = _o.path.join(_base, "ca-cert.pem")
    if not _o.path.exists(_cf): return _jf({{"code": 1, "msg": "CA 证书尚未生成"}}), 404
    return _sf(_cf, as_attachment=True, download_name="ClassTrack_CA_Certificate.crt",
               mimetype="application/x-x509-ca-cert")

# --- Config APIs ---
@_app.route("/api/config", methods=["GET"])
def _h51():
    _db = _get_db()
    _rs = _db.execute("SELECT key, value FROM app_config").fetchall()
    return _jf({{"code": 0, "data": {{r["key"]: r["value"] for r in _rs}}}})

@_app.route("/api/config", methods=["POST"])
def _h52():
    _d = _rq.get_json() or {{}}
    _db = _get_db()
    for k, v in _d.items():
        _db.execute("INSERT OR REPLACE INTO app_config (key,value) VALUES (?,?)", (str(k), str(v)))
    _db.commit()
    return _jf({{"code": 0, "msg": "配置已保存"}})

# --- Stats ---
@_app.route("/api/stats", methods=["GET"])
def _h53():
    _cid = _gcr()
    _db = _get_db()
    _ts = _db.execute("SELECT COUNT(*) as c FROM students WHERE class_id=?", (_cid,)).fetchone()["c"]
    _tg = _db.execute("SELECT COUNT(*) as c FROM groups_info WHERE class_id=?", (_cid,)).fetchone()["c"]
    _gr = _db.execute("SELECT COUNT(*) as c FROM students WHERE group_id > 0 AND class_id=?", (_cid,)).fetchone()["c"]
    _tr = _db.execute("SELECT COUNT(*) as c FROM homework h JOIN students s ON h.student_id=s.id WHERE s.class_id=?",
                      (_cid,)).fetchone()["c"]
    _ll = _db.execute("SELECT value FROM app_config WHERE key='last_lock_time'").fetchone()
    _cl = _db.execute("SELECT name FROM classes WHERE id=?", (_cid,)).fetchone()
    return _jf({{"code": 0, "data": {{"total_students": _ts, "total_groups": _tg,
        "grouped_students": _gr, "unassigned_students": _ts - _gr,
        "total_homework_records": _tr,
        "last_lock_time": _ll["value"] if _ll else "尚未锁定",
        "class_name": _cl["name"] if _cl else ""}}}})

# --- Shutdown ---
@_app.route("/api/shutdown", methods=["POST"])
@_ca
def _h54():
    _o._exit(0)
    return _jf({{"code": 0}})

# --- Activation APIs ---
@_app.route("/api/activation/fingerprint", methods=["GET"])
def _h55():
    if not _ACTIVATION_AVAILABLE: return _jf({{"code": 1, "msg": "激活模块未加载"}}), 500
    try:
        _info = _ghf()
        _fpe = _efp()
        return _jf({{"code": 0, "data": {{"machine_code": _info["machine_code"],
            "fingerprint_export": _fpe, "cpu": _info["cpu"], "disk": _info["disk"]}}}})
    except Exception as e: return _jf({{"code": 1, "msg": f"采集失败: {{str(e)}}"}}), 500

@_app.route("/api/activation/verify", methods=["POST"])
def _h56():
    if not _ACTIVATION_AVAILABLE: return _jf({{"code": 1, "msg": "激活模块未加载"}}), 500
    _d = _rq.get_json(silent=True) or {{}}
    _fc = _d.get("file_content", "")
    if not _fc: return _jf({{"code": 1, "msg": "未提供激活文件内容"}}), 400
    if not _saf(_fc): return _jf({{"code": 1, "msg": "激活文件保存失败"}}), 500
    _res = _va()
    return _jf({{"code": 0 if _res.activated else 1, "msg": _res.reason, "data": _res.to_dict()}})

@_app.route("/api/activation/status", methods=["GET"])
def _h57():
    if not _ACTIVATION_AVAILABLE: return _jf({{"code": 0, "data": {{"activated": True}}}})
    _res = _va()
    return _jf({{"code": 0, "data": _res.to_dict()}})

@_app.route("/activation")
@_app.route("/activation/")
def _h58(): return _render_page("activation.html")

# --- Activation Guard Middleware ---
_ACT_WHITELIST = {{"/activation", "/api/activation/fingerprint", "/api/activation/verify",
                    "/api/activation/status", "/api/shutdown", "/api/cert/download",
                    "/api/qrcode", "/mobile", "/print"}}

@_app.before_request
def _ag():
    if not _ACTIVATION_AVAILABLE: return None
    try:
        _path = (_rq.path or "/").rstrip("/") or "/"
        if _path.startswith("/static/"): return None
        if _path in _ACT_WHITELIST: return None
        if _path in ("/favicon.ico", "/robots.txt"): return None
        _res = _va()
        if not _res.activated:
            if _path.startswith("/api/"):
                return _jf({{"code": 403, "msg": "软件未激活", "data": {{"activated": False}}}}), 403
            return _render_page("activation.html")
        return None
    except: return None

# --- Error Handler: Suppress stack traces ---
@_app.errorhandler(Exception)
def _eh(e):
    return _jf({{"code": 500, "msg": "Internal server error"}}), 500

# ================================================================
# MAIN ENTRY POINT
# ================================================================
def main():
    try: _idb()
    except Exception as e: _o._exit(1)

    _act_ok = False
    if _ACTIVATION_AVAILABLE:
        try:
            _res = _va(); _act_ok = _res.activated
        except: pass
    else: _act_ok = True

    _port = 5088
    _base = _o.path.join(_o.getenv('LOCALAPPDATA', _o.path.expanduser('~')), 'ClassTrack_v2')
    _o.makedirs(_base, exist_ok=True)
    _cf = _o.path.join(_base, "cert.pem")
    _kf = _o.path.join(_base, "key.pem")
    _caf = _o.path.join(_base, "ca-cert.pem")
    _cakf = _o.path.join(_base, "ca-key.pem")

    def _lip():
        try:
            s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
            return ip
        except: return "127.0.0.1"

    def _gca():
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        ck = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cs = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Root CA"),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack")])
        cc = (x509.CertificateBuilder().subject_name(cs).issuer_name(cs)
              .public_key(ck.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(_dt.utcnow()).not_valid_after(_dt.utcnow() + _td(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
              .add_extension(x509.KeyUsage(key_cert_sign=True, crl_sign=True, digital_signature=False,
                                           content_commitment=False, key_encipherment=False,
                                           data_encipherment=False, key_agreement=False,
                                           encipher_only=False, decipher_only=False), critical=True)
              .sign(ck, hashes.SHA256()))
        with open(_cakf, "wb") as f: f.write(ck.private_bytes(encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
        with open(_caf, "wb") as f: f.write(cc.public_bytes(serialization.Encoding.PEM))
        return ck, cc

    def _ssc(ca_k, ca_c):
        import ipaddress
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        sk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        lip = _lip()
        ss = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Server"),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack")])
        sc = (x509.CertificateBuilder().subject_name(ss).issuer_name(ca_c.subject)
              .public_key(sk.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(_dt.utcnow()).not_valid_after(_dt.utcnow() + _td(days=3650))
              .add_extension(x509.SubjectAlternativeName([
                  x509.DNSName("localhost"),
                  x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                  x509.IPAddress(ipaddress.IPv4Address(lip))]), critical=False)
              .sign(ca_k, hashes.SHA256()))
        with open(_kf, "wb") as f: f.write(sk.private_bytes(encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
        with open(_cf, "wb") as f: f.write(sc.public_bytes(serialization.Encoding.PEM))

    def _tca():
        try:
            _sp.run(["certutil", "-addstore", "-user", "Root", _caf], capture_output=True, text=True, timeout=15)
            return True
        except: return False

    if _o.path.exists(_cf) and _o.path.exists(_kf):
        _ssl = (_cf, _kf)
    else:
        try:
            if _o.path.exists(_caf) and _o.path.exists(_cakf):
                from cryptography import x509
                from cryptography.hazmat.primitives import serialization
                with open(_cakf, "rb") as f: _ca_k = serialization.load_pem_private_key(f.read(), password=None)
                with open(_caf, "rb") as f: _ca_c = x509.load_pem_x509_certificate(f.read())
            else: _ca_k, _ca_c = _gca()
            _ssc(_ca_k, _ca_c); _tca(); _ssl = (_cf, _kf)
        except: _ssl = "adhoc"

    def _ob():
        _t.sleep(1.5)
        try:
            _o.startfile(f"https://localhost:{{_port}}{{'' if _act_ok else '/activation'}}")
        except Exception:
            pass
    _th.Thread(target=_ob, daemon=True).start()
    _app.run(host="0.0.0.0", port=_port, debug=False, threaded=True, ssl_context=_ssl)

if __name__ == "__main__":
    main()
'''
    return core

# ============================================================
# Step 7: Main build function
# ============================================================
def build():
    """Execute the complete build process"""
    print("=" * 60)
    print("  ClassTrack Hardened Build System v2.0")
    print("=" * 60)

    # Generate keys
    print("\n[1/6] Generating encryption keys...")
    f_key, xor_keys = generate_keys()
    print(f"  Fernet key: {f_key.decode()[:20]}...")
    print(f"  XOR keys: 3 x 16 bytes generated")

    # Encrypt resources
    print("\n[2/6] Encrypting templates and static resources...")
    resources = encrypt_resources(f_key)
    print(f"  Encrypted {len(resources)} resource files:")
    for name in sorted(resources.keys()):
        print(f"    - {name} ({len(resources[name])} bytes base64)")

    # Build string table
    print("\n[3/6] Building string encryption table...")
    str_table = build_string_table(SENSITIVE_STRINGS, xor_keys)
    print(f"  {len(str_table)} strings encrypted")

    # Read activation module
    print("\n[4/6] Processing activation module...")
    act_dir = ORIG_ROOT / "activation"
    activation_code = ""
    if act_dir.exists():
        for pyf in sorted(act_dir.glob("*.py")):
            if pyf.name.startswith('_'): continue
            with open(pyf, 'r', encoding='utf-8') as fh:
                activation_code += fh.read() + "\n"
        print(f"  Embedded activation module ({len([f for f in act_dir.glob('*.py') if not f.name.startswith('_')])} files)")
    else:
        print("  Activation module not found (optional)")

    # Generate hardened core
    print("\n[5/6] Generating hardened core file...")
    core = generate_hardened_core(f_key, xor_keys, resources, activation_code)

    # Write output
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_file = ROOT / "class_track_core.py"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(core)
    size_kb = len(core) / 1024
    print(f"  Written: {output_file} ({size_kb:.1f} KB)")

    # Save keys for PyInstaller
    print("\n[6/6] Saving build artifacts...")
    key_file = ROOT / "build_keys.json"
    key_data = {
        "fernet_key": f_key.decode(),
        "xor_keys": [k.hex() for k in xor_keys],
        "build_time": datetime.now().isoformat(),
        "resource_count": len(resources),
    }
    with open(key_file, 'w') as f:
        json.dump(key_data, f, indent=2)
    print(f"  Keys saved: {key_file}")
    print(f"\n{'=' * 60}")
    print(f"  BUILD COMPLETE")
    print(f"  Output: {output_file}")
    print(f"  Next: Run pyarmor obfuscate, then PyInstaller")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    build()
