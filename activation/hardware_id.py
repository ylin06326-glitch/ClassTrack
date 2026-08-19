# -*- coding: utf-8 -*-
"""
本机硬件唯一码采集
==================
采集规则（优先级从高到低）：
1. Windows: wmic cpu ProcessorId + wmic diskdrive SerialNumber（C盘所在磁盘）
2. 备选:    wmic baseboard SerialNumber
3. 兜底1:   注册表 MachineGuid（Windows 安装级唯一标识，稳定不变）
4. 兜底2:   UUID.getnode() MAC 地址（最后手段，可能随网卡变化）

注意: Windows 11 24H2 起 wmic 默认被移除，多数新机器会走到 MachineGuid 兜底。
      采集结果进程内缓存，避免每次请求都 spawn 子进程。

拼接规则: CPU_ID + "|" + DISK_ID → SHA256 前 32 位 → 8段4字符大写短码
展示格式: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX

全程无网络，纯本地系统命令。
"""

import hashlib
import subprocess
import sys
import uuid

# 进程级缓存：指纹采集只执行一次，避免每次请求都调用系统命令
_HW_ID_CACHE = {"value": None}


def _run_wmic(command: str) -> str:
    """执行 wmic 命令并返回清理后的输出"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=5,
        )
        # wmic 输出可能是 UTF-8 或系统编码，尝试多种解码
        raw = result.stdout
        for encoding in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")

        lines = text.strip().splitlines()
        # 取第二行（第一行是列标题），去除空白
        for line in lines[1:]:
            val = line.strip()
            if val and val.upper() not in ("", "TO BE FILLED BY O.E.M.", "TO BE FILLED BY O.E.M"):
                return val
        return ""
    except Exception:
        return ""


def get_cpu_serial() -> str:
    """获取 CPU 序列号"""
    return _run_wmic("wmic cpu get processorid")


def get_disk_serial() -> str:
    """
    获取系统盘所在物理磁盘序列号。
    先查 C: 盘对应的磁盘 index，再取该磁盘的序列号。
    """
    # 方法1：直接取所有物理磁盘的第一个
    serial = _run_wmic("wmic diskdrive get serialnumber")
    if serial:
        return serial

    # 方法2：通过 diskpart 关联（更精确但更慢，作为兜底）
    try:
        # wmic path Win32_DiskDrive where "Index=0" get SerialNumber
        result = subprocess.run(
            'wmic path Win32_DiskDrive where "Index=0" get SerialNumber',
            shell=True, capture_output=True, timeout=5
        )
        raw = result.stdout
        for encoding in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
        lines = text.strip().splitlines()
        for line in lines[1:]:
            val = line.strip()
            if val:
                return val
    except Exception:
        pass
    return ""


def get_motherboard_serial() -> str:
    """获取主板序列号（备选方案）"""
    return _run_wmic("wmic baseboard get serialnumber")


def get_mac_address() -> str:
    """获取 MAC 地址（最后兜底方案）"""
    try:
        return uuid.getnode().to_bytes(6, "big").hex(":").upper()
    except Exception:
        return ""


def get_machine_guid() -> str:
    """
    获取 Windows 安装级唯一标识 MachineGuid（注册表）。
    此值在系统安装时生成，重装系统前不会改变，远稳定于 MAC 地址。
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(value).strip()
    except Exception:
        return ""


def collect_hardware_id() -> str:
    """
    采集本机硬件唯一标识符（结果进程内缓存）。

    优先级:
    1. CPU 序列号 + 磁盘序列号
    2. CPU 序列号 + 主板序列号（磁盘不可用时）
    3. 注册表 MachineGuid（wmic 被移除的新系统走这里，稳定）
    4. MAC 地址（最后手段）

    Returns:
        原始硬件标识字符串，如 "BFEBFBFF000906A3|1234567890"
    """
    if _HW_ID_CACHE["value"]:
        return _HW_ID_CACHE["value"]

    cpu = get_cpu_serial()
    disk = get_disk_serial()

    hw_id = ""
    if cpu and disk:
        hw_id = f"{cpu}|{disk}"
    elif cpu:
        mb = get_motherboard_serial()
        if mb:
            hw_id = f"{cpu}|MB_{mb}"

    # 兜底: MachineGuid（Windows 安装级唯一标识，稳定不变）
    if not hw_id:
        guid = get_machine_guid()
        if guid:
            hw_id = f"GUID_{guid}"

    # 最后手段: MAC 地址（可能随网卡/适配器变化，仅在拿不到 Guid 时使用）
    if not hw_id:
        hw_id = f"MAC_{get_mac_address()}"

    _HW_ID_CACHE["value"] = hw_id
    return hw_id


def hardware_id_to_machine_code(hardware_id: str) -> str:
    """
    将原始硬件ID转为展示用的机器码。

    算法: SHA256(hardware_id) → 取前 128 位 (32 hex chars) → 8组4字符大写

    Args:
        hardware_id: 原始硬件标识字符串

    Returns:
        展示用机器码，如 "A3F2-8B1C-9D4E-7F02-15C8-3E9A-6B4D-28F1"
    """
    h = hashlib.sha256(hardware_id.encode("utf-8")).hexdigest().upper()
    # 取前 32 位
    short = h[:32]
    # 每 4 位一组，用 "-" 连接
    parts = [short[i:i+4] for i in range(0, 32, 4)]
    return "-".join(parts)


def get_full_hardware_fingerprint() -> dict:
    """
    获取完整的硬件指纹信息。

    Returns:
        {
            "raw": 原始硬件ID,
            "machine_code": 展示用机器码,
            "cpu": CPU序列号,
            "disk": 磁盘序列号,
        }
    """
    cpu = get_cpu_serial()
    disk = get_disk_serial()
    raw = collect_hardware_id()
    machine_code = hardware_id_to_machine_code(raw)
    return {
        "raw": raw,
        "machine_code": machine_code,
        "cpu": cpu or "(未获取到)",
        "disk": disk or "(未获取到)",
    }


# ============================================================
# 自测（直接运行此脚本时）
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  硬件指纹采集测试")
    print("=" * 50)
    info = get_full_hardware_fingerprint()
    print(f"  CPU 序列号:  {info['cpu']}")
    print(f"  磁盘序列号:  {info['disk']}")
    print(f"  原始硬件ID:  {info['raw']}")
    print(f"  机器码:      {info['machine_code']}")
    print("=" * 50)
