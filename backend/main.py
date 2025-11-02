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
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
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
    
    logger.info("Starting AI Chat API Server (Python 3.12)...")
    logger.info(f"Server will be available at: http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"API Documentation: http://{settings.API_HOST}:{settings.API_PORT}/api/docs")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    # 确保工作目录正确
    os.chdir(current_dir)
    
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,  # 禁用reload以避免路径问题
        log_level=settings.LOG_LEVEL.lower()
    )