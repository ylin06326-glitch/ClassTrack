# -*- coding: utf-8 -*-
"""
ClassTrack FastAPI 应用入口
===========================
- 激活守卫中间件(未激活拦截全部业务 API)
- 路由挂载
- 前端构建产物托管(前后端分离,生产模式同端口)
- 单实例锁 + TLS 证书 + 浏览器自动打开(桌面分发模式)

启动方式:
- 开发: python run.py [--reload] [--port 5088] [--http]
- 打包: PyInstaller(见 ClassTrack.spec)
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    APP_VERSION,
    FRONTEND_DIST,
    ensure_data_dir,
    get_data_dir,
)
from app.database import init_db

# ============================================================
# 激活模块加载(降级模式:导入失败则禁用激活校验)
# ============================================================
_ACTIVATION_AVAILABLE = True
if os.environ.get("CLASSTRACK_NO_ACTIVATION") == "1":
    _ACTIVATION_AVAILABLE = False
else:
    try:
        from app.activation.license_manager import verify_activation  # noqa: F401
    except Exception:
        _ACTIVATION_AVAILABLE = False

# 激活守卫白名单(去尾斜杠精确匹配)
ACTIVATION_WHITELIST = {
    "/activation",
    "/api/activation/fingerprint",
    "/api/activation/verify",
    "/api/activation/status",
    "/api/shutdown",
    "/api/cert/download",
    "/api/qrcode",
    "/mobile",
    "/print",
}


class ActivationGuardMiddleware(BaseHTTPMiddleware):
    """激活守卫:未激活时拦截全部业务 API(403)与页面(由前端路由守卫接管跳转)"""

    async def dispatch(self, request: Request, call_next):
        if not _ACTIVATION_AVAILABLE:
            return await call_next(request)  # 降级模式:全部放行

        path = request.url.path
        # 静态资源与杂项直接放行
        if path.startswith("/static/") or path.startswith("/assets/") \
                or path in ("/favicon.ico", "/robots.txt"):
            return await call_next(request)

        # 白名单(去尾斜杠精确匹配)
        normalized = path[:-1] if path.endswith("/") else path
        if normalized in ACTIVATION_WHITELIST or path == "/":
            return await call_next(request)

        # 校验激活状态
        try:
            from app.activation.license_manager import verify_activation as _verify
            status = _verify()
            activated = status.activated
            machine_code = status.machine_code
        except Exception:
            return await call_next(request)  # 守卫异常:放行

        if activated:
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse(
                {"code": 403, "msg": "软件未激活，请先完成激活登录",
                 "data": {"activated": False, "machine_code": machine_code}},
                status_code=403,
            )
        # 非 API 页面:返回 SPA 入口,由前端路由守卫跳转激活页
        return await call_next(request)


# ============================================================
# FastAPI 应用
# ============================================================
app = FastAPI(title="ClassTrack", version=APP_VERSION, docs_url=None, redoc_url=None)
app.add_middleware(ActivationGuardMiddleware)


@app.middleware("http")
async def _cache_json_body(request: Request, call_next):
    """预先缓存 JSON 请求体,使同步路由可以直接读取(避免 await request.json())"""
    ctype = request.headers.get("content-type", "")
    if request.method in ("POST", "PUT", "PATCH") and "application/json" in ctype:
        try:
            request.state.body = await request.body()
        except Exception:
            request.state.body = b""
    else:
        request.state.body = b""
    return await call_next(request)


@app.on_event("startup")
def _startup() -> None:
    ensure_data_dir()
    init_db()


# ---- 路由挂载 ----
from app.routers import (  # noqa: E402
    activation_api,
    ai,
    analytics,
    classes,
    config_api,
    exam_scores,
    exports,
    groups,
    homework,
    scan,
    students,
)

for _router in (
    classes.router,
    students.router,
    groups.router,
    homework.router,
    exam_scores.router,
    analytics.router,
    exports.router,
    scan.router,
    config_api.router,
    activation_api.router,
    ai.router,
):
    app.include_router(_router)


# ---- 前端构建产物托管(生产模式) ----
@app.get("/api")
def _api_index():
    return {"code": 0, "msg": "ClassTrack API", "version": APP_VERSION}


if FRONTEND_DIST.exists():
    _assets_dir = FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")
    # 老版静态资源(/static/css, /static/js, /static/images)
    _static_dir = FRONTEND_DIST / "static"
    if _static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/print")
def page_print():
    """二维码批量打印页面"""
    print_file = FRONTEND_DIST / "print.html"
    if print_file.exists():
        return FileResponse(str(print_file))
    return Response("打印页面未找到", media_type="text/plain", status_code=404)


@app.get("/mobile")
def page_mobile():
    """手机扫码端页面"""
    mobile_file = FRONTEND_DIST / "mobile.html"
    if mobile_file.exists():
        return FileResponse(str(mobile_file))
    return Response("手机端页面未找到", media_type="text/plain", status_code=404)


@app.get("/{full_path:path}")
def _spa_fallback(full_path: str):
    """SPA fallback:非 /api 路径返回前端入口(存在时),否则提示未构建"""
    if full_path.startswith("api"):
        return JSONResponse({"code": 1, "msg": "接口不存在"}, status_code=404)
    if FRONTEND_DIST.exists():
        target = (FRONTEND_DIST / full_path).resolve()
        # 只允许访问 dist 内的真实文件
        if full_path and target.is_file() and FRONTEND_DIST.resolve() in target.parents:
            return FileResponse(str(target))
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return Response(
        "ClassTrack 前端未构建。请先运行: cd frontend && npm run build",
        media_type="text/plain",
        status_code=503,
    )


# ============================================================
# 桌面启动逻辑(单实例锁 + TLS + 浏览器打开)
# ============================================================
def _ensure_single_instance() -> bool:
    """Windows 命名互斥锁:防止用户重复双击启动多个实例抢端口/写库。
    返回 True 表示本进程是唯一实例;False 表示已有实例在运行。"""
    if not getattr(sys, "frozen", False):
        return True  # 开发模式允许多实例,方便调试
    if os.environ.get("CLASSTRACK_NO_LOCK") == "1":
        return True  # 免锁版(nolock spec)允许多开
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW(None, False, "ClassTrack_SingleInstance_Mutex")
        # use_last_error=True 时 get_last_error 才是可靠的(ctypes 调用间会覆盖)
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def run_server(port: int = 5088, use_ssl: bool = True) -> None:
    """启动 uvicorn 服务器(桌面模式:含单实例锁/证书/浏览器)"""
    import uvicorn

    print("=" * 60)
    print(f"  🎒 ClassTrack v{APP_VERSION} - 班级作业分组管理系统")
    print("  面向中小学教师的班级作业管理工具")
    print("=" * 60)

    # ---- 单实例保护 ----
    if not _ensure_single_instance():
        webbrowser.open(f"https://localhost:{port}")
        print("  ⚠️ ClassTrack 已在运行,本次启动已退出(请查看已打开的浏览器窗口)")
        if getattr(sys, "frozen", False):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0, "ClassTrack 已经在运行中。\n\n请查看已打开的浏览器窗口继续使用。",
                    "ClassTrack", 0x40)
            except Exception:
                pass
        return

    # ---- 数据目录 + 数据库 ----
    data_dir = get_data_dir()
    try:
        ensure_data_dir()
        print(f"  📁 数据目录: {data_dir}")
    except Exception as e:
        print(f"  ❌ 无法创建数据目录: {data_dir}\n{e}\n\n"
              f"  请将 ClassTrack.exe 移动到可写位置(如桌面)后重试。")
        return
    try:
        init_db()
        print(f"  ✅ 数据库已就绪: {data_dir / 'classtrack.db'}")
    except Exception as e:
        print(f"  ❌ 数据库初始化失败: {e}")
        sys.exit(1)

    # ---- 激活状态检测 ----
    if _ACTIVATION_AVAILABLE:
        try:
            from app.activation.license_manager import verify_activation as _verify
            result = _verify()
            if result.activated:
                print("  ✅ 激活校验通过")
                print(f"  💻 机器码: {result.machine_code}")
            else:
                print("  🔒 未激活 — 需要导入激活文件解锁全部功能")
                print(f"  💻 机器码: {result.machine_code}")
                print(f"  ℹ️  原因: {result.reason}")
        except Exception as e:
            print(f"  ⚠️ 激活校验异常: {e}")
    else:
        print("  ⚠️ 激活模块未加载(降级模式)")

    # ---- TLS 证书(手机扫码需要 HTTPS) ----
    ssl_kwargs = {}
    if use_ssl:
        from app.services.tls_service import prepare_tls
        cert_path, key_path = prepare_tls()
        if cert_path and key_path:
            ssl_kwargs = {"ssl_certfile": cert_path, "ssl_keyfile": key_path}

    print(f"  📱 手机扫码地址: https://<本机IP>:{port}/mobile")
    print(f"  🌐 本地地址: https://localhost:{port}")
    print("  📋 按 Ctrl+C 停止服务")
    print("=" * 60)

    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"https://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", **ssl_kwargs)


if __name__ == "__main__":
    run_server()
