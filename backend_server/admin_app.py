#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack.com — PyQt6 管理桌面端
==================================
液态玻璃视觉风格 · 直连 SQLite · 独立运行
功能: 登录 → 数据看板 → 注册码管理 → 系统设置 → 操作日志
"""

import os
import sys
import sqlite3
import hashlib
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QTabWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QFileDialog,
    QComboBox, QTextEdit, QScrollArea, QSizePolicy,
    QSpacerItem, QProgressBar, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette, QBrush


# ---- PyInstaller 路径适配 ----
if getattr(sys, 'frozen', False):
    _ROOT = Path(sys._MEIPASS)
    _EXE_DIR = Path(sys.executable).resolve().parent
else:
    _ROOT = Path(__file__).resolve().parent
    _EXE_DIR = _ROOT

# ============================================================
# 路径 & 常量
# ============================================================
ROOT = _ROOT
DATA_DIR = _EXE_DIR / "data"
DB_PATH = DATA_DIR / "classtrack_server.db"
FILES_DIR = DATA_DIR / "files"
MEDIA_DIR = DATA_DIR / "media"
ADMIN_PASSWORD = "admin123"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ---- 订单模块 ----
sys.path.insert(0, str(_ROOT))
from order_utils import (
    generate_order_no, calculate_expiry, expire_stale_orders,
    validate_status_transition, get_status_label, get_status_color,
    VALID_STATUSES
)

# ---- 隧道模块 ----
from tunnel import TunnelManager

# ---- 马卡龙色系（与 Web 端一致）----
COLORS = {
    "bg":            "#F5F1ED",
    "bg_alt":        "#FAF8F5",
    "primary":       "#7EB5D6",
    "primary_light": "#B8D8E8",
    "primary_pale":  "#E4F0F6",
    "primary_dark":  "#5A9AB8",
    "accent":        "#E8A0BF",
    "accent_light":  "#F2C8DA",
    "accent_pale":   "#FAEBF0",
    "success":       "#A8D5BA",
    "success_pale":  "#E8F4EB",
    "warning":       "#F4C97E",
    "warning_pale":  "#FEF6E5",
    "danger":        "#E07080",
    "text":          "#5D5A5A",
    "text_light":    "#999595",
    "text_lighter":  "#BFBBBB",
    "white":         "#FFFFFF",
    "card_bg":       "rgba(255,255,255,0.62)",
    "card_border":   "rgba(255,255,255,0.22)",
    "header_bg":     "rgba(255,255,255,0.88)",
}

# ---- 全局 QSS 样式表 ----
GLOBAL_QSS = f"""
/* ========== 全局 ========== */
QMainWindow, QDialog {{
    background-color: {COLORS["bg"]};
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    color: {COLORS["text"]};
}}

/* ========== 标签页 ========== */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: rgba(255,255,255,0.45);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 14px;
    padding: 8px 20px;
    margin: 4px 4px;
    font-size: 13px;
    font-weight: 600;
    color: {COLORS["text_light"]};
}}
QTabBar::tab:selected {{
    background: rgba(255,255,255,0.85);
    color: {COLORS["primary"]};
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{
    background: rgba(255,255,255,0.7);
    color: {COLORS["text"]};
}}

/* ========== 卡片框 ========== */
QFrame#card {{
    background: {COLORS["card_bg"]};
    border: 1px solid {COLORS["card_border"]};
    border-radius: 20px;
}}
QFrame#statCard {{
    background: {COLORS["card_bg"]};
    border: 1px solid {COLORS["card_border"]};
    border-radius: 20px;
    padding: 16px;
}}
QFrame#statCard:hover {{
    background: rgba(255,255,255,0.78);
}}

/* ========== 按钮 ========== */
QPushButton {{
    background: rgba(255,255,255,0.6);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 20px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    color: {COLORS["text"]};
}}
QPushButton:hover {{
    background: rgba(255,255,255,0.85);
}}
QPushButton:pressed {{
    background: rgba(255,255,255,0.7);
}}

QPushButton#btnPrimary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7EB5D6, stop:1 #8EC8C0);
    color: white;
    font-weight: 700;
    border: 1px solid rgba(255,255,255,0.3);
}}
QPushButton#btnPrimary:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8EC8E0, stop:1 #9ED8D0);
}}
QPushButton#btnAccent {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #E8A0BF, stop:1 #F0B8A0);
    color: white;
    font-weight: 700;
    border: 1px solid rgba(255,255,255,0.3);
}}
QPushButton#btnSuccess {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #A8D5BA, stop:1 #8EC8C0);
    color: white;
    font-weight: 700;
    border: 1px solid rgba(255,255,255,0.3);
}}
QPushButton#btnDanger {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #E07080, stop:1 #D4889F);
    color: white;
    font-weight: 700;
    border: 1px solid rgba(255,255,255,0.3);
}}

/* ========== 输入框 ========== */
QLineEdit, QTextEdit, QComboBox {{
    background: rgba(255,255,255,0.65);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 14px;
    padding: 8px 12px;
    font-size: 13px;
    color: {COLORS["text"]};
    selection-background-color: {COLORS["primary_light"]};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: {COLORS["primary"]};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 10px;
    selection-background-color: {COLORS["primary_pale"]};
}}

/* ========== 表格 ========== */
QTableWidget {{
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 14px;
    gridline-color: rgba(0,0,0,0.04);
    font-size: 13px;
}}
QTableWidget::item {{
    padding: 6px 12px;
    border-bottom: 1px solid rgba(0,0,0,0.03);
}}
QTableWidget::item:selected {{
    background: {COLORS["primary_pale"]};
    color: {COLORS["text"]};
}}
QHeaderView::section {{
    background: rgba(255,255,255,0.6);
    border: none;
    border-bottom: 2px solid rgba(0,0,0,0.06);
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 700;
    color: {COLORS["text"]};
    text-transform: uppercase;
}}

