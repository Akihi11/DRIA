"""
File upload API endpoints
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid
import shutil
from pathlib import Path
from typing import List
import sys
import os

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from config import settings
from models.api_models import FileUploadResponse, ErrorResponse

router = APIRouter()


def validate_file_extension(filename: str) -> bool:
    """验证文件扩展名"""
    file_path = Path(filename)
    return file_path.suffix.lower() in settings.ALLOWED_EXTENSIONS


def validate_file_size(file: UploadFile) -> bool:
    """验证文件大小"""
    # Note: This is a simplified check. In production, you'd want to check the actual file size
    return True


@router.post("/upload", response_model=FileUploadResponse, summary="上传数据文件")
async def upload_file(file: UploadFile = File(...)):
    """
    上传数据文件（CSV或Excel格式）
    
    - **file**: 要上传的数据文件
    
    返回文件ID和基本信息，包括检测到的通道列表
    """
    
    # Validate file extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持的格式: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Validate file size
    if not validate_file_size(file):
        raise HTTPException(
            status_code=413,
            detail=f"文件太大。最大允许大小: {settings.MAX_FILE_SIZE / (1024*1024):.0f}MB"
        )
    
    try:
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Create file path
        file_extension = Path(file.filename).suffix
        stored_filename = f"{file_id}{file_extension}"
        file_path = settings.UPLOAD_DIR / stored_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Mock channel detection (in real implementation, this would analyze the file)
        detected_channels = [
            "Ng(rpm)",
            "Temperature(°C)", 
            "Pressure(kPa)",
            "Fuel_Flow(kg/h)",
            "Vibration(mm/s)"
        ]
        
        # Mock preview data
        preview_data = {
            "total_rows": 10000,
            "duration_seconds": 300.5,
            "sample_rate": 33.3,
            "first_few_rows": [
                {"timestamp": 0.0, "Ng(rpm)": 15234, "Temperature(°C)": 650.2},
                {"timestamp": 0.03, "Ng(rpm)": 15241, "Temperature(°C)": 650.5},
                {"timestamp": 0.06, "Ng(rpm)": 15238, "Temperature(°C)": 650.1}
            ]
        }
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=file_path.stat().st_size,
            upload_time=datetime.now().isoformat(),
            detected_channels=detected_channels,
            preview_data=preview_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败: {str(e)}"
        )


@router.get("/files/{file_id}/channels", summary="获取文件通道信息")
async def get_file_channels(file_id: str):
    """
    获取指定文件的通道信息
    
    - **file_id**: 文件ID
    """
    
    # Mock implementation - in reality, this would read the actual file
    return {
        "file_id": file_id,
        "channels": [
            {
                "name": "Ng(rpm)",
                "unit": "rpm",
                "data_type": "numeric",
                "sample_count": 10000,
                "min_value": 1000.0,
                "max_value": 16000.0,
                "avg_value": 12500.5
            },
            {
                "name": "Temperature(°C)",
                "unit": "°C", 
                "data_type": "numeric",
                "sample_count": 10000,
                "min_value": 15.2,
                "max_value": 850.7,
                "avg_value": 425.3
            },
            {
                "name": "Pressure(kPa)",
                "unit": "kPa",
                "data_type": "numeric", 
                "sample_count": 10000,
                "min_value": 0.0,
                "max_value": 1200.0,
                "avg_value": 600.0
            }
        ]
    }


@router.delete("/files/{file_id}", summary="删除文件")
async def delete_file(file_id: str):
    """
    删除上传的文件
    
    - **file_id**: 要删除的文件ID
    """
    
    try:
        # Find and delete file (mock implementation)
        # In reality, you'd search for the file by ID and delete it
        
        return {"message": f"文件 {file_id} 已成功删除"}
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"文件 {file_id} 不存在"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除文件失败: {str(e)}"
        )