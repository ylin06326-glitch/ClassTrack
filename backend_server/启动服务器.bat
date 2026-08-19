@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   ClassTrack.com Web 服务 + 管理后台
echo ============================================
echo.
echo   [1] 启动 Web 服务 (用户页面)
echo   [2] 启动管理后台 (PyQt6 桌面端)
echo   [3] 同时启动两者
echo   [4] 启动 EXE 版本 (dist/ClassTrack_Server.exe)
echo   [0] 退出
echo.
set /p choice="请选择 (0-4): "

if "%choice%"=="1" goto web
if "%choice%"=="2" goto admin
if "%choice%"=="3" goto both
if "%choice%"=="4" goto exe
if "%choice%"=="0" exit /b

:web
echo.
echo 启动 Web 服务 (http://localhost:5099)...
cd /d "%~dp0"
python app.py
goto end

:admin
echo.
echo 启动 PyQt6 管理后台...
cd /d "%~dp0"
python admin_app.py
goto end

:both
echo.
echo 启动 Web 服务...
cd /d "%~dp0"
start "ClassTrack Web" python app.py
echo Web 服务已启动 (http://localhost:5099)
echo.
echo 启动 PyQt6 管理后台...
python admin_app.py
goto end

:exe
echo.
echo 启动 EXE 版本...
cd /d "%~dp0"
if exist "dist\ClassTrack_Server.exe" (
    start "ClassTrack Server" "dist\ClassTrack_Server.exe"
    echo ClassTrack_Server.exe 已启动 (http://localhost:5099)
) else (
    echo 未找到 dist\ClassTrack_Server.exe，请先运行 build.bat 打包
)
goto end

:end
pause
