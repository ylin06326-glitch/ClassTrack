# -*- coding: utf-8 -*-
"""
应用配置与数据路径管理
======================
统一管理数据目录位置,解决打包分发后的两个问题:

1. exe 放在无写权限目录(Program Files / 共享盘 / 压缩包直接双击)
   时无法创建 data 目录导致保存失败。
   → 打包版数据目录固定为 %APPDATA%\\ClassTrack。

2. 老版本数据存放在 exe 同级 data\\ 目录,升级后自动迁移到新位置,
   避免用户"升级后数据不见了"。

开发模式(源码运行)仍使用项目根目录下的 data\\,方便调试。
"""

import os
import sys
from pathlib import Path

APP_NAME = "ClassTrack"
APP_VERSION = "2.0.0"

# 项目根目录(backend/ 的上一级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 前端构建产物目录(fastapi 托管用)
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def is_frozen() -> bool:
    """是否为 PyInstaller 打包后的运行环境"""
    return bool(getattr(sys, "frozen", False))


def get_exe_dir() -> Path | None:
    """打包环境下 exe 所在目录;开发环境返回 None"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return None


def get_data_dir(exe_dir: Path | None = None) -> Path:
    """
    数据目录:
    - 打包版: %APPDATA%\\ClassTrack(APPDATA 不可用时退回 exe 同级 data\\)
    - 开发版: 项目根目录 data\\
    """
    if is_frozen():
        exe_dir = exe_dir or get_exe_dir()
        appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
        return (exe_dir / "data") if exe_dir else Path("data")
    return PROJECT_ROOT / "data"


def get_legacy_data_dir(exe_dir: Path | None = None) -> Path | None:
    """旧版数据目录(exe 同级 data\\);开发环境无旧目录概念,返回 None"""
    if not is_frozen():
        return None
    exe_dir = exe_dir or get_exe_dir()
    return (exe_dir / "data") if exe_dir else None


def migrate_legacy_data(data_dir: Path, legacy_dir: Path | None) -> bool:
    """
    把旧版 exe 同级 data\\ 目录整体迁移到新数据目录。
    仅当新数据目录中还没有数据库文件时执行(绝不覆盖已有新数据)。
    迁移失败不阻塞启动(旧数据仍保留在原处)。
    """
    if legacy_dir is None or not legacy_dir.exists():
        return False
    try:
        if (data_dir / "classtrack.db").exists():
            return False
        import shutil

        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy_dir, data_dir, dirs_exist_ok=True)
        print(f"  📦 已迁移旧数据: {legacy_dir} -> {data_dir}")
        return True
    except Exception as e:
        print(f"  ⚠️ 旧数据迁移失败(不影响启动,数据仍在原处): {e}")
        return False


def ensure_data_dir() -> Path:
    """确保数据目录存在并返回其路径(启动时调用,含旧数据迁移)"""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    migrate_legacy_data(data_dir, get_legacy_data_dir())
    return data_dir


def get_db_path() -> Path:
    """数据库文件路径"""
    return ensure_data_dir() / "classtrack.db"
