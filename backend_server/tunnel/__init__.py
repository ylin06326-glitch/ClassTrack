#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack 内网穿透模块
=======================
用法:
    from tunnel import TunnelManager

    tunnel = TunnelManager()
    tunnel.set_db_path(db_path)
    if tunnel.is_enabled():
        url = tunnel.start(port=5099)
        print(f"公网地址: {url}")
"""

from .base import BaseTunnelBackend, TunnelError
from .manager import TunnelManager

__all__ = ["TunnelManager", "BaseTunnelBackend", "TunnelError"]
