@echo off
echo ========================================
echo AI Report Generation API Server
echo Python 3.12 Compatible Version
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python未安装或不在PATH中
    echo 请先安装Python 3.12+
    pause
    exit /b 1
)

echo 🐍 检测到的Python版本:
python --version

REM 检查是否在正确的目录
if not exist "main.py" (
    echo ❌ 请在backend目录下运行此脚本
    pause
    exit /b 1
)

REM 安装依赖（如果需要）
if not exist "venv" (
    echo 🔧 首次运行，正在设置虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo 📦 安装Python 3.12兼容依赖...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM 启动服务器
echo 🚀 启动Python 3.12兼容服务器...
python start_server.py

pause