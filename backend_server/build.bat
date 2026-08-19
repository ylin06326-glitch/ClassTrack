@echo off
chcp 65001 >nul
title ClassTrack Backend Server - 打包构建

echo.
echo   ============================================
echo     🔨 ClassTrack Backend Server v2.0 - 打包
echo     生成 Windows 独立可执行程序
echo   ============================================
echo.

cd /d "%~dp0"

:: 检查 PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装 PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 检查项目依赖
python -c "import flask, pyngrok, PyQt6" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装项目依赖...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 检查激活模块依赖
python -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装加密库...
    pip install cryptography -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo   🔨 开始打包 (使用 backend_server.spec)...
echo.

:: 清理旧构建
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: PyInstaller 打包
pyinstaller --clean --noconfirm backend_server.spec

if errorlevel 1 (
    echo.
    echo   ❌ 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo   ============================================
echo     ✅ 打包完成！
echo     📁 输出位置: dist\ClassTrack_Server.exe
echo   ============================================
echo.
echo   💡 使用说明:
echo      - 将 dist\ClassTrack_Server.exe 复制到任意目录运行
echo      - 首次运行会自动创建 data 文件夹
echo      - data\classtrack_server.db 是数据库文件
echo      - data\files\ 存放软件包
echo      - data\media\ 存放媒体文件
echo      - activation\private_key.pem 需放在 exe 同级目录
echo.
echo   🌐 访问:
echo      - 用户页面: http://localhost:5099
echo      - 管理后台: http://localhost:5099/admin
echo      - 或双击运行 admin_app.py 使用桌面管理端
echo.
echo   🔧 v2.0 新功能:
echo      - 内网穿透 (需配置 ngrok auth token)
echo      - 完整订单系统
echo      - 隧道状态监控
echo.
pause
