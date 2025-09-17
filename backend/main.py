"""
Main entry point for the AI Report Generation Backend - Python 3.12 compatible
Run this file to start the development server
"""

if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path
    
    # 添加当前目录到Python路径
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    import uvicorn
    from config import settings
    
    print("🚀 Starting AI Report Generation API Server (Python 3.12)...")
    print(f"📍 Server will be available at: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📚 API Documentation: http://{settings.API_HOST}:{settings.API_PORT}/api/docs")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print(f"🐍 Python 3.12 Compatible Version")
    
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )