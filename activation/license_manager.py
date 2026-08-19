# -*- coding: utf-8 -*-
"""
激活文件管理器
==============
负责:
1. 激活文件的本地存储与读取
2. 激活校验（硬件码匹配 + RSA 验签）
3. 激活状态查询

存储位置: DATA_DIR / "activation.dat"
文件格式: Base64(JSON_payload) + "." + Base64(RSA签名)
"""

import os
import hashlib
from pathlib import Path


def get_activation_file_path() -> Path:
    """
    获取激活文件的存储路径。
    打包版跟随 app_paths 的数据目录（%APPDATA%\\ClassTrack），
    与数据库/证书等放在一起；开发版为项目根目录 data\\。
    """
    try:
        from app_paths import get_data_dir
        return get_data_dir() / "activation.dat"
    except ImportError:
        # 兜底（app_paths 不可用时维持旧逻辑）
        import sys
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).resolve().parent
            return exe_dir / "data" / "activation.dat"
        return Path(__file__).resolve().parent.parent / "data" / "activation.dat"


def save_activation_file(file_content: str) -> bool:
    """
    保存激活文件到本地。

    Args:
        file_content: 激活文件的完整文本内容

    Returns:
        True 如果保存成功
    """
    try:
        file_path = get_activation_file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_content, encoding="utf-8")
        reset_activation_cache()  # 激活文件已变化，缓存失效
        return True
    except Exception:
        return False


def load_activation_file() -> str | None:
    """
    读取本地激活文件。

    Returns:
        文件内容字符串，或 None 如果文件不存在/读取失败
    """
    file_path = get_activation_file_path()
    if not file_path.exists():
        return None
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return None


def delete_activation_file() -> bool:
    """删除本地激活文件（用于重置激活状态）"""
    file_path = get_activation_file_path()
    if file_path.exists():
        try:
            file_path.unlink()
            reset_activation_cache()
            return True
        except Exception:
            return False
    return True


# ============================================================
# 激活校验核心逻辑
# ============================================================
class ActivationStatus:
    """激活校验结果"""

    def __init__(self, activated: bool, reason: str = "", machine_code: str = ""):
        self.activated = activated
        self.reason = reason
        self.machine_code = machine_code

    def to_dict(self) -> dict:
        return {
            "activated": self.activated,
            "reason": self.reason,
            "machine_code": self.machine_code,
        }

    def __bool__(self):
        return self.activated


# ---- 校验结果缓存：避免每个请求都重新采集硬件码 + RSA 验签 ----
_VERIFY_CACHE = {"ts": 0.0, "result": None}
VERIFY_TTL_SECONDS = 300  # 5 分钟内复用校验结果（指纹进程内本就稳定）


def reset_activation_cache():
    """激活文件增删后调用，强制下次校验重新计算"""
    _VERIFY_CACHE["ts"] = 0.0
    _VERIFY_CACHE["result"] = None


def verify_activation() -> ActivationStatus:
    """
    执行完整的激活校验流程（带 TTL 缓存）：
    1. 检查本地激活文件是否存在
    2. 解码激活文件
    3. RSA 公钥验签
    4. 硬件码匹配校验

    Returns:
        ActivationStatus 包含激活状态和详细信息
    """
    import time
    now = time.monotonic()
    if _VERIFY_CACHE["result"] is not None and now - _VERIFY_CACHE["ts"] < VERIFY_TTL_SECONDS:
        return _VERIFY_CACHE["result"]
    result = _verify_activation_uncached()
    _VERIFY_CACHE["ts"] = now
    _VERIFY_CACHE["result"] = result
    return result


def _verify_activation_uncached() -> ActivationStatus:
    """实际执行激活校验（不做缓存，由 verify_activation 包装）"""
    from activation.hardware_id import collect_hardware_id, hardware_id_to_machine_code
    from activation.crypto import decode_activation_file, payload_to_bytes
    from activation.key_pair import get_public_key

    # 1. 获取本机硬件码
    current_hw_id = collect_hardware_id()
    current_machine_code = hardware_id_to_machine_code(current_hw_id)
    current_hw_hash = hashlib.sha256(current_hw_id.encode("utf-8")).hexdigest()

    # 2. 读取激活文件
    file_content = load_activation_file()
    if file_content is None:
        return ActivationStatus(
            False,
            reason="未找到激活文件",
            machine_code=current_machine_code,
        )

    # 3. 解码激活文件（新格式返回 (None, error_msg) 而不是 (None, None)）
    result_tuple = decode_activation_file(file_content)
    if result_tuple is None or result_tuple[0] is None:
        error_msg = result_tuple[1] if result_tuple else "激活文件格式错误"
        return ActivationStatus(
            False,
            reason=f"密钥无效 — {error_msg}",
            machine_code=current_machine_code,
        )
    payload, signature = result_tuple

    # 4. RSA 公钥验签
    public_key = get_public_key()
    data_bytes = payload_to_bytes(payload)
    from activation.crypto import verify_signature
    if not verify_signature(public_key, data_bytes, signature):
        return ActivationStatus(
            False,
            reason="密钥签名校验失败 — 密钥可能被篡改或来自非法来源",
            machine_code=current_machine_code,
        )

    # 5. 硬件码匹配校验（兼容新格式 "h" 和旧格式 "hw_hash"）
    stored_h = payload.get("h", "") or payload.get("hw_hash", "")
    # 新格式 "h" 是前16位，旧格式 "hw_hash" 是全64位
    if len(stored_h) <= 16:
        # 新格式：只比较前16位
        current_h_short = current_hw_hash[:16]
        if stored_h != current_h_short:
            return ActivationStatus(
                False,
                reason=f"硬件码不匹配 — 此密钥绑定其他设备（本机: {current_h_short[:8]}…, 密钥: {stored_h[:8]}…）",
                machine_code=current_machine_code,
            )
    else:
        # 旧格式：全hash比较
        if stored_h != current_hw_hash:
            return ActivationStatus(
                False,
                reason=f"硬件码不匹配 — 此密钥绑定其他设备",
                machine_code=current_machine_code,
            )

    # 校验通过！
    return ActivationStatus(
        True,
        reason="激活校验通过",
        machine_code=current_machine_code,
    )


# ============================================================
# 商家端: 生成激活文件
# ============================================================
def export_fingerprint() -> str:
    """导出本机硬件指纹（base64 编码），用户发送给商家"""
    import base64
    from activation.hardware_id import collect_hardware_id
    raw = collect_hardware_id()
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_fingerprint(export_str: str) -> str | None:
    """解码用户发送的硬件指纹导出字符串"""
    import base64
    try:
        return base64.urlsafe_b64decode(export_str.encode("ascii")).decode("utf-8")
    except Exception:
        return None


def generate_activation(private_key_pem: str, hardware_id_raw: str) -> str | None:
    """
    使用私钥生成激活文件内容（商家端使用）。

    Args:
        private_key_pem: 商家私钥 PEM 字符串
        hardware_id_raw: 用户的原始硬件ID（从"复制机器指纹"获得，商家解码后传入）

    Returns:
        激活文件内容字符串，或 None 如果失败
    """
    from activation.crypto import (
        load_private_key_from_pem,
        create_activation_payload,
        sign_data,
        encode_activation_file,
        payload_to_bytes,
    )

    try:
        private_key = load_private_key_from_pem(private_key_pem)
        payload = create_activation_payload(hardware_id_raw)
        data_bytes = payload_to_bytes(payload)
        signature = sign_data(private_key, data_bytes)
        file_content = encode_activation_file(payload, signature)
        return file_content
    except Exception as e:
        print(f"生成激活文件失败: {e}")
        return None
