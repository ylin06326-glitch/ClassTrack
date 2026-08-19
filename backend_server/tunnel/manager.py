#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TunnelManager — 隧道管理单例

职责:
  - 根据 server_config 配置初始化对应后端
  - 启动/停止/重启隧道
  - 后台健康检查（每60秒）
  - 状态变更写入 admin_log
  - 公网 URL 写入 server_config
"""

import threading
import time
import sqlite3
from pathlib import Path

from .base import BaseTunnelBackend, TunnelError
from .noop_backend import NoopTunnelBackend
from .pyngrok_backend import PyngrokTunnelBackend, connect_with_retry
from .serveo_backend import ServeoTunnelBackend, LocalhostRunBackend


class TunnelManager:
    """隧道管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._db_path: Path | None = None
        self._backend: BaseTunnelBackend | None = None
        self._port: int = 5099
        self._enabled: bool = False
        self._health_thread: threading.Thread | None = None
        self._running: bool = False
        self._state_lock = threading.Lock()

    # ----------------------------------------------------------------
    #  公开 API
    # ----------------------------------------------------------------
    def set_db_path(self, db_path: Path):
        """设置数据库路径（必须在 start() 之前调用）"""
        self._db_path = db_path

    def load_config(self):
        """从 server_config 表加载隧道配置并初始化后端"""
        config = self._read_config()
        self._enabled = config.get("tunnel_enabled", "1") == "1"
        backend_name = config.get("tunnel_backend", "serveo")
        auth_token = config.get("tunnel_ngrok_auth_token", "")

        if not self._enabled:
            self._backend = NoopTunnelBackend()
        elif backend_name == "pyngrok":
            self._backend = PyngrokTunnelBackend(auth_token=auth_token)
        elif backend_name == "serveo":
            self._backend = ServeoTunnelBackend()
        elif backend_name == "localhost_run":
            self._backend = LocalhostRunBackend()
        else:
            self._backend = NoopTunnelBackend()

    def is_enabled(self) -> bool:
        return self._enabled

    def start(self, port: int = 5099) -> str | None:
        """启动隧道。成功返回公网 URL，失败返回 None"""
        if self._db_path is None:
            raise RuntimeError("TunnelManager: 请先调用 set_db_path()")

        with self._state_lock:
            self._port = port
            self.load_config()

            if not self._enabled or self._backend is None:
                return None

            try:
                if isinstance(self._backend, PyngrokTunnelBackend):
                    url = connect_with_retry(self._backend, port)
                else:
                    url = self._backend.connect(port)
                self._running = True
                self._save_public_url(url)
                self._write_log("tunnel_connected", f"隧道已连接: {url}")
                self._start_health_check()
                return url
            except TunnelError as e:
                self._write_log("tunnel_error", f"隧道启动失败: {e}")
                return None

    def stop(self):
        """停止隧道"""
        with self._state_lock:
            self._running = False
            if self._backend is not None:
                try:
                    self._backend.disconnect()
                except Exception:
                    pass
            self._save_public_url("")
            self._write_log("tunnel_disconnected", "隧道已断开")

    def restart(self, port: int = 5099) -> str | None:
        """重启隧道"""
        self.stop()
        time.sleep(1)
        return self.start(port)

    def get_public_url(self) -> str | None:
        if self._backend is None:
            return None
        return self._backend.get_public_url()

    def is_connected(self) -> bool:
        if self._backend is None:
            return False
        return self._backend.is_connected()

    def get_backend_name(self) -> str:
        if self._backend is None:
            return "未初始化"
        return self._backend.backend_name

    def get_status(self) -> dict:
        """返回完整的隧道状态信息，供 API 使用"""
        return {
            "enabled": self._enabled,
            "backend": self.get_backend_name(),
            "connected": self.is_connected(),
            "public_url": self.get_public_url(),
        }

    # ----------------------------------------------------------------
    #  内部
    # ----------------------------------------------------------------
    def _read_config(self) -> dict:
        """从 server_config 表读取隧道相关配置"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT key, value FROM server_config WHERE key LIKE 'tunnel_%'"
            ).fetchall()
            conn.close()
            return {r["key"]: r["value"] for r in rows}
        except Exception:
            return {}

    def _save_public_url(self, url: str):
        """将公网 URL 写入 server_config"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT OR REPLACE INTO server_config (key, value) VALUES (?, ?)",
                ("tunnel_public_url", url)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _write_log(self, action: str, detail: str):
        """写入 admin_log"""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT INTO admin_log (action, detail) VALUES (?, ?)",
                (action, detail)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _start_health_check(self):
        """启动后台健康检查线程"""
        if self._health_thread is not None and self._health_thread.is_alive():
            return
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True
        )
        self._health_thread.start()

    def _health_loop(self):
        """后台健康检查（每60秒）"""
        while self._running:
            time.sleep(60)
            if not self._running:
                break
            try:
                if self._backend is not None and not self._backend.is_connected():
                    # 尝试重连
                    try:
                        if isinstance(self._backend, PyngrokTunnelBackend):
                            url = connect_with_retry(self._backend, self._port, max_retries=3)
                        else:
                            url = self._backend.connect(self._port)
                        self._save_public_url(url)
                        self._write_log("tunnel_reconnected", f"隧道已重连: {url}")
                    except TunnelError:
                        self._write_log("tunnel_health_fail", "隧道重连失败，将在下次检查时重试")
            except Exception:
                pass
