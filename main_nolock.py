#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack 无锁版入口
禁用激活校验，直接进入系统，用于免费分发
"""
import main

# 禁用激活校验
main._ACTIVATION_AVAILABLE = False

# 启动主程序
main.main()
