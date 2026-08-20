# -*- mode: python ; coding: utf-8 -*-
"""
ClassTrack 打包配置(FastAPI + Vue3 前后端分离架构)
====================================================
- 入口: launcher.py(开发/打包通用)
- 前端: frontend/dist(Vite 构建产物,由 FastAPI 托管)
- 数据: 运行时 %APPDATA%\\ClassTrack(见 backend/app/config.py),绝不打包 data\\ 目录

构建前置:
    cd frontend && npm run build      # 先生成 frontend/dist
    pyinstaller ClassTrack.spec
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# 前端构建产物(Vite dist)打包,prefix 与 app.config.FRONTEND_DIST 的 _MEIPASS 路径对齐
datas = [
    Tree('frontend/dist', prefix='frontend/dist', excludes=['*.map']),
]
binaries = []
hiddenimports = [
    # FastAPI / uvicorn 技术栈
    'fastapi', 'starlette', 'uvicorn', 'anyio', 'h11',
    # uvicorn 懒加载模块(importlib 动态导入,PyInstaller 静态分析不到)
    'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'uvicorn.logging', 'uvicorn.main', 'uvicorn.server', 'uvicorn.config',
    # 表单/文件上传(FastAPI UploadFile 依赖)
    'multipart', 'multipart.multipart',
    # 邮件模块(HTTP 响应头编码)
    'email.mime', 'email.mime.text', 'email.mime.multipart',
    # 数据与导出
    'pandas', 'openpyxl', 'xlrd',
    # AI 调用
    'requests', 'urllib3',
    # Cryptography(自建 CA / TLS 证书生成)
    'cryptography', 'cryptography.hazmat', 'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.x509', 'cryptography.x509.oid',
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

# ---- Collect cryptography ----
tmp_ret = collect_all('cryptography')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect Pillow (包括所有图像插件和 C extensions) ----
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect qrcode ----
tmp_ret = collect_all('qrcode')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- Collect 应用激活模块(纯源码,无数据文件;显式列出防静态分析遗漏) ----
hiddenimports += [
    'app', 'app.main', 'app.config', 'app.database', 'app.deps', 'app.utils',
    'app.activation', 'app.activation.crypto', 'app.activation.hardware_id',
    'app.activation.key_pair', 'app.activation.license_manager',
    'app.services', 'app.services.tls_service', 'app.services.ai_service',
    'app.services.report_service',
]

# Remove duplicates
hiddenimports = list(dict.fromkeys(hiddenimports))

a = Analysis(
    ['launcher.py'],
    pathex=['backend'],   # 让 PyInstaller 能解析 `app` 包
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
    name='ClassTrack',
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
