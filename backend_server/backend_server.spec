# -*- mode: python ; coding: utf-8 -*-
"""
ClassTrack Backend Server — PyInstaller 打包配置
=================================================
入口: app.py (Flask Web 服务)
同时包含: admin_app.py (PyQt6 管理桌面端)
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]
binaries = []
hiddenimports = [
    # Flask & web
    'flask', 'flask.json', 'werkzeug', 'jinja2',
    'sqlite3',
    # Activation module (共享)
    'activation', 'activation.hardware_id', 'activation.crypto',
    'activation.key_pair', 'activation.license_manager',
    # PyQt6 (admin_app.py)
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'PyQt6.sip',
    # pyngrok (tunnel)
    'pyngrok', 'pyngrok.conf', 'pyngrok.ngrok',
    # Order utils
    'order_utils',
    # Tunnel module
    'tunnel', 'tunnel.base', 'tunnel.noop_backend',
    'tunnel.pyngrok_backend', 'tunnel.serveo_backend',
    'tunnel.subprocess_backend', 'tunnel.manager',
]

# ---- Collect jinja2 ----
tmp_ret = collect_all('jinja2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect PyQt6 ----
try:
    tmp_ret = collect_all('PyQt6')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
except Exception:
    pass

# ---- Collect activation ----
try:
    act_datas, act_bins, act_hidden = collect_all('activation')
    datas += act_datas; binaries += act_bins; hiddenimports += act_hidden
except Exception:
    pass

# Remove duplicates
hiddenimports = list(dict.fromkeys(hiddenimports))

# ---- 主 EXE: ClassTrack_Server (Web 服务) ----
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ClassTrack_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # 后端服务需要控制台输出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../ClassTrack.ico'],
)
