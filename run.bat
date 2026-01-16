@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   薪酬管理系统 - 启动中...
echo   Payroll Management System - Starting...
echo ============================================
echo.

:: Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在，请先运行 setup.bat
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Check if streamlit is installed
streamlit --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Streamlit 未安装，请运行 setup.bat
    pause
    exit /b 1
)

:: Set environment variables
set STREAMLIT_SERVER_HEADLESS=true

:: Start the application
echo 正在启动系统...
echo.
echo 浏览器将自动打开，如果没有请手动访问:
echo http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo ============================================
echo.

streamlit run app.py --server.port 8501

pause
