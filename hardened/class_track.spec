# -*- coding: utf-8 -*-
# ClassTrack Hardened - PyInstaller spec file
# ============================================
# Usage: pyinstaller --clean class_track.spec
# Or:    python -m PyInstaller class_track.spec

import sys
from pathlib import Path

# --- Configuration ---
APP_NAME = "ClassTrack"
APP_VERSION = "2.0.0"
ENTRY_SCRIPT = "class_track_core.py"  # Updated from build.py output
OUTPUT_DIR = "dist"
WORK_DIR = "build"

# --- PyInstaller Analysis ---
block_cipher = None  # PyArmor will set this

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle encrypted activation module if it exists
        ('../activation/*.py', 'activation'),
        ('../activation/*.pem', 'activation'),
    ],
    hiddenimports=[
        # Core
        'flask', 'werkzeug', 'jinja2', 'markupsafe',
        'cryptography', 'cryptography.fernet',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.asymmetric',
        'cryptography.hazmat.primitives.serialization',
        'cryptography.x509',
        'cryptography.x509.oid',
        # Database
        'pysqlcipher3', 'pysqlcipher3.dbapi2',
        'sqlite3',
        # Data
        'pandas', 'openpyxl', 'xlrd',
        'qrcode', 'qrcode.image',
        'PIL', 'PIL.Image',
        # System
        'ctypes', 'ctypes.windll',
        'subprocess', 'socket', 'threading',
        'hashlib', 'base64', 'json', 're',
        'tempfile', 'shutil', 'pathlib',
        # Activation (if embedded)
        'activation', 'activation.hardware_id',
        'activation.license_manager',
        'activation.crypto', 'activation.key_pair',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused/development modules
        'tkinter', 'unittest', 'test', 'pydoc',
        'distutils', 'setuptools', 'pip',
        'email', 'http', 'html', 'xml', 'xmlrpc',
        'pdb', 'profile', 'cProfile',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out unnecessary binary duplicates
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (windowed mode)
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # PyInstaller encryption key (different from Fernet/SQLCipher keys)
    # Generate unique key per build
    icon='../static/favicon.ico' if Path('../static/favicon.ico').exists() else None,
)

# Also create a directory build option (for debugging)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
