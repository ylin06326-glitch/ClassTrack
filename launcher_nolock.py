# -*- coding: utf-8 -*-
"""
ClassTrack 打包版启动入口 — 免锁版(ClassTrack_nolock.spec 使用)
================================================================
与 launcher.py 相同,但关闭单实例锁(允许多开)。
"""

import os
import sys
from pathlib import Path

os.environ["CLASSTRACK_NO_LOCK"] = "1"

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import run_server  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("CLASSTRACK_PORT", "5088"))
    run_server(port=port)
