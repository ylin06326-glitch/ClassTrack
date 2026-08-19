@echo off
chcp 65001 >nul
title ClassTrack - 班级作业分组管理

echo.
echo   ============================================
echo     🎒 ClassTrack - 班级作业分组管理系统
echo     Version 1.0.0
echo   ============================================
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   ❌ 未找到Python，请先安装Python 3.8+
    echo   📥 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查依赖
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装依赖，请稍候...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo   ❌ 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo   🚀 正在启动服务...
echo   🌐 浏览器将自动打开，请稍候...
echo.
python main.py

pause