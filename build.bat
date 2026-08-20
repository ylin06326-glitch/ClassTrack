@echo off
chcp 65001 >nul
title ClassTrack - 打包构建

echo.
echo   ============================================
echo     🔨 ClassTrack v2.0 - 打包构建脚本
echo     FastAPI + Vue3 前后端分离架构
echo     生成 Windows 独立可执行程序
echo   ============================================
echo.

cd /d "%~dp0"

:: 检查 Python 依赖
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装 PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

python -c "import fastapi, uvicorn, pandas, openpyxl, qrcode, PIL" >nul 2>&1
if errorlevel 1 (
    echo   ⏳ 正在安装项目依赖...
    pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

:: 构建前端（Vite）
echo   📦 正在构建前端...
cd frontend
if not exist "node_modules" (
    echo   ⏳ 首次构建,安装前端依赖...
    call npm install
)
call npm run build
if errorlevel 1 (
    echo   ❌ 前端构建失败
    cd ..
    pause
    exit /b 1
)
cd ..

echo   🔨 开始打包 (使用 ClassTrack.spec)...
echo.

:: 清理旧构建
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: PyInstaller 使用 spec 文件打包
pyinstaller --clean --noconfirm ClassTrack.spec

if errorlevel 1 (
    echo.
    echo   ❌ 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo   ============================================
echo     ✅ 打包完成！
echo     📁 输出位置: dist\ClassTrack.exe
echo   ============================================
echo.
echo   📦 正在生成发布压缩包（仅 exe + 使用说明）...
if exist "dist\release" rmdir /s /q "dist\release"
mkdir "dist\release"
copy /y "dist\ClassTrack.exe" "dist\release\" >nul
if exist "使用说明书.md" copy /y "使用说明书.md" "dist\release\使用说明书.txt" >nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\release\*' -DestinationPath 'dist\ClassTrack.zip' -Force"
if errorlevel 1 (
    echo   ⚠️ 压缩包生成失败（不影响 exe 本身）
) else (
    echo   📦 发布压缩包: dist\ClassTrack.zip
)
echo.
echo   💡 使用说明:
echo      - 把 dist\ClassTrack.zip 发给老师，解压后运行 exe 即可
echo      - 所有数据保存在 %%APPDATA%%\ClassTrack（不再依赖 exe 所在位置）
echo      - 老版本数据（exe 旁 data 文件夹）首次运行会自动迁移
echo      - 浏览器会自动打开，无需手动输入网址
echo      - 二维码打印功能离线可用
echo      - 手机扫码功能离线可用
echo.
echo   ⚠️ 重要:
echo      - 只分发 ClassTrack.zip！不要手动把 dist\data 文件夹
echo        或 data 目录打包进去（内含你的激活文件、测试数据和 API Key）
echo      - 老师首次运行会看到激活页面，需按机器码生成激活文件
echo.
pause
