"""
FastAPI main application module - Python 3.12 compatible
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import logging
from datetime import datetime
import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# 确保可以从项目根目录导入
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import settings
from models.api_models import ErrorResponse
from api.routes import (
    dialogue,
    health,
    config,
    upload,
    analysis,
    config_dialogue,
    steady_state,
    status_evaluation,
    functional,
    report_config,
    combined_report,
)
from backend.services.db import init_schema

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    import asyncio
    
    # 启动时执行的代码
    logger.info("AI Chat API starting up (Python 3.12 compatible)...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # 显示配置状态
    available_providers = settings.get_available_providers()
    logger.info(f"Default LLM provider: {settings.DEFAULT_LLM_PROVIDER}")
    logger.info(f"Available providers: {available_providers}")
    
    if not available_providers:
        logger.warning("⚠️  没有可用的LLM提供商！请检查.env配置文件")
    elif not settings.is_provider_available(settings.DEFAULT_LLM_PROVIDER):
        logger.warning(f"⚠️  默认提供商 '{settings.DEFAULT_LLM_PROVIDER}' 不可用，将使用: {available_providers[0]}")
    else:
        logger.info(f"✅ 默认提供商 '{settings.DEFAULT_LLM_PROVIDER}' 已正确配置")
    
    try:
        init_schema()
        logger.info("✅ 数据库表结构检查完成")
    except Exception as db_err:
        logger.warning(f"⚠️ 数据库初始化失败，相关功能将不可用: {db_err}")
    
    logger.info("AI Chat API ready for pure dialogue conversations")
    
    yield
    
    # 关闭时执行的代码
    try:
        logger.info("AI Chat API shutting down...")
    except asyncio.CancelledError:
        # 在关闭过程中，CancelledError 是正常的，不需要记录为错误
        logger.debug("Server shutdown cancelled (normal during shutdown)")
        raise  # 重新抛出以正确传播取消信号


# Create FastAPI application
app = FastAPI(
    title="AI Chat API",
    description="纯对话AI助手 API - 用户与大模型直接对话",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(dialogue.router, prefix="/api", tags=["Dialogue"])
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(config_dialogue.router, prefix="/api/config-dialogue", tags=["Config Dialogue"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(steady_state.router, prefix="/api", tags=["Steady State Reports"])
app.include_router(status_evaluation.router, prefix="/api", tags=["Status Evaluation Reports"])
app.include_router(functional.router, prefix="/api", tags=["Functional Reports"])
app.include_router(report_config.router, prefix="/api", tags=["Report Config"])
app.include_router(combined_report.router, prefix="/api", tags=["Combined Reports"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    error_response = ErrorResponse(
        error="InternalServerError",
        message="An internal server error occurred",
        timestamp=datetime.now().isoformat()
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


def custom_openapi():
    """Custom OpenAPI schema generation"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AI Chat API",
        version="1.0.0",
        description=f"""
        ## AI纯对话助手API
        
        **Python版本**: {sys.version}
        **运行环境**: Python 3.12 兼容模式
        
        本API提供以下核心功能：
        
        ### 💬 纯对话功能
        - 用户与大模型直接对话
        - 智能AI助手响应
        - 多轮对话状态管理
        - 会话管理
        
        ### 系统监控
        - 健康检查
        - 服务状态监控
        
        ### 🔧 Python 3.12 适配说明
        - 使用兼容的依赖包版本
        - 优化了数据处理逻辑
        - 支持最新的Python特性
        """,
        routes=app.routes,
    )
    
    # Add custom info
    openapi_schema["info"]["contact"] = {
        "name": "DRIA Development Team",
        "email": "support@dria.com"
    }
    
    openapi_schema["info"]["x-python-version"] = sys.version
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )