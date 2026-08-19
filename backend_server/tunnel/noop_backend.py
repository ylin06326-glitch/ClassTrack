#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空隧道后端 — 用户禁用内网穿透时使用
"""

from .base import BaseTunnelBackend


class NoopTunnelBackend(BaseTunnelBackend):
    """禁用隧道时的空实现"""

    def connect(self, port: int) -> str:
        return ""

    def disconnect(self):
        pass

    def get_public_url(self) -> str | None:
        return None

    def is_connected(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "禁用"
