# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# 手动收集目录文件（替代 Tree，兼容 PyInstaller 6.x）
def collect_tree(src_dir, prefix, excludes=None):
    result = []
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if excludes and any(f.endswith(ext) for ext in excludes):
                continue
            src = os.path.join(root, f)
            rel = os.path.relpath(src, src_dir)
            dest = os.path.join(prefix, rel).replace('\\', '/')
            result.append((src, dest))
    return result

datas = collect_tree('templates', 'templates', ['.bak']) + collect_tree('static', 'static', ['.bak'])
binaries = []
hiddenimports = [
    # Flask & web
    'flask', 'flask.json', 'werkzeug', 'jinja2',
    # Data processing
    'pandas', 'openpyxl', 'xlrd', 'sqlite3',
    # Cryptography (for SSL/TLS cert generation)
    'cryptography', 'cryptography.hazmat', 'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.x509', 'cryptography.x509.oid',
    # Activation module
    'activation', 'activation.hardware_id', 'activation.crypto',
    'activation.key_pair', 'activation.license_manager',
    # ======== QR Code + Pillow (关键: 二维码生成) ========
    'qrcode', 'qrcode.image', 'qrcode.image.pil', 'qrcode.image.styledpil',
    'qrcode.image.styles', 'qrcode.image.colors',
    'qrcode.image.svg', 'qrcode.image.pure',
    'qrcode.main', 'qrcode.util', 'qrcode.constants',
    # Pillow / PIL core
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageDraw2',
    'PIL.ImageFont', 'PIL.ImageFilter', 'PIL.ImageColor', 'PIL.ImageOps',
    'PIL.ImageFile', 'PIL.ImageMode', 'PIL.ImagePalette', 'PIL.ImagePath',
    'PIL.ImageSequence', 'PIL.ImageStat', 'PIL.ImageText',
    'PIL.ImageTransform', 'PIL.ImageEnhance', 'PIL.ImageMath',
    'PIL.ImageCms', 'PIL.ImageShow', 'PIL.ImageGrab',
    'PIL._imaging', 'PIL._util', 'PIL._binary',
    # PIL image format plugins (PNG is essential for QR codes)
    'PIL.PngImagePlugin', 'PIL.JpegImagePlugin', 'PIL.GifImagePlugin',
    'PIL.BmpImagePlugin', 'PIL.IcoImagePlugin', 'PIL.TiffImagePlugin',
    'PIL.WebPImagePlugin', 'PIL.PpmImagePlugin',
    # PIL C extension modules
    'PIL._imagingft', 'PIL._imagingmath', 'PIL._imagingcms',
]

# ---- Collect jinja2 ----
tmp_ret = collect_all('jinja2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect cryptography ----
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect Pillow (包括所有图像插件和 C extensions) ----
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect qrcode ----
tmp_ret = collect_all('qrcode')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect activation（排除商家私钥/商家工具/手机端工程，防止随 exe 分发） ----
act_datas, act_bins, act_hidden = collect_all('activation')
def _keep_activation_datas(src_path):
    s = src_path.replace('\\', '/')
    if '/mobile/' in s:        # 手机端 Capacitor 工程（含 node_modules），打包无需
        return False
    if '__pycache__' in s:     # 缓存目录
        return False
    if s.endswith('private_key.pem'):   # 商家私钥，绝不能进 exe
        return False
    if s.endswith('merchant_tool.py'):  # 商家工具，仅开发者使用
        return False
    return True
act_datas = [(s, d) for s, d in act_datas if _keep_activation_datas(s)]
datas += act_datas; binaries += act_bins; hiddenimports += act_hidden

# Remove duplicates
hiddenimports = list(dict.fromkeys(hiddenimports))
hiddenimports += ['app_paths']  # 数据目录管理模块（APPDATA 迁移）

a = Analysis(
    ['main_nolock.py'],
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
    name='ClassTrack-Free',
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
    icon=['ClassTrack.ico'],
)
