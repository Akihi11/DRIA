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
import numpy as np

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.config import settings
from backend.models.api_models import FileUploadResponse, ErrorResponse
from backend.services.real_data_service import RealDataReader

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
        
        # Create file path - 确保使用绝对路径
        file_extension = Path(file.filename).suffix
        stored_filename = f"{file_id}{file_extension}"
        
        # 强制使用字符串绝对路径
        import logging
        logger = logging.getLogger(__name__)
        
        upload_dir = settings.UPLOAD_DIR
        logger.info(f"DEBUG: upload_dir = {upload_dir}, type = {type(upload_dir)}")
        logger.info(f"DEBUG: upload_dir.exists() = {upload_dir.exists()}")
        logger.info(f"DEBUG: Current working directory = {os.getcwd()}")
        
        # 构造完整的文件路径并转换为字符串
        file_path = str((upload_dir / stored_filename).absolute())
        logger.info(f"DEBUG: file_path (string) = {file_path}")
        logger.info(f"DEBUG: file_path type = {type(file_path)}")
        logger.info(f"DEBUG: Parent dir exists = {Path(file_path).parent.exists()}")
        
        # Save file
        logger.info(f"DEBUG: About to open file for writing: {file_path}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"DEBUG: File saved successfully")
        
        # 转回Path对象用于后续操作
        file_path = Path(file_path)
        
        # Use real data reader to detect channels and extract metadata
        data_reader = RealDataReader()
        
        # Get available channels from the actual file
        detected_channels = data_reader.get_available_channels(str(file_path))
        
        # Get file metadata
        metadata = data_reader.get_file_metadata(str(file_path))
        
        # Read first few rows for preview (limit to first 3 rows and 5 channels)
        preview_channels = detected_channels[:5] if len(detected_channels) > 5 else detected_channels
        try:
            channel_data = data_reader.read(str(file_path), preview_channels)
            first_few_rows = []
            if channel_data and len(channel_data[0].values) > 0:
                # Get first 3 data points
                for i in range(min(3, len(channel_data[0].values))):
                    row_data = {"timestamp": channel_data[0].timestamps[i] if channel_data[0].timestamps else i * 0.03}
                    for ch in channel_data:
                        row_data[ch.channel_name] = float(ch.values[i])
                    first_few_rows.append(row_data)
        except Exception as e:
            # If preview fails, just use empty preview
            first_few_rows = []
        
        # Build preview data
        preview_data = {
            "total_rows": metadata.get("total_rows", 0),
            "duration_seconds": metadata.get("duration_seconds", 0.0),
            "sample_rate": metadata.get("sample_rate", 0.0),
            "first_few_rows": first_few_rows
        }
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=file_path.stat().st_size,
            upload_time=datetime.now().isoformat(),
            available_channels=detected_channels,
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
    获取指定文件的通道信息（包含统计数据）
    
    - **file_id**: 文件ID
    
    返回每个通道的统计信息：最小值、最大值、平均值、样本数等
    """
    
    try:
        # 1. 查找上传的文件
        file_path = None
        for path in settings.UPLOAD_DIR.glob(f"{file_id}.*"):
            file_path = path
            break
        
        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件 {file_id} 不存在"
            )
        
        # 2. 使用真实数据读取器
        data_reader = RealDataReader()
        
        # 3. 获取所有通道名称
        channel_names = data_reader.get_available_channels(str(file_path))
        
        if not channel_names:
            return {
                "file_id": file_id,
                "channels": []
            }
        
        # 4. 读取所有通道数据
        channel_data_list = data_reader.read(str(file_path), channel_names)
        
        # 5. 计算每个通道的统计量
        channels_info = []
        for channel_data in channel_data_list:
            values = np.array([point.value for point in channel_data.data_points])
            
            # 过滤掉 NaN 和 Inf 值
            values = values[np.isfinite(values)]
            
            if len(values) == 0:
                # 如果没有有效数据，跳过该通道
                continue
            
            channels_info.append({
                "name": channel_data.channel_name,
                "unit": channel_data.unit,
                "data_type": "numeric",
                "sample_count": len(values),
                "min_value": float(np.min(values)),
                "max_value": float(np.max(values)),
                "avg_value": float(np.mean(values)),
                "std_value": float(np.std(values))
            })
        
        return {
            "file_id": file_id,
            "channels": channels_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取文件通道信息失败: {str(e)}"
        )


@router.delete("/files/{file_id}", summary="删除文件")
async def delete_file(file_id: str):
    """
    删除上传的文件
    
    - **file_id**: 要删除的文件ID
    """
    
    try:
        # 查找上传的文件
        file_path = None
        for path in settings.UPLOAD_DIR.glob(f"{file_id}.*"):
            file_path = path
            break
        
        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件 {file_id} 不存在"
            )
        
        # 删除文件
        file_path.unlink()
        
        return {"message": f"文件 {file_id} 已成功删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除文件失败: {str(e)}"
        )