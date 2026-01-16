@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   薪酬管理系统 - 安装程序
echo   Payroll Management System - Setup
echo ============================================
echo.

:: Check Python installation
echo [1/4] 检查 Python 安装...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo        已检测到 Python %PYTHON_VERSION%

:: Check if virtual environment exists
echo.
echo [2/4] 创建虚拟环境...
if exist ".venv" (
    echo        虚拟环境已存在，跳过创建
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo        虚拟环境创建成功
)

:: Activate virtual environment
echo.
echo [3/4] 激活虚拟环境...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)
echo        虚拟环境已激活

:: Install dependencies
echo.
echo [4/4] 安装依赖包...
echo        这可能需要几分钟，请耐心等待...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [警告] 部分依赖安装失败，但核心功能应该可用
    echo        如果遇到问题，请参考 README.md 故障排除章节
) else (
    echo        依赖安装完成
)

:: Create necessary directories
echo.
echo 创建必要目录...
if not exist "vault" mkdir vault
if not exist "exports" mkdir exports
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups

echo.
echo ============================================
echo   安装完成！
echo   
echo   运行 run.bat 启动系统
echo ============================================
echo.

pause
