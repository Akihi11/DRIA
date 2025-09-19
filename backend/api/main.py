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

# 确保可以从项目根目录导入
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.config import settings
from backend.models.api_models import ErrorResponse
from backend.api.routes import dialogue, file_upload, report_generation, health

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="AI Report Generation API",
    description="智能对话式报表生成系统 API - Python 3.12兼容版本",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
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
app.include_router(file_upload.router, prefix="/api", tags=["File Upload"])
app.include_router(dialogue.router, prefix="/api", tags=["Dialogue"])
app.include_router(report_generation.router, prefix="/api", tags=["Report Generation"])


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
        title="AI Report Generation API",
        version="1.0.0",
        description=f"""
        ## AI对话式报表生成系统API
        
        **Python版本**: {sys.version}
        **运行环境**: Python 3.12 兼容模式
        
        本API提供以下核心功能：
        
        ### 🗂️ 文件管理
        - 上传数据文件（CSV, Excel）
        - 文件预分析和通道检测
        
        ### 💬 智能对话
        - AI引导式配置对话
        - 自然语言参数设置
        - 多轮对话状态管理
        
        ### 📊 报表生成
        - 稳定状态参数汇总表
        - 功能计算汇总表  
        - 状态评估表
        - Excel文件导出（Mock实现）
        
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


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("AI Report Generation API starting up (Python 3.12 compatible)...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # 确保目录存在
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (settings.REPORT_OUTPUT_DIR / "api_generated").mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Upload directory: {settings.UPLOAD_DIR}")
    logger.info(f"Upload directory exists: {settings.UPLOAD_DIR.exists()}")
    logger.info(f"Report output directory: {settings.REPORT_OUTPUT_DIR}")
    logger.info(f"Report output directory exists: {settings.REPORT_OUTPUT_DIR.exists()}")
    
    # 加载默认示例报表
    logger.info("Loading default sample report...")
    from backend.api.routes.report_generation import load_default_sample_report
    load_default_sample_report()


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("AI Report Generation API shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )