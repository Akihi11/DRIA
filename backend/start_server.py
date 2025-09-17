"""
服务器启动脚本 - Python 3.12 兼容版本
提供便捷的服务器启动和管理功能
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    print(f"🐍 Python版本: {sys.version}")
    
    if sys.version_info >= (3, 12):
        print("✅ Python 3.12+ 检测通过")
        return True
    else:
        print("⚠️  建议使用Python 3.12+以获得最佳兼容性")
        return True  # 仍然允许运行

def check_dependencies():
    """检查依赖是否已安装"""
    print("🔍 检查项目依赖...")
    
    try:
        import fastapi
        import uvicorn
        import pydantic
        print("✅ 核心依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def create_directories():
    """创建必要的目录"""
    print("📁 创建必要的目录...")
    
    directories = ["uploads", "reports"]
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"   创建目录: {dir_path}")
        else:
            print(f"   目录已存在: {dir_path}")

def start_server():
    """启动开发服务器"""
    print("🚀 启动AI报表生成API服务器 (Python 3.12)...")
    print()
    
    # 检查Python版本
    if not check_python_version():
        return
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 创建目录
    create_directories()
    
    print("=" * 60)
    print("AI Report Generation API Server (Python 3.12)")
    print("=" * 60)
    print("📍 服务地址: http://127.0.0.1:8000")
    print("📚 API文档: http://127.0.0.1:8000/api/docs") 
    print("🔍 ReDoc文档: http://127.0.0.1:8000/api/redoc")
    print("❤️  健康检查: http://127.0.0.1:8000/api/health")
    print("🐍 Python 3.12 兼容版本")
    print("=" * 60)
    print()
    print("按 Ctrl+C 停止服务器")
    print()
    
    # 启动服务器
    try:
        os.system("python main.py")
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")

if __name__ == "__main__":
    start_server()