/* ========== 滚动条 ========== */
QScrollBar:vertical {{
    width: 5px;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    background: rgba(0,0,0,0.1);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0,0,0,0.18);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


# ============================================================
# 数据库工具
# ============================================================
def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表（与 Flask 端一致）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS registration_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            reg_code TEXT NOT NULL UNIQUE,
            user_note TEXT DEFAULT '',
            is_paid INTEGER DEFAULT 0,
            paid_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS software_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            version TEXT DEFAULT '1.0.0',
            file_size INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS server_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
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
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(registration_codes)").fetchall()}
    for col in [("order_id", "INTEGER DEFAULT NULL"), ("order_no", "TEXT DEFAULT ''"),
                ("amount", "REAL DEFAULT 0.00"), ("payment_method", "TEXT DEFAULT ''")]:
        if col[0] not in existing_cols:
            conn.execute(f"ALTER TABLE registration_codes ADD COLUMN {col[0]} {col[1]}")
    # 默认配置
    defaults = {
        "payment_api_url": "",
        "payment_api_enabled": "0",
        "payment_api_key": "",
        "payment_simulation_mode": "1",
        "hero_video_filename": "",
        "payment_qr_filename": "",
        "payment_instructions": "请使用微信或支付宝扫描二维码完成付款\n付款后请点击下方「模拟支付成功」验证并解锁下载",
        # v2.0
        "order_expiry_minutes": "30",
        "tunnel_enabled": "1",
        "tunnel_backend": "serveo",
        "tunnel_ngrok_auth_token": "",
        "tunnel_public_url": "",
        "default_amount": "0.00",
    }
    for k, v in defaults.items():
        if not conn.execute("SELECT value FROM server_config WHERE key=?", (k,)).fetchone():
            conn.execute("INSERT INTO server_config (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def write_log(action, detail=""):
    conn = get_db_connection()
    conn.execute("INSERT INTO admin_log (action, detail) VALUES (?, ?)", (action, detail))
    conn.commit()
    conn.close()


# ============================================================
#  登录对话框
# ============================================================
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClassTrack.com — 管理员登录")
        self.setFixedSize(380, 280)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS["bg"]};
            }}
            QLabel#title {{
                font-size: 20px;
                font-weight: 700;
                color: {COLORS["text"]};
            }}
            QLabel#subtitle {{
                font-size: 13px;
                color: {COLORS["text_light"]};
            }}
            QLabel#error {{
                font-size: 12px;
                color: {COLORS["danger"]};
            }}
            QLineEdit {{
                font-size: 16px;
                padding: 10px 16px;
                text-align: center;
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(36, 28, 36, 28)

        # 图标 + 标题
        icon_lbl = QLabel("🔐")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 40px;")
        layout.addWidget(icon_lbl)

        title = QLabel("ClassTrack.com 管理后台")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 密码输入
        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("请输入管理密码")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.returnPressed.connect(self._login)
        layout.addWidget(self.pw_input)

        # 错误提示
        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("error")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_lbl.setVisible(False)
        layout.addWidget(self.error_lbl)

        # 登录按钮
        btn = QPushButton("🔓 登录")
        btn.setObjectName("btnPrimary")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._login)
        layout.addWidget(btn)

        self.setLayout(layout)

    def _login(self):
        pw = self.pw_input.text()
        if pw == ADMIN_PASSWORD:
            write_log("admin_login", "管理员登录成功 (PyQt6)")
            self.accept()
        else:
            self.error_lbl.setText("密码错误，请重试")
            self.error_lbl.setVisible(True)
            self.pw_input.clear()
            self.pw_input.setFocus()


# ============================================================
# 上传软件包对话框
# ============================================================
class UploadPackageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📤 上传软件包")
        self.setFixedSize(480, 340)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("📤 上传新软件包")
        title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        layout.addWidget(title)

        # 版本号
        layout.addWidget(QLabel("版本号"))
        self.version_input = QLineEdit("1.0.0")
        layout.addWidget(self.version_input)

        # 文件选择
        layout.addWidget(QLabel("选择文件"))
        file_row = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("选择 .exe / .zip / .msi 文件...")
        self.file_path_input.setReadOnly(True)
        file_row.addWidget(self.file_path_input)

        browse_btn = QPushButton("📁 浏览")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # 按钮
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.upload_btn = QPushButton("📤 确认上传")
        self.upload_btn.setObjectName("btnPrimary")
        self.upload_btn.clicked.connect(self._upload)
        btn_row.addWidget(self.upload_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择软件包", "",
            "软件包 (*.exe *.zip *.msi *.7z);;所有文件 (*.*)"
        )
        if path:
            self.file_path_input.setText(path)

    def _upload(self):
        src = self.file_path_input.text().strip()
        version = self.version_input.text().strip() or "1.0.0"
        if not src:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        src_path = Path(src)
        if not src_path.exists():
            QMessageBox.warning(self, "提示", "文件不存在")
            return

        dest_path = FILES_DIR / src_path.name
        try:
            shutil.copy2(str(src_path), str(dest_path))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"复制文件失败: {e}")
            return

        file_size = dest_path.stat().st_size
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO software_packages (filename, version, file_size) VALUES (?, ?, ?)",
            (src_path.name, version, file_size)
        )
        conn.commit()
        conn.close()

        write_log("upload_package", f"上传 {src_path.name} v{version}")
        QMessageBox.information(self, "成功", f"「{src_path.name}」上传成功")
        self.accept()


