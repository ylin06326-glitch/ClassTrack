# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['class_track_core.py'],
    pathex=[],
    binaries=[],
    datas=[('../activation', 'activation')],
    hiddenimports=['flask', 'cryptography', 'cryptography.fernet', 'pandas', 'openpyxl', 'qrcode', 'PIL', 'sqlcipher3', 'sqlcipher3.dbapi2', 'activation', 'activation.hardware_id', 'activation.license_manager', 'activation.crypto', 'activation.key_pair'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
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
    name='ClassTrack_V2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)
