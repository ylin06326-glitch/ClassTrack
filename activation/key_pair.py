# -*- coding: utf-8 -*-
"""
预置密钥对
==========
公钥内置于软件中用于校验激活文件。
私钥仅用于独立商家工具生成激活文件。

重要: 此文件由 crypto.py 在首次运行时自动生成。
      开发构建时预生成一对密钥，私钥需妥善保管在商家工具中。

公钥 PEM → 编译进软件（此文件内）
私钥 PEM → 仅存在于 merchant_tool.py 引用的独立文件中
"""

# ============================================================
# ClassTrack YRL 产品预置公钥（2048-bit RSA）
# ============================================================
# 此公钥在构建时由 generate_key_pair() 生成并固定。
# 对应的私钥存放于 activation/private_key.pem（不随软件分发）。

_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA6RXSlTuAb5XHx2xSuBCG
8T5TGkiy4YVTcst/3LG8Bxov6KW0omnxwAojYf3INxuOSCwfpBU7qZ5hWPT0vzdA
PwnsXBAxum6FpGY5nK99ut2ndpef7+mkFWczc4oi+ziCMQPfz0r3Pvc/dTeqzrPu
ocZOGGysQT+LP1iB2KRhEY4EuYrlh4CnsNXweDWkEsZ8tgNWfD+hzFC8Xyi0wECx
qN/7K+uarWU5P3rMLOu/PqXsgrsrPi4U41z1zvdsbfY1pQ07dF5AoFeskN9N4Wst
+BOXr0TqTIOkdlynFr97frXJ/Ao//YLeN7pZIReBmFurIpakhWDCZg/2Oy7Qq4Ax
cQIDAQAB
-----END PUBLIC KEY-----"""

# 注意：上方的公钥是示例占位，实际使用时应替换为真实生成的密钥对。
# 可通过运行 `python -m activation.crypto` 中调用 generate_key_pair() 生成，
# 然后将公钥 PEM 粘贴到此处，私钥 PEM 保存到 merchant_tool.py 或单独文件中。

# ============================================================
# 公钥加载（懒加载 + 缓存）
# ============================================================
_PUBLIC_KEY_CACHE = None


def get_public_key():
    """获取内置公钥对象（懒加载，首次调用后缓存）"""
    global _PUBLIC_KEY_CACHE
    if _PUBLIC_KEY_CACHE is None:
        from activation.crypto import load_public_key_from_pem
        _PUBLIC_KEY_CACHE = load_public_key_from_pem(_PUBLIC_KEY_PEM)
    return _PUBLIC_KEY_CACHE


def get_public_key_pem() -> str:
    """获取内置公钥 PEM 字符串"""
    return _PUBLIC_KEY_PEM
