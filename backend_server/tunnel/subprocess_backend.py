#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子进程隧道基类 — 任何通过命令行启动的隧道工具均可继承此类
"""

import subprocess
import threading
import time
import re
from .base import BaseTunnelBackend, TunnelError


class SubprocessTunnelBackend(BaseTunnelBackend):
    """通过子进程运行隧道命令的通用后端

    子类只需实现:
      - _build_command(port) -> list[str]
      - _extract_url(line: str) -> str | None
      - backend_name 属性

    可选覆盖:
      - _startup_timeout: 等待 URL 出现的最大秒数 (默认 15)
    """

    _startup_timeout: float = 15.0

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._public_url: str | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    # ----------------------------------------------------------------
    #  子类必须实现
    # ----------------------------------------------------------------
    def _build_command(self, port: int) -> list[str]:
        raise NotImplementedError

    def _extract_url(self, line: str) -> str | None:
        raise NotImplementedError

    @property
    def backend_name(self) -> str:
        raise NotImplementedError

    # ----------------------------------------------------------------
    #  BaseTunnelBackend 接口
    # ----------------------------------------------------------------
    def connect(self, port: int) -> str:
        with self._lock:
            self.disconnect()
            cmd = self._build_command(port)
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                )
            except FileNotFoundError as e:
                raise TunnelError(f"未找到命令 '{cmd[0]}': {e}")
            except Exception as e:
                raise TunnelError(f"启动隧道进程失败: {e}")

            self._running = True
            self._public_url = None
            url_event = threading.Event()

            def reader():
                try:
                    for line in self._process.stdout:
                        if not self._running:
                            break
                        line = line.rstrip()
                        print(f"  [tunnel] {line}")  # 打印到控制台方便调试
                        if self._public_url is None:
                            url = self._extract_url(line)
                            if url:
                                self._public_url = url
                                url_event.set()
                except Exception:
                    pass

            self._reader_thread = threading.Thread(target=reader, daemon=True)
            self._reader_thread.start()

            # 等待 URL 出现
            if not url_event.wait(timeout=self._startup_timeout):
                self.disconnect()
                raise TunnelError(
                    f"隧道启动超时（{self._startup_timeout}秒未检测到公网URL）\n"
                    f"请检查网络连接，或尝试其他隧道后端"
                )

            return self._public_url

    def disconnect(self):
        with self._lock:
            self._running = False
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None
            self._public_url = None

    def get_public_url(self) -> str | None:
        return self._public_url

    def is_connected(self) -> bool:
        if not self._running or self._process is None:
            return False
        return self._process.poll() is None


# ============================================================
# 内置的 URL 提取器
# ============================================================

def extract_serveo_url(line: str) -> str | None:
    """从 serveo.net 输出中提取 URL"""
    match = re.search(r'(https?://[a-zA-Z0-9]+\.serveo\.net)', line)
    if match:
        return match.group(1)
    return None


def extract_localhost_run_url(line: str) -> str | None:
    """从 localhost.run 输出中提取 URL"""
    match = re.search(r'(https?://[a-zA-Z0-9]+\.localhost\.run)', line)
    if match:
        return match.group(1)
    # 也可能是 tunnel address 格式
    match = re.search(r'tunnel address[:\s]+(https?://\S+)', line, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_bore_url(line: str) -> str | None:
    """从 bore 输出中提取 URL"""
    match = re.search(r'listening at\s+(https?://\S+)', line, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'(bore\.pub:\d+)', line)
    if match:
        return f"http://{match.group(1)}"
    return None


def extract_generic_url(line: str) -> str | None:
    """通用 URL 提取器：提取行中第一个 http/https URL"""
    # 排除 localhost / 127.0.0.1
    match = re.search(r'(https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[a-zA-Z0-9.\-]+(?:\.\w+)+(?::\d+)?(?:/\S*)?)', line)
    if match:
        return match.group(1)
    return None