# ============================================================
# 主窗口
# ============================================================
class AdminMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClassTrack.com — 管理后台")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 820)
        self._setup_ui()
        self._load_all()

    # --------------------------------------------------------
    #  UI 构建
    # --------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout()
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)
        central.setLayout(root_layout)

        # ---- 顶部导航条 ----
        root_layout.addWidget(self._build_header())

        # ---- Tab 页 ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "📊 管理看板")
        self.tabs.addTab(self._build_orders_tab(), "📋 订单管理")
        self.tabs.addTab(self._build_settings_tab(), "⚙️ 系统设置")
        self.tabs.addTab(self._build_logs_tab(), "📋 操作日志")
        root_layout.addWidget(self.tabs, stretch=1)

        # ---- 底部状态栏 ----
        footer = QLabel("© 2026 ClassTrack.com — 班级作业分组管理系统  |  数据本地存储 · 安全可靠")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"""
            font-size:12px; color:{COLORS['text_lighter']};
            padding:12px; border-top:1px solid rgba(0,0,0,0.04);
        """)
        root_layout.addWidget(footer)

    def _build_header(self):
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(f"""
            QFrame {{
                background: {COLORS["header_bg"]};
                border-bottom: 1px solid rgba(200,190,185,0.15);
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Logo
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("🎒")
        logo_icon.setStyleSheet("font-size:24px;")
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("ClassTrack.com")
        logo_text.setStyleSheet(f"""
            font-size:18px; font-weight:700;
            color: {COLORS["primary_dark"]};
        """)
        logo_layout.addWidget(logo_text)
        layout.addLayout(logo_layout)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # 右侧信息
        right_layout = QHBoxLayout()
        # 隧道状态
        self.tunnel_status_lbl = QLabel("🔒 公网未连接")
        self.tunnel_status_lbl.setStyleSheet(f"font-size:11px; color:{COLORS['text_lighter']}; margin-right:16px;")
        right_layout.addWidget(self.tunnel_status_lbl)

        info = QLabel("🔐 管理后台  |  PyQt6 Desktop")
        info.setStyleSheet(f"font-size:12px; color:{COLORS['text_light']};")
        right_layout.addWidget(info)
        layout.addLayout(right_layout)

        header.setLayout(layout)
        return header

    # --------------------------------------------------------
    #  Tab 1: 管理看板
    # --------------------------------------------------------
    def _build_dashboard_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # -- 统计卡片 --
        self.stat_cards = {}
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        card_specs = [
            ("statTotal",    "🔑", "注册码总数", "0",    "primary_dark"),
            ("statPaid",     "✅", "已付款",     "0",    "#3A7D5A"),
            ("statUnpaid",    "⏳", "待付款",     "0",    "#C08050"),
            ("statDownloads", "📥", "总下载次数",  "0",    "#C4728E"),
            ("statToday",     "🆕", "今日新增",   "0",    "primary_dark"),
            ("statOrders",    "📋", "总订单数",   "0",    "#7EB5D6"),
            ("statPendingOrd","⏳", "待处理订单",  "0",    "#C08050"),
            ("statRevenue",   "💰", "总收入",     "¥0",  "#3A7D5A"),
        ]

        for obj_name, icon, label, val, val_color in card_specs:
            card = QFrame()
            card.setObjectName("statCard")
            card.setMinimumSize(190, 110)
            card_layout = QVBoxLayout()
            card_layout.setSpacing(6)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size:28px;")
            card_layout.addWidget(icon_lbl)

            val_lbl = QLabel(val)
            val_lbl.setObjectName(obj_name)
            val_lbl.setStyleSheet(f"font-size:28px;font-weight:700;color:{val_color};")
            card_layout.addWidget(val_lbl)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size:12px;color:{COLORS['text_light']};")
            card_layout.addWidget(lbl)

            card.setLayout(card_layout)
            cards_layout.addWidget(card)
            self.stat_cards[obj_name] = val_lbl

        layout.addLayout(cards_layout)

        # -- 筛选 & 搜索栏 --
        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(20, 14, 20, 14)

        filter_layout.addWidget(QLabel("筛选:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["全部", "✅ 已付款", "⏳ 待付款"])
        self.status_combo.setFixedWidth(120)
        self.status_combo.currentIndexChanged.connect(lambda: self._load_records())
        filter_layout.addWidget(self.status_combo)

        filter_layout.addSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索指纹 / 注册码 / 备注...")
        self.search_input.setFixedWidth(260)
        self.search_input.returnPressed.connect(lambda: self._load_records())
        filter_layout.addWidget(self.search_input)

        search_btn = QPushButton("🔍 搜索")
        search_btn.clicked.connect(lambda: self._load_records())
        filter_layout.addWidget(search_btn)

        filter_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        upload_btn = QPushButton("📤 上传软件包")
        upload_btn.setObjectName("btnAccent")
        upload_btn.clicked.connect(self._upload_package)
        filter_layout.addWidget(upload_btn)

        filter_frame.setLayout(filter_layout)
        layout.addWidget(filter_frame)

        # -- 记录表格 --
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(9)
        self.records_table.setHorizontalHeaderLabels([
            "ID", "指纹", "注册码", "备注", "状态", "创建时间", "付款时间", "", ""
        ])
        self.records_table.horizontalHeader().setStretchLastSection(False)
        self.records_table.setColumnWidth(0, 50)
        self.records_table.setColumnWidth(1, 150)
        self.records_table.setColumnWidth(2, 170)
        self.records_table.setColumnWidth(3, 120)
        self.records_table.setColumnWidth(4, 100)
        self.records_table.setColumnWidth(5, 160)
        self.records_table.setColumnWidth(6, 160)
        self.records_table.setColumnWidth(7, 90)  # mark paid btn
        self.records_table.setColumnWidth(8, 70)  # delete btn
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.records_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.records_table, stretch=1)

        # -- 分页 --
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self.page_label = QLabel("")
        self.page_label.setStyleSheet(f"font-size:12px;color:{COLORS['text_light']};")
        page_layout.addWidget(self.page_label)

        self.prev_btn = QPushButton("◀ 上一页")
        self.prev_btn.clicked.connect(self._prev_page)
        page_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一页 ▶")
        self.next_btn.clicked.connect(self._next_page)
        page_layout.addWidget(self.next_btn)
        page_layout.addStretch()
        layout.addLayout(page_layout)

        self._current_page = 1
        self._total_pages = 1

        widget.setLayout(layout)
        return widget

    # --------------------------------------------------------
    #  Tab 2: 订单管理
    # --------------------------------------------------------
    def _build_orders_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # -- 筛选栏 --
        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(20, 14, 20, 14)

        filter_layout.addWidget(QLabel("筛选:"))
        self.order_status_combo = QComboBox()
        self.order_status_combo.addItems(["全部", "⏳ 待付款", "✅ 已付款", "⏰ 已过期", "↩️ 已退款", "❌ 已取消"])
        self.order_status_combo.setFixedWidth(140)
        self.order_status_combo.currentIndexChanged.connect(lambda: self._load_orders())
        filter_layout.addWidget(self.order_status_combo)

        filter_layout.addSpacing(12)
        self.order_search_input = QLineEdit()
        self.order_search_input.setPlaceholderText("搜索订单号 / 指纹...")
        self.order_search_input.setFixedWidth(260)
        self.order_search_input.returnPressed.connect(lambda: self._load_orders())
        filter_layout.addWidget(self.order_search_input)

        search_btn = QPushButton("🔍 搜索")
        search_btn.clicked.connect(lambda: self._load_orders())
        filter_layout.addWidget(search_btn)

        filter_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        expire_btn = QPushButton("⏰ 过期处理")
        expire_btn.setObjectName("btnAccent")
        expire_btn.clicked.connect(self._expire_stale_orders)
        filter_layout.addWidget(expire_btn)

        filter_frame.setLayout(filter_layout)
        layout.addWidget(filter_frame)

        # -- 订单表格 --
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(9)
        self.orders_table.setHorizontalHeaderLabels([
            "订单号", "金额", "付款方式", "状态", "指纹", "注册码", "创建时间", "", ""
        ])
        self.orders_table.setColumnWidth(0, 160)
        self.orders_table.setColumnWidth(1, 70)
        self.orders_table.setColumnWidth(2, 80)
        self.orders_table.setColumnWidth(3, 100)
        self.orders_table.setColumnWidth(4, 140)
        self.orders_table.setColumnWidth(5, 170)
        self.orders_table.setColumnWidth(6, 160)
        self.orders_table.setColumnWidth(7, 100)
        self.orders_table.setColumnWidth(8, 80)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.orders_table, stretch=1)

        # -- 分页 --
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self.order_page_label = QLabel("")
        self.order_page_label.setStyleSheet(f"font-size:12px;color:{COLORS['text_light']};")
        page_layout.addWidget(self.order_page_label)

        self.order_prev_btn = QPushButton("◀ 上一页")
        self.order_prev_btn.clicked.connect(self._order_prev_page)
        page_layout.addWidget(self.order_prev_btn)

        self.order_next_btn = QPushButton("下一页 ▶")
        self.order_next_btn.clicked.connect(self._order_next_page)
        page_layout.addWidget(self.order_next_btn)
        page_layout.addStretch()
        layout.addLayout(page_layout)

        self._order_current_page = 1
        self._order_total_pages = 1

        widget.setLayout(layout)
        return widget

    def _load_orders(self):
        """加载订单列表"""
        try:
            status_idx = self.order_status_combo.currentIndex() if hasattr(self, 'order_status_combo') else 0
            search = self.order_search_input.text().strip() if hasattr(self, 'order_search_input') else ""

            status_map = {0: None, 1: "pending", 2: "paid", 3: "expired", 4: "refunded", 5: "cancelled"}
            status = status_map.get(status_idx)

            where = "WHERE 1=1"
            params = []
            if status:
                where += " AND status=?"
                params.append(status)
            if search:
                where += " AND (order_no LIKE ? OR fingerprint LIKE ? OR reg_code LIKE ? OR user_note LIKE ?)"
                like = f"%{search}%"
                params.extend([like, like, like, like])

            conn = get_db_connection()
            total = conn.execute(f"SELECT COUNT(*) as c FROM orders {where}", params).fetchone()["c"]

            per_page = 25
            self._order_total_pages = max(1, (total + per_page - 1) // per_page)
            if self._order_current_page > self._order_total_pages:
                self._order_current_page = self._order_total_pages

            offset = (self._order_current_page - 1) * per_page
            rows = conn.execute(
                f"SELECT * FROM orders {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [per_page, offset]
            ).fetchall()

            self.orders_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                fp = r["fingerprint"] or ""
                fp_display = fp[:20] + "..." if len(fp) > 20 else (fp or "-")
                rc = r["reg_code"] or ""
                rc_display = rc[:16] + "..." if len(rc) > 16 else (rc or "-")

                self.orders_table.setItem(i, 0, self._cell(r["order_no"], bold=True, mono=True))
                self.orders_table.setItem(i, 1, self._cell(f"¥{r['amount']:.2f}"))
                self.orders_table.setItem(i, 2, self._cell(r["payment_method"] or "-"))
                self.orders_table.setItem(i, 3, self._cell(
                    get_status_label(r["status"]),
                    color=get_status_color(r["status"]),
                    bold=True
                ))
                self.orders_table.setItem(i, 4, self._cell(fp_display))
                self.orders_table.setItem(i, 5, self._cell(rc_display, mono=True))
                self.orders_table.setItem(i, 6, self._cell(r["created_at"] or ""))

                # 操作按钮
                order_no = r["order_no"]
                curr_status = r["status"]

                btn_container = QWidget()
                btn_layout = QHBoxLayout()
                btn_layout.setSpacing(4)
                btn_layout.setContentsMargins(0, 0, 0, 0)

                if curr_status == "pending":
                    btn_pay = QPushButton("标记已付")
                    btn_pay.setObjectName("btnSuccess")
                    btn_pay.setStyleSheet("font-size:11px;padding:4px 8px;")
                    btn_pay.clicked.connect(lambda checked, ono=order_no: self._order_set_status(ono, "paid"))
                    btn_layout.addWidget(btn_pay)

                    btn_cancel = QPushButton("取消")
                    btn_cancel.setObjectName("btnDanger")
                    btn_cancel.setStyleSheet("font-size:11px;padding:4px 8px;")
                    btn_cancel.clicked.connect(lambda checked, ono=order_no: self._order_set_status(ono, "cancelled"))
                    btn_layout.addWidget(btn_cancel)
                elif curr_status == "paid":
                    btn_refund = QPushButton("退款")
                    btn_refund.setStyleSheet(f"font-size:11px;color:{COLORS['danger']};padding:4px 8px;")
                    btn_refund.clicked.connect(lambda checked, ono=order_no: self._order_set_status(ono, "refunded"))
                    btn_layout.addWidget(btn_refund)

                btn_container.setLayout(btn_layout)
                self.orders_table.setCellWidget(i, 7, btn_container)

                btn_del = QPushButton("删除")
                btn_del.setObjectName("btnDanger")
                btn_del.setStyleSheet("font-size:11px;padding:4px 8px;")
                btn_del.clicked.connect(lambda checked, ono=order_no: self._delete_order(ono))
                self.orders_table.setCellWidget(i, 8, btn_del)

            conn.close()

            self.order_page_label.setText(f"共 {total} 条 · 第 {self._order_current_page}/{self._order_total_pages} 页")
            self.order_prev_btn.setEnabled(self._order_current_page > 1)
            self.order_next_btn.setEnabled(self._order_current_page < self._order_total_pages)
        except Exception as e:
            print(f"load_orders error: {e}")

    def _order_set_status(self, order_no, target):
        label = get_status_label(target)
        reply = QMessageBox.question(
            self, "确认操作", f"确认将订单 {order_no} 标记为「{label}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = get_db_connection()
        row = conn.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone()
        if not row:
            conn.close()
            return

        if not validate_status_transition(row["status"], target):
            QMessageBox.warning(self, "错误", f"不允许从 {get_status_label(row['status'])} 转为 {label}")
            conn.close()
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if target == "paid":
            conn.execute("UPDATE orders SET status='paid', paid_at=? WHERE order_no=?", (now_str, order_no))
            if row["fingerprint"]:
                conn.execute("UPDATE registration_codes SET is_paid=1, paid_at=? WHERE fingerprint=? ORDER BY id DESC LIMIT 1",
                             (now_str, row["fingerprint"]))
        elif target == "refunded":
            conn.execute("UPDATE orders SET status='refunded', refunded_at=? WHERE order_no=?", (now_str, order_no))
            if row["fingerprint"]:
                conn.execute("UPDATE registration_codes SET is_paid=0, paid_at=NULL WHERE fingerprint=?",
                             (row["fingerprint"],))
        elif target == "cancelled":
            conn.execute("UPDATE orders SET status='cancelled', cancelled_at=? WHERE order_no=?", (now_str, order_no))

        conn.commit()
        conn.close()
        write_log("order_status_update", f"订单 {order_no}: {get_status_label(row['status'])} → {label}")
        self._load_orders()
        self._load_stats()
        self._load_logs()

    def _delete_order(self, order_no):
        reply = QMessageBox.question(
            self, "确认删除", f"确认删除订单 {order_no}？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        conn = get_db_connection()
        conn.execute("DELETE FROM orders WHERE order_no=?", (order_no,))
        conn.commit()
        conn.close()
        write_log("delete_order", f"删除订单 {order_no}")
        self._load_orders()
        self._load_stats()
        self._load_logs()

    def _expire_stale_orders(self):
        """手动触发过期处理"""
        conn = get_db_connection()
        count = expire_stale_orders(conn)
        conn.close()
        if count > 0:
            write_log("orders_expired", f"过期处理: {count} 笔订单已过期")
        QMessageBox.information(self, "过期处理", f"已过期 {count} 笔待付款订单")
        self._load_orders()
        self._load_stats()
        self._load_logs()

    def _order_prev_page(self):
        if self._order_current_page > 1:
            self._order_current_page -= 1
            self._load_orders()

    def _order_next_page(self):
        if self._order_current_page < self._order_total_pages:
            self._order_current_page += 1
            self._load_orders()

    # --------------------------------------------------------
    #  Tab 3: 系统设置
    # --------------------------------------------------------
    def _build_settings_tab(self):
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        inner = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # 表单卡片
        form_card = QFrame()
        form_card.setObjectName("card")
        form_card.setMaximumWidth(700)
        form_layout = QVBoxLayout()
        form_layout.setSpacing(16)
        form_layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("🔧 服务配置")
        title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        form_layout.addWidget(title)

        # 配置1: 支付接口
        form_layout.addWidget(QLabel("💳 支付接口地址"))
        self.cfg_payment = QLineEdit()
        self.cfg_payment.setPlaceholderText("https://api.example.com/payment/callback")
        form_layout.addWidget(self.cfg_payment)
        hint1 = QLabel("用户付款成功后的回调接口地址，用于自动标记注册码为已付款状态")
        hint1.setStyleSheet(f"font-size:11px;color:{COLORS['text_lighter']};margin-bottom:4px;")
        form_layout.addWidget(hint1)

        # 配置2: 视频上传
        form_layout.addWidget(QLabel("📹 视频上传地址"))
        self.cfg_video = QLineEdit()
        self.cfg_video.setPlaceholderText("https://upload.example.com/video")
        form_layout.addWidget(self.cfg_video)
        hint2 = QLabel("教学视频上传的目标接口地址")
        hint2.setStyleSheet(f"font-size:11px;color:{COLORS['text_lighter']};margin-bottom:4px;")
        form_layout.addWidget(hint2)

        # 配置3: 软件包路径
        form_layout.addWidget(QLabel("📁 软件包存储路径"))
        path_row = QHBoxLayout()
        self.cfg_path = QLineEdit()
        self.cfg_path.setPlaceholderText(str(FILES_DIR))
        path_row.addWidget(self.cfg_path)
        browse_btn = QPushButton("📁 浏览")
        browse_btn.clicked.connect(lambda: self._browse_folder(self.cfg_path))
        path_row.addWidget(browse_btn)
        form_layout.addLayout(path_row)
        hint3 = QLabel("客户端软件安装包的本地存储目录路径（绝对路径）")
        hint3.setStyleSheet(f"font-size:11px;color:{COLORS['text_lighter']};margin-bottom:4px;")
        form_layout.addWidget(hint3)

        form_layout.addSpacerItem(QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # 保存按钮
        save_btn = QPushButton("💾 保存配置")
        save_btn.setObjectName("btnPrimary")
        save_btn.setFixedHeight(44)
        save_btn.clicked.connect(self._save_settings)
        form_layout.addWidget(save_btn)

        form_card.setLayout(form_layout)
        layout.addWidget(form_card)

        # ---- 🎬 媒体上传卡片（视频 + 二维码 + 付款说明）----
        media_card = QFrame()
        media_card.setObjectName("card")
        media_card.setMaximumWidth(700)
        media_layout = QVBoxLayout()
        media_layout.setSpacing(14)
        media_layout.setContentsMargins(28, 24, 28, 24)

        media_title = QLabel("🎬 首页媒体管理")
        media_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        media_layout.addWidget(media_title)

        # 视频上传
        media_layout.addWidget(QLabel("🎬 首页背景视频 (.mp4 / .webm)"))
        vid_row = QHBoxLayout()
        self.cfg_video_file = QLineEdit()
        self.cfg_video_file.setPlaceholderText("未上传视频（将使用默认渐变背景）")
        self.cfg_video_file.setReadOnly(True)
        vid_row.addWidget(self.cfg_video_file)
        vid_browse = QPushButton("📁 浏览")
        vid_browse.clicked.connect(lambda: self._browse_media("hero_video"))
        vid_row.addWidget(vid_browse)
        vid_upload = QPushButton("⬆ 上传")
        vid_upload.clicked.connect(lambda: self._upload_media("hero_video"))
        vid_row.addWidget(vid_upload)
        vid_clear = QPushButton("🗑 清除")
        vid_clear.setObjectName("btnDanger")
        vid_clear.clicked.connect(lambda: self._clear_media("hero_video"))
        vid_row.addWidget(vid_clear)
        media_layout.addLayout(vid_row)

        # 二维码上传
        media_layout.addWidget(QLabel("🖼️ 付款二维码 (.png / .jpg)"))
        qr_row = QHBoxLayout()
        self.cfg_qr_file = QLineEdit()
        self.cfg_qr_file.setPlaceholderText("未上传二维码")
        self.cfg_qr_file.setReadOnly(True)
        qr_row.addWidget(self.cfg_qr_file)
        qr_browse = QPushButton("📁 浏览")
        qr_browse.clicked.connect(lambda: self._browse_media("payment_qr"))
        qr_row.addWidget(qr_browse)
        qr_upload = QPushButton("⬆ 上传")
        qr_upload.clicked.connect(lambda: self._upload_media("payment_qr"))
        qr_row.addWidget(qr_upload)
        qr_clear = QPushButton("🗑 清除")
        qr_clear.setObjectName("btnDanger")
        qr_clear.clicked.connect(lambda: self._clear_media("payment_qr"))
        qr_row.addWidget(qr_clear)
        media_layout.addLayout(qr_row)

        # 付款说明
        media_layout.addWidget(QLabel("📝 付款说明文字"))
        self.cfg_payment_instructions = QTextEdit()
        self.cfg_payment_instructions.setPlaceholderText("请使用微信或支付宝扫描二维码完成付款...")
        self.cfg_payment_instructions.setMaximumHeight(80)
        media_layout.addWidget(self.cfg_payment_instructions)

        # 保存媒体设置
        media_save = QPushButton("💾 保存媒体设置")
        media_save.setObjectName("btnPrimary")
        media_save.setFixedHeight(40)
        media_save.clicked.connect(self._save_media_settings)
        media_layout.addWidget(media_save)

        media_card.setLayout(media_layout)
        layout.addWidget(media_card)

        # ---- 🌐 隧道配置卡片 ----
        tunnel_card = QFrame()
        tunnel_card.setObjectName("card")
        tunnel_card.setMaximumWidth(700)
        tunnel_layout = QVBoxLayout()
        tunnel_layout.setSpacing(12)
        tunnel_layout.setContentsMargins(28, 24, 28, 24)

        tunnel_title = QLabel("🌐 内网穿透设置")
        tunnel_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        tunnel_layout.addWidget(tunnel_title)

        hint_tunnel = QLabel("启用后可获得公网URL，外网用户也能访问本服务。需先在 ngrok.com 注册免费账号获取 Auth Token。")
        hint_tunnel.setStyleSheet(f"font-size:11px;color:{COLORS['text_lighter']};margin-bottom:4px;")
        hint_tunnel.setWordWrap(True)
        tunnel_layout.addWidget(hint_tunnel)

        # 启用/禁用
        self.cfg_tunnel_enabled = QCheckBox("启用内网穿透")
        self.cfg_tunnel_enabled.setStyleSheet(f"font-weight:600;font-size:13px;")
        tunnel_layout.addWidget(self.cfg_tunnel_enabled)

        # 后端选择
        tunnel_layout.addWidget(QLabel("隧道后端"))
        self.cfg_tunnel_backend = QComboBox()
        self.cfg_tunnel_backend.addItems(["serveo (SSH免费免注册)", "localhost_run (SSH备选)", "pyngrok (需注册)", "禁用"])
        tunnel_layout.addWidget(self.cfg_tunnel_backend)

        # Auth Token
        tunnel_layout.addWidget(QLabel("Ngrok Auth Token"))
        self.cfg_tunnel_token = QLineEdit()
        self.cfg_tunnel_token.setPlaceholderText("在 https://ngrok.com 注册后获取")
        self.cfg_tunnel_token.setEchoMode(QLineEdit.EchoMode.Password)
        tunnel_layout.addWidget(self.cfg_tunnel_token)

        # 公网URL 状态
        self.cfg_tunnel_url = QLabel("")
        self.cfg_tunnel_url.setStyleSheet(f"font-size:13px;font-family:monospace;padding:8px;border-radius:10px;")
        self.cfg_tunnel_url.setWordWrap(True)
        tunnel_layout.addWidget(self.cfg_tunnel_url)

        tunnel_save = QPushButton("💾 保存隧道设置并重启")
        tunnel_save.setObjectName("btnPrimary")
        tunnel_save.setFixedHeight(40)
        tunnel_save.clicked.connect(self._save_tunnel_settings)
        tunnel_layout.addWidget(tunnel_save)

        tunnel_card.setLayout(tunnel_layout)
        layout.addWidget(tunnel_card)

        # ---- 📋 订单设置卡片 ----
        order_cfg_card = QFrame()
        order_cfg_card.setObjectName("card")
        order_cfg_card.setMaximumWidth(700)
        order_cfg_layout = QVBoxLayout()
        order_cfg_layout.setSpacing(12)
        order_cfg_layout.setContentsMargins(28, 24, 28, 24)

        order_cfg_title = QLabel("📋 订单设置")
        order_cfg_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        order_cfg_layout.addWidget(order_cfg_title)

        order_cfg_layout.addWidget(QLabel("默认金额 (元)"))
        self.cfg_default_amount = QLineEdit("0.00")
        order_cfg_layout.addWidget(self.cfg_default_amount)

        order_cfg_layout.addWidget(QLabel("未付订单过期时间 (分钟)"))
        self.cfg_order_expiry = QLineEdit("30")
        order_cfg_layout.addWidget(self.cfg_order_expiry)

        order_cfg_save = QPushButton("💾 保存订单设置")
        order_cfg_save.setObjectName("btnPrimary")
        order_cfg_save.setFixedHeight(40)
        order_cfg_save.clicked.connect(self._save_order_settings)
        order_cfg_layout.addWidget(order_cfg_save)

        order_cfg_card.setLayout(order_cfg_layout)
        layout.addWidget(order_cfg_card)

        # 当前配置摘要卡片
        summary_card = QFrame()
        summary_card.setObjectName("card")
        summary_card.setMaximumWidth(700)
        summary_layout = QVBoxLayout()
        summary_layout.setSpacing(8)
        summary_layout.setContentsMargins(28, 20, 28, 20)

        summary_title = QLabel("📋 当前配置摘要")
        summary_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{COLORS['text']};")
        summary_layout.addWidget(summary_title)

        self.summary_labels = {}
        for icon, key, label in [
            ("💳", "summary_payment", "支付接口"),
            ("📹", "summary_video", "视频上传"),
            ("📁", "summary_path", "软件包路径"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{icon} {label}:"))
            val_lbl = QLabel("加载中...")
            val_lbl.setObjectName(key)
            val_lbl.setStyleSheet(f"font-size:12px;color:{COLORS['text_light']};font-family:monospace;")
            val_lbl.setWordWrap(True)
            row.addWidget(val_lbl, stretch=1)
            summary_layout.addLayout(row)
            self.summary_labels[key] = val_lbl

        summary_card.setLayout(summary_layout)
        layout.addWidget(summary_card)

        layout.addStretch()
        inner.setLayout(layout)
        scroll.setWidget(inner)
        return scroll

    # --------------------------------------------------------
    #  Tab 3: 操作日志
    # --------------------------------------------------------
    def _build_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        header_row = QHBoxLayout()
        title = QLabel("📋 最近操作日志")
        title.setStyleSheet(f"font-size:16px;font-weight:700;color:{COLORS['text']};")
        header_row.addWidget(title)
        header_row.addStretch()

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._load_logs)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(3)
        self.logs_table.setHorizontalHeaderLabels(["时间", "操作", "详情"])
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        self.logs_table.setColumnWidth(0, 180)
        self.logs_table.setColumnWidth(1, 140)
        self.logs_table.verticalHeader().setVisible(False)
        self.logs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.logs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.logs_table, stretch=1)

        widget.setLayout(layout)
        return widget

    # --------------------------------------------------------
    #  数据加载
    # --------------------------------------------------------
    def _load_all(self):
        self._load_stats()
        self._load_records()
        self._load_orders()
        self._load_settings()
        self._load_logs()

    def _load_stats(self):
        try:
            conn = get_db_connection()
            total = conn.execute("SELECT COUNT(*) as c FROM registration_codes").fetchone()["c"]
            paid = conn.execute("SELECT COUNT(*) as c FROM registration_codes WHERE is_paid=1").fetchone()["c"]
            unpaid = total - paid
            downloads = conn.execute("SELECT COALESCE(SUM(download_count),0) as c FROM software_packages").fetchone()["c"]
            today = datetime.now().strftime("%Y-%m-%d")
            today_new = conn.execute(
                "SELECT COUNT(*) as c FROM registration_codes WHERE date(created_at)=?", (today,)
            ).fetchone()["c"]
            # 订单统计
            total_orders = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
            pending_orders = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status='pending'").fetchone()["c"]
            revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) as c FROM orders WHERE status='paid'").fetchone()["c"]
            conn.close()

            self.stat_cards["statTotal"].setText(str(total))
            self.stat_cards["statPaid"].setText(str(paid))
            self.stat_cards["statUnpaid"].setText(str(unpaid))
            self.stat_cards["statDownloads"].setText(str(downloads))
            self.stat_cards["statToday"].setText(str(today_new))
            self.stat_cards["statOrders"].setText(str(total_orders))
            self.stat_cards["statPendingOrd"].setText(str(pending_orders))
            self.stat_cards["statRevenue"].setText(f"¥{revenue:.2f}")

            # ---- 隧道状态 ----
            self._update_tunnel_status()
        except Exception as e:
            print(f"load_stats error: {e}")

    def _update_tunnel_status(self):
        """更新顶部隧道状态指示器"""
        try:
            conn = get_db_connection()
            row = conn.execute(
                "SELECT value FROM server_config WHERE key='tunnel_public_url'"
            ).fetchone()
            conn.close()
            url = (row["value"] if row else "").strip()
            if url:
                short = url[:50] + "..." if len(url) > 50 else url
                self.tunnel_status_lbl.setText(f"🟢 公网已连接: {short}")
                self.tunnel_status_lbl.setStyleSheet(
                    f"font-size:11px; color:{COLORS['success']}; margin-right:16px; font-weight:600;")
                self.tunnel_status_lbl.setToolTip(url)
            else:
                self.tunnel_status_lbl.setText("🔴 公网未连接")
                self.tunnel_status_lbl.setStyleSheet(
                    f"font-size:11px; color:{COLORS['danger']}; margin-right:16px;")
                self.tunnel_status_lbl.setToolTip("请在系统设置中配置并启用内网穿透")
        except Exception:
            pass

    def _load_records(self):
        try:
            status = self.status_combo.currentIndex() if hasattr(self, 'status_combo') else 0
            search = self.search_input.text().strip() if hasattr(self, 'search_input') else ""

            where = "WHERE 1=1"
            params = []
            if status == 1:  # 已付款
                where += " AND is_paid=1"
            elif status == 2:  # 待付款
                where += " AND is_paid=0"

            if search:
                where += " AND (fingerprint LIKE ? OR reg_code LIKE ? OR user_note LIKE ?)"
                like = f"%{search}%"
                params.extend([like, like, like])

            conn = get_db_connection()
            total = conn.execute(f"SELECT COUNT(*) as c FROM registration_codes {where}", params).fetchone()["c"]

            per_page = 25
            self._total_pages = max(1, (total + per_page - 1) // per_page)
            if self._current_page > self._total_pages:
                self._current_page = self._total_pages

            offset = (self._current_page - 1) * per_page
            rows = conn.execute(
                f"SELECT * FROM registration_codes {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [per_page, offset]
            ).fetchall()

            self.records_table.setRowCount(0)
            self.records_table.setRowCount(len(rows))

            for i, r in enumerate(rows):
                fp = r["fingerprint"]
                fp_display = fp[:20] + "..." if len(fp) > 20 else fp

                self.records_table.setItem(i, 0, self._cell(str(r["id"])))
                self.records_table.setItem(i, 1, self._cell(fp_display))
                self.records_table.setItem(i, 2, self._cell(r["reg_code"], bold=True, mono=True))
                self.records_table.setItem(i, 3, self._cell(r["user_note"] or "-"))
                self.records_table.setItem(i, 4, self._cell(
                    "✅ 已付款" if r["is_paid"] else "⏳ 待付款",
                    color="#3A7D5A" if r["is_paid"] else "#B08030",
                    bold=True
                ))
                self.records_table.setItem(i, 5, self._cell(r["created_at"] or ""))
                self.records_table.setItem(i, 6, self._cell(r["paid_at"] or "-"))

                # 操作按钮
                rid = r["id"]
                is_paid = r["is_paid"]

                if is_paid:
                    btn_unpay = QPushButton("取消付款")
                    btn_unpay.setStyleSheet(f"font-size:11px;color:{COLORS['danger']};padding:4px 10px;")
                    btn_unpay.clicked.connect(lambda checked, rid=rid: self._toggle_paid(rid, False))
                    self.records_table.setCellWidget(i, 7, btn_unpay)
                else:
                    btn_pay = QPushButton("标记已付")
                    btn_pay.setObjectName("btnSuccess")
                    btn_pay.setStyleSheet("font-size:11px;padding:4px 10px;")
                    btn_pay.clicked.connect(lambda checked, rid=rid: self._toggle_paid(rid, True))
                    self.records_table.setCellWidget(i, 7, btn_pay)

                btn_del = QPushButton("删除")
                btn_del.setObjectName("btnDanger")
                btn_del.setStyleSheet("font-size:11px;padding:4px 10px;")
                btn_del.clicked.connect(lambda checked, rid=rid: self._delete_record(rid))
                self.records_table.setCellWidget(i, 8, btn_del)

            self.records_table.setRowCount(len(rows))  # ensure

            conn.close()

            self.page_label.setText(f"共 {total} 条 · 第 {self._current_page}/{self._total_pages} 页")
            self.prev_btn.setEnabled(self._current_page > 1)
            self.next_btn.setEnabled(self._current_page < self._total_pages)
        except Exception as e:
            print(f"load_records error: {e}")

    def _cell(self, text, bold=False, mono=False, color=None):
        item = QTableWidgetItem(text)
        font = QFont()
        font.setBold(bold)
        if mono:
            font.setFamily("Consolas, Courier New, monospace")
        item.setFont(font)
        if color:
            item.setForeground(QBrush(QColor(color)))
        return item

    def _toggle_paid(self, rid, paid):
        action = "标记为已付款" if paid else "取消已付款标记"
        reply = QMessageBox.question(
            self, "确认操作", f"确认{action}？（ID: {rid}）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = get_db_connection()
        row = conn.execute("SELECT reg_code FROM registration_codes WHERE id=?", (rid,)).fetchone()
        if not row:
            conn.close()
            return

        if paid:
            conn.execute(
                "UPDATE registration_codes SET is_paid=1, paid_at=datetime('now','localtime') WHERE id=?",
                (rid,)
            )
        else:
            conn.execute("UPDATE registration_codes SET is_paid=0, paid_at=NULL WHERE id=?", (rid,))

        conn.commit()
        conn.close()

        write_log("mark_paid" if paid else "unmark_paid", f"注册码 {row['reg_code']} {action}")
        self._load_stats()
        self._load_records()
        self._load_logs()

    def _delete_record(self, rid):
        reply = QMessageBox.question(
            self, "确认删除", f"确认删除该注册码记录？（ID: {rid}）\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = get_db_connection()
        row = conn.execute("SELECT reg_code FROM registration_codes WHERE id=?", (rid,)).fetchone()
        if row:
            conn.execute("DELETE FROM registration_codes WHERE id=?", (rid,))
            conn.commit()
            write_log("delete_record", f"删除注册码 {row['reg_code']}")
        conn.close()

        self._load_stats()
        self._load_records()
        self._load_logs()

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_records()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_records()

    def _upload_package(self):
        dlg = UploadPackageDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load_stats()
            self._load_logs()

    # --------------------------------------------------------
    #  系统设置
    # --------------------------------------------------------
    def _load_settings(self):
        try:
            conn = get_db_connection()
            rows = conn.execute("SELECT key, value FROM server_config").fetchall()
            config = {r["key"]: r["value"] for r in rows}
            conn.close()

            self.cfg_payment.setText(config.get("payment_api_url", ""))
            self.cfg_video.setText(config.get("video_upload_url", ""))
            self.cfg_path.setText(config.get("software_package_path", ""))

            # 媒体配置
            self.cfg_video_file.setText(config.get("hero_video_filename", ""))
            self.cfg_qr_file.setText(config.get("payment_qr_filename", ""))
            self.cfg_payment_instructions.setPlainText(config.get("payment_instructions", ""))

            # 隧道配置
            self.cfg_tunnel_enabled.setChecked(config.get("tunnel_enabled", "1") == "1")
            backend = config.get("tunnel_backend", "serveo")
            backend_map = {
                "serveo": "serveo (SSH免费免注册)",
                "localhost_run": "localhost_run (SSH备选)",
                "pyngrok": "pyngrok (需注册)",
                "disabled": "禁用",
            }
            self.cfg_tunnel_backend.setCurrentText(backend_map.get(backend, "serveo (SSH免费免注册)"))
            self.cfg_tunnel_token.setText(config.get("tunnel_ngrok_auth_token", ""))
            pub_url = config.get("tunnel_public_url", "").strip()
            if pub_url:
                self.cfg_tunnel_url.setText(f"🟢 {pub_url}")
                self.cfg_tunnel_url.setStyleSheet(
                    f"font-size:13px;font-family:monospace;padding:8px;border-radius:10px;"
                    f"background:{COLORS['success_pale']};color:{COLORS['success']};")
            else:
                self.cfg_tunnel_url.setText("🔴 未连接")
                self.cfg_tunnel_url.setStyleSheet(
                    f"font-size:13px;font-family:monospace;padding:8px;border-radius:10px;"
                    f"background:{COLORS['warning_pale']};color:{COLORS['text_light']};")

            # 订单配置
            self.cfg_default_amount.setText(config.get("default_amount", "0.00"))
            self.cfg_order_expiry.setText(config.get("order_expiry_minutes", "30"))

            self.summary_labels["summary_payment"].setText(config.get("payment_api_url", "未设置"))
            self.summary_labels["summary_video"].setText(config.get("video_upload_url", "未设置"))
            self.summary_labels["summary_path"].setText(config.get("software_package_path", "未设置"))
        except Exception as e:
            print(f"load_settings error: {e}")

    def _save_tunnel_settings(self):
        """保存隧道配置并尝试重启"""
        enabled = "1" if self.cfg_tunnel_enabled.isChecked() else "0"
        backend_display = self.cfg_tunnel_backend.currentText()
        # 映射显示值 → 实际值
        backend_map = {
            "serveo (SSH免费免注册)": "serveo",
            "localhost_run (SSH备选)": "localhost_run",
            "pyngrok (需注册)": "pyngrok",
            "禁用": "disabled",
        }
        backend = backend_map.get(backend_display, "serveo")
        token = self.cfg_tunnel_token.text().strip()

        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", ("tunnel_enabled", enabled))
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", ("tunnel_backend", backend))
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", ("tunnel_ngrok_auth_token", token))
        conn.commit()
        conn.close()

        write_log("tunnel_config", f"隧道配置更新: 启用={enabled} 后端={backend}")
        QMessageBox.information(self, "成功", "隧道配置已保存。\n请重启 Web 服务 (app.py) 以使隧道配置生效。\n或通过 Web 管理后台的隧道设置页面在线重启。")
        self._load_settings()

    def _save_order_settings(self):
        """保存订单设置"""
        amount = self.cfg_default_amount.text().strip()
        expiry = self.cfg_order_expiry.text().strip()

        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", ("default_amount", amount))
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", ("order_expiry_minutes", expiry))
        conn.commit()
        conn.close()

        write_log("update_settings", f"订单设置更新: 金额={amount} 过期={expiry}分钟")
        QMessageBox.information(self, "成功", "订单设置已保存")
        self._load_settings()

    def _save_settings(self):
        config_data = {
            "payment_api_url": self.cfg_payment.text().strip(),
            "video_upload_url": self.cfg_video.text().strip(),
            "software_package_path": self.cfg_path.text().strip(),
        }

        conn = get_db_connection()
        for k, v in config_data.items():
            conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)", (k, v))
        conn.commit()
        conn.close()

        write_log("update_settings", f"更新了 {len(config_data)} 项配置")
        self._load_settings()
        self._load_logs()
        QMessageBox.information(self, "成功", "配置已保存成功")

    def _save_media_settings(self):
        """保存媒体设置（付款说明文字）"""
        instructions = self.cfg_payment_instructions.toPlainText().strip()
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                     ("payment_instructions", instructions))
        conn.commit()
        conn.close()
        write_log("update_settings", "更新付款说明文字")
        QMessageBox.information(self, "成功", "付款说明已保存")

    def _browse_media(self, media_type):
        """浏览选择媒体文件"""
        if media_type == "hero_video":
            path, _ = QFileDialog.getOpenFileName(
                self, "选择首页视频", "",
                "视频文件 (*.mp4 *.webm);;所有文件 (*.*)"
            )
            if path:
                self._pending_media_path = path
                self.cfg_video_file.setText(Path(path).name)
        elif media_type == "payment_qr":
            path, _ = QFileDialog.getOpenFileName(
                self, "选择付款二维码", "",
                "图片文件 (*.png *.jpg *.jpeg);;所有文件 (*.*)"
            )
            if path:
                self._pending_media_path = path
                self.cfg_qr_file.setText(Path(path).name)

    def _upload_media(self, media_type):
        """上传媒体文件到 MEDIA_DIR"""
        if not hasattr(self, '_pending_media_path') or not self._pending_media_path:
            QMessageBox.warning(self, "提示", "请先浏览选择文件")
            return

        src = Path(self._pending_media_path)
        if not src.exists():
            QMessageBox.warning(self, "提示", "文件不存在")
            return

        config_key = "hero_video_filename" if media_type == "hero_video" else "payment_qr_filename"
        prefix = "hero_video" if media_type == "hero_video" else "payment_qr"
        ext = src.suffix.lower()
        new_filename = f"{prefix}{ext}"

        # 删除旧文件
        conn = get_db_connection()
        old = conn.execute("SELECT value FROM server_config WHERE key=?", (config_key,)).fetchone()
        if old and old["value"]:
            old_path = MEDIA_DIR / old["value"]
            try:
                if old_path.exists():
                    old_path.unlink()
            except Exception:
                pass

        # 复制新文件
        dest = MEDIA_DIR / new_filename
        try:
            shutil.copy2(str(src), str(dest))
        except Exception as e:
            conn.close()
            QMessageBox.critical(self, "错误", f"复制文件失败: {e}")
            return

        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                     (config_key, new_filename))
        conn.commit()
        conn.close()

        label = "视频" if media_type == "hero_video" else "二维码"
        write_log("upload_media", f"上传{label}: {new_filename}")

        if media_type == "hero_video":
            self.cfg_video_file.setText(new_filename)
        else:
            self.cfg_qr_file.setText(new_filename)

        QMessageBox.information(self, "成功", f"{label}上传成功！\n首页刷新后生效。")

    def _clear_media(self, media_type):
        """清除媒体文件"""
        config_key = "hero_video_filename" if media_type == "hero_video" else "payment_qr_filename"
        label = "视频" if media_type == "hero_video" else "二维码"

        reply = QMessageBox.question(
            self, "确认清除", f"确认清除已上传的{label}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = get_db_connection()
        old = conn.execute("SELECT value FROM server_config WHERE key=?", (config_key,)).fetchone()
        if old and old["value"]:
            old_path = MEDIA_DIR / old["value"]
            try:
                if old_path.exists():
                    old_path.unlink()
            except Exception:
                pass

        conn.execute("INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                     (config_key, ""))
        conn.commit()
        conn.close()

        if media_type == "hero_video":
            self.cfg_video_file.setText("")
        else:
            self.cfg_qr_file.setText("")

        write_log("delete_media", f"清除{label}")
        QMessageBox.information(self, "成功", f"{label}已清除")

    def _browse_folder(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            line_edit.setText(path)

    # --------------------------------------------------------
    #  操作日志
    # --------------------------------------------------------
    def _load_logs(self):
        try:
            conn = get_db_connection()
            rows = conn.execute("SELECT * FROM admin_log ORDER BY id DESC LIMIT 100").fetchall()
            conn.close()

            self.logs_table.setRowCount(len(rows))
            action_map = {
                "admin_login": "🔐 管理员登录",
                "mark_paid": "✅ 标记已付",
                "unmark_paid": "↩️ 取消已付",
                "delete_record": "🗑️ 删除记录",
                "new_registration": "🆕 新注册",
                "new_order": "📋 新订单",
                "upload_package": "📤 上传软件包",
                "update_settings": "⚙️ 更新配置",
                "toggle_package": "🔄 上下架",
                "delete_package": "🗑️ 删除软件包",
                "upload_media": "📁 上传媒体",
                "delete_media": "🗑️ 删除媒体",
                "tunnel_connected": "🌐 隧道已连接",
                "tunnel_disconnected": "🔒 隧道已断开",
                "tunnel_config": "⚙️ 隧道配置",
                "tunnel_reconnected": "🌐 隧道重连",
                "tunnel_error": "❌ 隧道错误",
                "tunnel_health_fail": "⚠️ 隧道健康检查失败",
                "order_status_update": "📋 订单状态更新",
                "orders_expired": "⏰ 订单过期处理",
                "delete_order": "🗑️ 删除订单",
                "payment_verified": "💳 支付验证通过",
                "payment_simulated": "🧪 模拟支付",
            }
            for i, r in enumerate(rows):
                self.logs_table.setItem(i, 0, self._cell(r["created_at"] or ""))
                self.logs_table.setItem(i, 1, self._cell(
                    action_map.get(r["action"], r["action"])
                ))
                self.logs_table.setItem(i, 2, self._cell(r["detail"] or ""))
        except Exception as e:
            print(f"load_logs error: {e}")


# ============================================================
# 入口
# ============================================================
def main():
    init_db()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_QSS)

    # 登录
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    # 主窗口
    window = AdminMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
