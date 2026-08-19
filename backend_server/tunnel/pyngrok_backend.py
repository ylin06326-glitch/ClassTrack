#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pyngrok 隧道后端 — 使用 ngrok 免费隧道实现内网穿透

前置条件:
  1. pip install pyngrok
  2. 在 https://ngrok.com 注册免费账号
  3. 获取 auth token 填入管理后台设置页
"""

import time
from .base import BaseTunnelBackend, TunnelError


class PyngrokTunnelBackend(BaseTunnelBackend):
    """使用 pyngrok 库建立 HTTP 隧道"""

    def __init__(self, auth_token: str = ""):
        self._auth_token = auth_token.strip()
        self._public_url: str | None = None
        self._ngrok_tunnel = None

    # ----------------------------------------------------------------
    #  BaseTunnelBackend 接口
    # ----------------------------------------------------------------
    def connect(self, port: int) -> str:
        if self._auth_token:
            self._configure_auth()

        try:
            from pyngrok import ngrok
            # 如果已有活跃隧道则先断开
            if self._ngrok_tunnel is not None:
                try:
                    ngrok.disconnect(self._ngrok_tunnel.public_url)
                except Exception:
                    pass

            self._ngrok_tunnel = ngrok.connect(port, "http")
            self._public_url = str(self._ngrok_tunnel.public_url)
            return self._public_url
        except ImportError:
            raise TunnelError(
                "pyngrok 库未安装，请运行: pip install pyngrok\n"
                "然后注册 ngrok 免费账号: https://ngrok.com"
            )
        except Exception as e:
            raise TunnelError(f"ngrok 隧道建立失败: {e}")

    def disconnect(self):
        try:
            from pyngrok import ngrok
            if self._ngrok_tunnel is not None:
                ngrok.disconnect(self._ngrok_tunnel.public_url)
        except Exception:
            pass
        finally:
            self._ngrok_tunnel = None
            self._public_url = None

    def get_public_url(self) -> str | None:
        return self._public_url

    def is_connected(self) -> bool:
        if self._public_url is None:
            return False
        try:
            from pyngrok import ngrok
            tunnels = ngrok.get_tunnels()
            return any(
                str(t.public_url) == self._public_url
                for t in tunnels
            )
        except Exception:
            return self._ngrok_tunnel is not None

    @property
    def backend_name(self) -> str:
        return "pyngrok (ngrok 免费隧道)"

    # ----------------------------------------------------------------
    #  内部
    # ----------------------------------------------------------------
    def _configure_auth(self):
        """配置 ngrok auth token"""
        try:
            from pyngrok import conf
            conf.get_default().auth_token = self._auth_token
        except ImportError:
            raise TunnelError("pyngrok 库未安装")
        except Exception as e:
            raise TunnelError(f"ngrok 认证配置失败: {e}")


def connect_with_retry(backend: PyngrokTunnelBackend, port: int,
                       max_retries: int = 5) -> str:
    """带指数退避重试的隧道连接

    延迟序列: 1s → 2s → 4s → 8s → 16s
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return backend.connect(port)
        except TunnelError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # 1, 2, 4, 8, 16
                time.sleep(delay)
    raise last_error or TunnelError("连接失败（已达最大重试次数）")
