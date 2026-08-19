# -*- coding: utf-8 -*-
"""
RSA 非对称加密工具
==================
基于 cryptography 库实现:
- RSA 2048 密钥对生成
- 私钥签名 / 公钥验签
- 密钥 PEM 格式导入/导出

注意: 本模块仅提供底层加解密原语，不管理密钥存储。
      公钥嵌入软件，私钥仅存在于商家工具。
"""

import base64
import hashlib
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend


# ============================================================
# 密钥对生成
# ============================================================
def generate_key_pair(key_size: int = 2048) -> tuple:
    """
    生成 RSA 密钥对。

    Args:
        key_size: 密钥长度，默认 2048

    Returns:
        (private_key, public_key) 两个 cryptography 密钥对象
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )
    public_key = private_key.public_key()
    return private_key, public_key


# ============================================================
# 密钥序列化
# ============================================================
def private_key_to_pem(private_key) -> str:
    """将私钥导出为 PEM 格式字符串"""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def public_key_to_pem(public_key) -> str:
    """将公钥导出为 PEM 格式字符串"""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def load_private_key_from_pem(pem_str: str):
    """从 PEM 字符串加载私钥"""
    return serialization.load_pem_private_key(
        pem_str.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )


def load_public_key_from_pem(pem_str: str):
    """从 PEM 字符串加载公钥"""
    return serialization.load_pem_public_key(
        pem_str.encode("utf-8"),
        backend=default_backend(),
    )


# ============================================================
# 签名 / 验签
# ============================================================
def sign_data(private_key, data: bytes) -> bytes:
    """
    使用私钥对数据进行签名（SHA-256 + PKCS1v15）。

    Args:
        private_key: RSA 私钥对象
        data: 待签名数据

    Returns:
        签名字节
    """
    return private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def verify_signature(public_key, data: bytes, signature: bytes) -> bool:
    """
    使用公钥验证签名。

    Args:
        public_key: RSA 公钥对象
        data: 原始数据
        signature: 待验证的签名

    Returns:
        True 如果签名有效
    """
    try:
        public_key.verify(
            signature,
            data,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


# ============================================================
# 激活密钥格式 (v2 紧凑版)
# ============================================================
# 密钥格式: <compact_payload_b64>.<signature_b64>
# 单行，无头尾包装，方便复制粘贴
#
# 紧凑载荷 (JSON, 按字母排序):
#   {"h":"<hw_hash_前16位>","t":<unix_timestamp>}
#   h = SHA256(原始硬件ID) 前16个十六进制字符，足够唯一
#   t = Unix 时间戳（整数）
# 载荷约 50 字符 → base64 约 68 字符 → 密钥总长约 420 字符

def create_activation_payload(hardware_id: str, product: str = "ClassTrack_YRL") -> dict:
    """
    创建激活载荷（紧凑版）。

    Args:
        hardware_id: 原始硬件ID字符串

    Returns:
        紧凑载荷字典 {"h": "<16 hex>", "t": <unix_ts>}
    """
    import time as _time
    hw_hash_full = hashlib.sha256(hardware_id.encode("utf-8")).hexdigest()
    payload = {
        "h": hw_hash_full[:16],   # SHA256 前16位，足够防碰撞
        "t": int(_time.time()),   # Unix 时间戳
    }
    return payload


def encode_activation_file(payload: dict, signature: bytes) -> str:
    """
    将载荷和签名编码为紧凑单行激活密钥。

    格式: <Base64(JSON_payload)>.<Base64(signature)>
    无头尾包装，直接单行字符串。
    """
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii")
    sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii")
    return f"{payload_b64}.{sig_b64}"


def decode_activation_file(file_content: str) -> tuple:
    """
    解码激活密钥内容（兼容新旧格式）。

    新格式: <payload_b64>.<sig_b64>  （单行紧凑）
    旧格式: ===== CLASSTRACK ... ===== （多行包装，向后兼容）

    Args:
        file_content: 用户粘贴的密钥文本

    Returns:
        (payload_dict, signature_bytes) 或 (None, error_msg_str)
    """
    # ---- 预处理：清洗常见复制粘贴问题 ----
    text = file_content.strip()
    # 去除首尾可能误粘的引号
    text = text.strip('"\'')
    # 去除不可见字符（仅保留可打印ASCII + 换行）
    text = ''.join(c for c in text if c.isprintable() or c in '\n\r')

    if not text:
        return None, "密钥为空"

    # ---- 尝试找到核心数据行 ----
    data_line = ""
    for line in text.splitlines():
        line = line.strip()
        # 跳过旧格式标记行和非数据行
        if line.startswith("=") or not line:
            continue
        if "." in line and len(line) > 40:
            data_line = line
            break

    if not data_line:
        # 如果没有找到含 '.' 的行，尝试把整个文本当作单行密钥
        if "." in text and len(text) > 40:
            data_line = text
        else:
            return None, "密钥格式无效（缺少有效数据）"

    # ---- 解析 payload_b64 . sig_b64 ----
    try:
        payload_b64, sig_b64 = data_line.split(".", 1)
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        payload = json.loads(payload_json)
        signature = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
        return payload, signature
    except (ValueError, json.JSONDecodeError):
        return None, "密钥格式无效（Base64/JSON解析失败）"
    except Exception:
        return None, "密钥解析异常"


# ============================================================
# 辅助: 验证载荷完整性
# ============================================================
def payload_to_bytes(payload: dict) -> bytes:
    """将载荷序列化为用于签名的规范字节（稳定排序）"""
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return payload_json.encode("utf-8")
