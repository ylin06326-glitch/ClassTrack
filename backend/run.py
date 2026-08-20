# -*- coding: utf-8 -*-
"""
开发模式启动入口
================
用法:
    python run.py              # 默认 HTTPS 5088(与桌面版一致)
    python run.py --http       # 纯 HTTP(本地调试,无摄像头要求时)
    python run.py --port 8000  # 自定义端口
    python run.py --reload     # 热重载
"""

import asyncio
import sys

# Windows 上使用 SelectorEventLoop 避免 ProactorEventLoop 的
# ConnectionResetError (WinError 10054) 问题
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

import argparse
from pathlib import Path

# 确保 backend/ 目录在 sys.path 上,使 `app` 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app, run_server  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="ClassTrack 开发服务器")
    parser.add_argument("--http", action="store_true", help="禁用 HTTPS(纯 HTTP 调试)")
    parser.add_argument("--port", type=int, default=5088, help="监听端口(默认 5088)")
    parser.add_argument("--reload", action="store_true", help="代码热重载")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    if args.reload or args.no_browser:
        # 热重载/无浏览器模式:直接 uvicorn,绕过桌面启动逻辑
        import uvicorn
        ssl_kwargs = {}
        if not args.http:
            from app.services.tls_service import prepare_tls
            cert_path, key_path = prepare_tls()
            if cert_path and key_path:
                ssl_kwargs = {"ssl_certfile": cert_path, "ssl_keyfile": key_path}
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=args.port,
            reload=args.reload,
            **ssl_kwargs,
        )
        return

    run_server(port=args.port, use_ssl=not args.http)


if __name__ == "__main__":
    main()
