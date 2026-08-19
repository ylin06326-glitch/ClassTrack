#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack — 订单工具模块
==========================
订单号生成 · 过期计算 · 状态流转校验 · 批量过期处理
"""

from datetime import datetime, timedelta


# 有效状态列表
VALID_STATUSES = ("pending", "paid", "expired", "refunded", "cancelled")

# 状态 → 中文标签
STATUS_LABELS = {
    "pending":   "⏳ 待付款",
    "paid":      "✅ 已付款",
    "expired":   "⏰ 已过期",
    "refunded":  "↩️ 已退款",
    "cancelled": "❌ 已取消",
}

# 状态流转规则：current → allowed targets
ALLOWED_TRANSITIONS = {
    "pending":   {"paid", "expired", "cancelled"},
    "paid":      {"refunded"},
    "expired":   set(),       # 终态
    "refunded":  set(),       # 终态
    "cancelled": set(),       # 终态
}


# ============================================================
# 工具函数
# ============================================================

def generate_order_no(db_connection) -> str:
    """
    生成唯一订单号: CT-YYYYMMDD-XXXX

    基于当天日期 + 当日序号自增，安全可靠。
    格式示例: CT-20260728-0001
    """
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"CT-{today}-"

    cursor = db_connection.execute(
        "SELECT COUNT(*) + 1 AS seq FROM orders WHERE order_no LIKE ?",
        (f"{prefix}%",)
    )
    seq = cursor.fetchone()[0]
    return f"{prefix}{seq:04d}"


def calculate_expiry(expiry_minutes: int | str) -> str:
    """
    计算订单过期时间

    Args:
        expiry_minutes: 过期分钟数（或整数字符串）

    Returns:
        ISO 格式的时间字符串 (datetime('now','localtime') 兼容)
    """
    mins = int(expiry_minutes) if isinstance(expiry_minutes, str) else expiry_minutes
    if mins <= 0:
        mins = 30  # 默认30分钟
    return (datetime.now() + timedelta(minutes=mins)).strftime("%Y-%m-%d %H:%M:%S")


def expire_stale_orders(db_connection) -> int:
    """
    将超时的待付款订单批量标记为过期

    Returns:
        被过期的订单数量
    """
    cursor = db_connection.execute(
        "UPDATE orders SET status = 'expired' "
        "WHERE status = 'pending' AND expired_at IS NOT NULL "
        "AND expired_at <= datetime('now', 'localtime')"
    )
    db_connection.commit()
    return cursor.rowcount


def validate_status_transition(current: str, target: str) -> bool:
    """
    校验订单状态流转是否合法

    Args:
        current: 当前状态
        target: 目标状态

    Returns:
        True 表示允许该流转
    """
    if current not in ALLOWED_TRANSITIONS:
        return False
    return target in ALLOWED_TRANSITIONS[current]


def get_status_label(status: str) -> str:
    """返回状态的中文显示标签"""
    return STATUS_LABELS.get(status, status)


def get_status_color(status: str) -> str:
    """返回状态对应的 CSS 颜色值"""
    return {
        "pending":   "#C08050",  # orange
        "paid":      "#3A7D5A",  # green
        "expired":   "#999595",  # grey
        "refunded":  "#C4728E",  # pink
        "cancelled": "#999595",  # grey
    }.get(status, "#5D5A5A")
