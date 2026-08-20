@echo off
chcp 65001 >nul
title ClassTrack - 班级作业分组管理

echo.
echo   ============================================
echo     🎒 ClassTrack - 班级作业分组管理系统
echo     Version 2.0.0
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
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装依赖，请稍候...
    pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo   ❌ 依赖安装失败，请手动运行: pip install -r backend\requirements.txt
        pause
        exit /b 1
    )
)

:: 检查前端是否已构建
if not exist "frontend\dist\index.html" (
    echo   ⏳ 前端尚未构建，正在构建（首次需要几分钟）...
    cd frontend
    if not exist "node_modules" call npm install
    call npm run build
    if errorlevel 1 (
        echo   ❌ 前端构建失败，请安装 Node.js 后重试
        cd ..
        pause
        exit /b 1
    )
    cd ..
)

echo   🚀 正在启动服务...
echo   🌐 浏览器将自动打开，请稍候...
echo.
python launcher.py

pause
