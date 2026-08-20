# -*- coding: utf-8 -*-
"""
激活校验 API (v1.5 — 纯离线,不侵入原有业务代码)
================================================
硬件指纹采集、激活文件校验与保存、激活状态查询。

激活模块在 app/activation/ 下;这里用函数内 import,
保持 main.py 的降级模式语义(模块导入失败时返回
"激活模块未加载"而不是让整个应用启动失败)。
"""

from fastapi import APIRouter, Depends, Request

from app.deps import get_body
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["activation"])


@router.get("/activation/fingerprint")
def api_activation_fingerprint():
    """获取本机硬件指纹和机器码"""

    try:
        from app.activation.hardware_id import get_full_hardware_fingerprint
        from app.activation.license_manager import export_fingerprint
    except ImportError:
        return JSONResponse({"code": 1, "msg": "激活模块未加载"}, status_code=500)
    try:
        info = get_full_hardware_fingerprint()
        fp_export = export_fingerprint()
        return {
            "code": 0,
            "data": {
                "machine_code": info["machine_code"],
                "fingerprint_export": fp_export,
                "cpu": info["cpu"],
                "disk": info["disk"],
            }
        }
    except Exception as e:
        return JSONResponse({"code": 1, "msg": f"采集失败: {e}"}, status_code=500)


@router.post("/activation/verify")
def api_activation_verify(data: dict = Depends(get_body)):
    """校验并保存激活文件"""

    try:
        from app.activation.license_manager import (
            save_activation_file,
            verify_activation,
        )
    except ImportError:
        return JSONResponse({"code": 1, "msg": "激活模块未加载"}, status_code=500)
    file_content = data.get("file_content", "")
    if not file_content:
        return JSONResponse({"code": 1, "msg": "未提供激活文件内容"}, status_code=400)

    # 先保存文件,再校验
    if not save_activation_file(file_content):
        return JSONResponse({"code": 1, "msg": "激活文件保存失败"}, status_code=500)

    # 执行完整校验
    result = verify_activation()
    return {
        "code": 0 if result.activated else 1,
        "msg": result.reason,
        "data": result.to_dict(),
    }


@router.get("/activation/status")
def api_activation_status():
    """查询当前激活状态(供前端轮询使用)"""

    try:
        from app.activation.license_manager import verify_activation
    except ImportError:
        # 激活模块不可用时视为已激活(开发/降级模式)
        return {"code": 0, "data": {"activated": True}}
    result = verify_activation()
    return {
        "code": 0,
        "data": result.to_dict(),
    }
