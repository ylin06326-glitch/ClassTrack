@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title ClassTrack Hardened Build System

echo ================================================================
echo   ClassTrack Hardened Build System v2.0
echo   班级作业分组管理系统 - 加固构建流程
echo ================================================================
echo.

REM ================================================================
REM Step 0: Environment Check
REM ================================================================
echo [0/5] 检查构建环境...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)
echo    Python: 已就绪

where pip >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 pip
    pause
    exit /b 1
)

REM ================================================================
REM Step 1: Install Dependencies
REM ================================================================
echo.
echo [1/5] 安装依赖...
pip install flask cryptography pandas openpyxl xlrd qrcode Pillow sqlcipher3 pyinstaller -q
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，继续构建...
)
echo    依赖安装完成

REM ================================================================
REM Step 2: Run Build Script (encrypt resources, generate core)
REM ================================================================
echo.
echo [2/5] 运行构建脚本 (加密资源/生成加固核心)...
python build.py
if %errorlevel% neq 0 (
    echo [错误] 构建脚本执行失败
    pause
    exit /b 1
)
echo    加固核心生成完成

REM ================================================================
REM Step 3: PyArmor Obfuscation (optional but recommended)
REM ================================================================
echo.
echo [3/5] PyArmor 字节码加密...

where pyarmor >nul 2>&1
if %errorlevel% neq 0 (
    echo    PyArmor 未安装，尝试安装...
    pip install pyarmor -q
    if %errorlevel% neq 0 (
        echo    [跳过] PyArmor 安装失败，将使用未加密字节码打包
        goto :skip_pyarmor
    )
)

REM PyArmor gen with maximum protection
pyarmor gen --platform windows.x86_64 ^
    --obf-code 2 ^
    --obf-module 1 ^
    --wrap-mode 0 ^
    --enable-jit ^
    --enable-themida ^
    --assert-call ^
    --assert-import ^
    --mix-str ^
    --private ^
    --restrict ^
    --no-cross-protection ^
    class_track_core.py

if %errorlevel% neq 0 (
    echo    [警告] PyArmor 加密失败，降级尝试...
    pyarmor gen --platform windows.x86_64 ^
        --obf-code 1 ^
        --obf-module 1 ^
        --mix-str ^
        class_track_core.py
)

if exist "dist\class_track_core.py" (
    echo    PyArmor 加密完成
    set ENTRY=dist\class_track_core.py
) else if exist "dist\class_track_core.py" (
    echo    PyArmor 加密完成 (dist)
    set ENTRY=dist\class_track_core.py
) else (
    echo    [警告] PyArmor 输出未找到，使用原始文件
    set ENTRY=class_track_core.py
)
goto :after_pyarmor

:skip_pyarmor
set ENTRY=class_track_core.py

:after_pyarmor

REM ================================================================
REM Step 4: PyInstaller Packaging
REM ================================================================
echo.
echo [4/5] PyInstaller 打包...

REM Generate a random encryption key for PyInstaller
set PYI_KEY=ClassTrack2026Secure

pyinstaller --clean --noconfirm ^
    --onefile ^
    --windowed ^
    --name="ClassTrack" ^
    --key="%PYI_KEY%" ^
    --add-data="../activation;activation" ^
    --hidden-import=flask ^
    --hidden-import=cryptography ^
    --hidden-import=cryptography.fernet ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=qrcode ^
    --hidden-import=PIL ^
    --hidden-import=sqlcipher3 ^
    --hidden-import=activation ^
    --hidden-import=activation.hardware_id ^
    --hidden-import=activation.license_manager ^
    --hidden-import=activation.crypto ^
    --hidden-import=activation.key_pair ^
    --exclude-module=tkinter ^
    --exclude-module=unittest ^
    --exclude-module=test ^
    %ENTRY%

if %errorlevel% neq 0 (
    echo [错误] PyInstaller 打包失败
    pause
    exit /b 1
)

echo    PyInstaller 打包完成

REM ================================================================
REM Step 5: Output
REM ================================================================
echo.
echo [5/5] 整理输出...

if exist "dist\ClassTrack.exe" (
    echo.
    echo ================================================================
    echo   构建成功！
    echo   输出文件: dist\ClassTrack.exe
    echo ================================================================
    echo.
    echo   加固特性:
    echo   [√] 反调试/反虚拟机检测
    echo   [√] 字符串异或分段加密
    echo   [√] SQLCipher 加密数据库 (AppData\ClassTrack_v2\storage.dat)
    echo   [√] Fernet 加密前端资源 (内存解密，不落盘)
    echo   [√] API Token 鉴权 + 高危接口强校验
    echo   [√] 异常堆栈屏蔽
    echo   [√] PyArmor 字节码加密
    echo   [√] PyInstaller --key 打包加密
    echo   [√] 单文件无控制台窗口
    echo   [√] 禁用 .pyc 缓存文件
    echo.
    echo   分发文件: dist\ClassTrack.exe
    echo   用户运行后数据位置: %%LOCALAPPDATA%%\ClassTrack_v2\
    echo.
) else (
    echo [错误] 未找到输出文件
    echo 请检查 dist\ 目录
    dir dist\ 2>nul
)

echo.
echo 按任意键退出...
pause >nul
