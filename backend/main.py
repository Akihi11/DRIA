"""
Main entry point for the AI Chat Backend - Python 3.12 compatible
Run this file to start the development server
"""

# 导入app对象
from api.main import app

if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path
    
    # 设置控制台编码为UTF-8 (Windows兼容)
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
    # 添加当前目录到Python路径
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    import uvicorn
    from config import settings
    
    print("[START] Starting AI Chat API Server (Python 3.12)...")
    print(f"[API] Server will be available at: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"[DOCS] API Documentation: http://{settings.API_HOST}:{settings.API_PORT}/api/docs")
    print(f"[DEBUG] Debug Mode: {settings.DEBUG}")
    print(f"[INFO] Python 3.12 Compatible Version")
    
    # 确保工作目录正确
    os.chdir(current_dir)
    print(f"[DIR] Working directory: {os.getcwd()}")
    
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,  # 禁用reload以避免路径问题
        log_level=settings.LOG_LEVEL.lower()
    )