# -*- coding: utf-8 -*-
"""
ClassTrack 打包版启动入口(PyInstaller)
======================================
- 开发模式:把 backend/ 加入 sys.path 后启动
- 打包模式:app 包已在 PYZ 内,sys.path 无需修改

用法: python launcher.py  (或打包后双击 ClassTrack.exe)
"""

import os
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import run_server  # noqa: E402

if __name__ == "__main__":
    # 支持环境变量覆盖端口(调试用)
    port = int(os.environ.get("CLASSTRACK_PORT", "5088"))
    run_server(port=port)
