# -*- coding: utf-8 -*-
"""
TLS 证书服务
============
手机扫码需要 HTTPS(浏览器摄像头 API 仅安全上下文可用),桌面端无域名,
因此启动时自建 CA 并签发含 localhost + 127.0.0.1 + 本机IP SAN 的服务器证书:
- CA 根证书: DATA_DIR/ca-cert.pem + ca-key.pem(3650 天)
- 服务器证书: DATA_DIR/cert.pem + key.pem(CA 签发,3650 天)
- Windows 上通过 certutil -addstore -user Root 自动信任 CA
- CA 证书同时提供 /api/cert/download 供手机安装
"""

import ipaddress
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import get_data_dir

DATA_DIR = get_data_dir()


def get_local_ip() -> str:
    """获取本机局域网 IP(UDP 探测,失败回落 127.0.0.1)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _generate_ca(ca_key_file: Path, ca_cert_file: Path):
    """生成 CA 根证书,返回 (ca_key, ca_cert)"""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Root CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            key_cert_sign=True, crl_sign=True, digital_signature=False,
            content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    with open(ca_key_file, "wb") as f:
        f.write(ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(ca_cert_file, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    return ca_key, ca_cert


def _sign_server_cert(ca_key, ca_cert, key_file: Path, cert_file: Path, local_ip: str) -> None:
    """用 CA 签发服务器证书"""
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ClassTrack Server"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ClassTrack"),
    ])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.IPAddress(ipaddress.IPv4Address(local_ip)),
            ]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    with open(key_file, "wb") as f:
        f.write(server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_file, "wb") as f:
        f.write(server_cert.public_bytes(serialization.Encoding.PEM))


def _trust_ca_on_windows(ca_cert_file: Path) -> bool:
    """将 CA 证书添加到当前用户的 Windows 受信任根证书存储"""
    try:
        result = subprocess.run(
            ["certutil", "-addstore", "-user", "Root", str(ca_cert_file)],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def prepare_tls() -> tuple[str, str]:
    """
    准备 HTTPS 服务器证书,返回 (cert_path, key_path) 元组(供 uvicorn ssl 参数)。
    已有证书则复用;否则生成/加载 CA 并签发服务器证书。
    """
    ca_cert_file = DATA_DIR / "ca-cert.pem"
    ca_key_file = DATA_DIR / "ca-key.pem"
    cert_file = DATA_DIR / "cert.pem"
    key_file = DATA_DIR / "key.pem"

    if cert_file.exists() and key_file.exists():
        print("  🔒 HTTPS 已启用(使用已有证书)")
        return str(cert_file), str(key_file)

    try:
        # 生成或加载 CA
        if ca_cert_file.exists() and ca_key_file.exists():
            with open(ca_key_file, "rb") as f:
                ca_key = serialization.load_pem_private_key(f.read(), password=None)
            with open(ca_cert_file, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())
            print("  🔑 使用已有 CA 根证书签发服务器证书")
        else:
            ca_key, ca_cert = _generate_ca(ca_key_file, ca_cert_file)
            print("  🔑 已生成 CA 根证书")

        _sign_server_cert(ca_key, ca_cert, key_file, cert_file, get_local_ip())
        print("  📜 已签发服务器证书(含 localhost + 本机IP)")

        # 自动信任 CA(Windows)
        if _trust_ca_on_windows(ca_cert_file):
            print("  ✅ CA 证书已添加到 Windows 受信任列表")
        else:
            print("  ⚠️ 未能自动信任 CA,桌面浏览器可能仍显示不安全")

        return str(cert_file), str(key_file)
    except ImportError:
        print("  ⚠️ 证书生成失败,使用临时证书")
        return None, None
    except Exception as e:
        print(f"  ⚠️ 证书生成失败: {e}")
        return None, None
