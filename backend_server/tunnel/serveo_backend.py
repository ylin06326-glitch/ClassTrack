#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveo.net SSH 隧道后端 — 免费免注册

使用 Windows 10+ 自带的 SSH 客户端，无需安装任何额外软件。
原理: ssh -R 80:localhost:<port> serveo.net
公网用户可通过 https://xxxx.serveo.net 访问本地服务。

优点:
  - 完全免费，无需注册
  - Windows 10+ 自带 SSH，零依赖
  - HTTPS 自动加密
"""

from .subprocess_backend import SubprocessTunnelBackend, extract_serveo_url


class ServeoTunnelBackend(SubprocessTunnelBackend):
    """通过 serveo.net SSH 隧道实现内网穿透"""

    _startup_timeout = 20.0  # SSH 连接可能稍慢

    def __init__(self, custom_domain: str = ""):
        """
        Args:
            custom_domain: 可选的自定义子域名（如 "myapp" → myapp.serveo.net）
                           留空则随机分配
        """
        super().__init__()
        self._custom_domain = custom_domain.strip()

    def _build_command(self, port: int) -> list[str]:
        """
        构建 SSH 隧道命令。

        serveo.net 默认不要求 StrictHostKeyChecking，
        但为避免交互式提示，我们关闭主机密钥检查。
        ServerAliveInterval 防止连接空闲断开。
        """
        if self._custom_domain:
            remote = f"80:localhost:{port}"
            # 自定义子域名通过 SSL 证书实现，实际还是 80 端口
        else:
            remote = f"80:localhost:{port}"

        return [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "ServerAliveInterval=60",
            "-o", "ConnectTimeout=15",
            "-R", remote,
            "serveo.net",
        ]

    def _extract_url(self, line: str) -> str | None:
        return extract_serveo_url(line)

    @property
    def backend_name(self) -> str:
        return "serveo.net (SSH 免费免注册)"


class LocalhostRunBackend(SubprocessTunnelBackend):
    """通过 localhost.run SSH 隧道实现内网穿透 — 备选方案"""

    _startup_timeout = 20.0

    def _build_command(self, port: int) -> list[str]:
        return [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=NUL",
            "-o", "ServerAliveInterval=60",
            "-o", "ConnectTimeout=15",
            "-R", f"80:localhost:{port}",
            "nokey@localhost.run",
        ]

    def _extract_url(self, line: str) -> str | None:
        from .subprocess_backend import extract_localhost_run_url
        return extract_localhost_run_url(line)

    @property
    def backend_name(self) -> str:
        return "localhost.run (SSH 免费免注册)"
