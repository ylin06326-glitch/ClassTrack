#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack — 内网穿透隧道模块
==============================
抽象基类 + TunnelError 异常定义
"""

from abc import ABC, abstractmethod


class TunnelError(Exception):
    """隧道连接/重连失败时抛出"""
    pass


class BaseTunnelBackend(ABC):
    """所有隧道后端的抽象基类"""

    @abstractmethod
    def connect(self, port: int) -> str:
        """建立隧道连接，返回公网 URL。失败时抛出 TunnelError"""
        ...

    @abstractmethod
    def disconnect(self):
        """断开隧道连接，释放资源"""
        ...

    @abstractmethod
    def get_public_url(self) -> str | None:
        """返回当前公网 URL，未连接时返回 None"""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """返回 True 表示隧道当前处于活动状态"""
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """供 UI 显示的可读名称"""
        ...
