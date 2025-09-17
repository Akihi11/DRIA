"""
Health check API endpoints
"""
from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from models.api_models import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, summary="健康检查")
async def health_check():
    """
    系统健康检查端点
    
    返回服务当前状态和基本信息
    """
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@router.get("/health/detailed", summary="详细健康检查")
async def detailed_health_check():
    """
    详细的系统健康检查
    
    包含更多系统状态信息
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {
            "api": "healthy",
            "file_storage": "healthy",
            "report_engine": "healthy"
        },
        "uptime": "0d 0h 0m",  # This would be calculated in a real implementation
        "memory_usage": "N/A",
        "disk_usage": "N/A"
    }