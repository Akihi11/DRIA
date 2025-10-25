"""
文件上传API路由
"""
import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import sys

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from config import settings
from models.api_models import ErrorResponse
from services.channel_analysis_service import ChannelAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter()

# 确保上传目录存在
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(exist_ok=True)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = settings.ALLOWED_EXTENSIONS.split(',')
ALLOWED_EXTENSIONS = [ext.strip() for ext in ALLOWED_EXTENSIONS]

def is_allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    if not filename:
        return False
    file_ext = Path(filename).suffix.lower()
    return file_ext in ALLOWED_EXTENSIONS

@router.post("/ai_report/upload", summary="文件上传接口")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件接口
    
    支持的文件类型: .csv, .xlsx, .xls
    最大文件大小: 100MB
    """
    try:
        # 检查文件是否存在
        if not file.filename:
            raise HTTPException(status_code=400, detail="没有选择文件")
        
        # 检查文件扩展名
        if not is_allowed_file(file.filename):
            allowed_exts = ', '.join(ALLOWED_EXTENSIONS)
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型。支持的类型: {allowed_exts}"
            )
        
        # 检查文件大小
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > settings.MAX_FILE_SIZE:
            max_size_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制。最大允许: {max_size_mb}MB"
            )
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix
        new_filename = f"{file_id}{file_ext}"
        file_path = UPLOAD_DIR / new_filename
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        logger.info(f"文件上传成功: {file.filename} -> {new_filename}")
        
        # 自动进行通道分析
        analysis_service = ChannelAnalysisService()
        analysis_result = analysis_service.analyze_file(str(file_path))
        
        # 构建响应数据
        response_data = {
            "success": True,
            "message": "文件上传成功",
            "file_id": file_id,
            "filename": file.filename,
            "saved_filename": new_filename,
            "file_size": file_size,
            "upload_time": datetime.now().isoformat(),
            "analysis": analysis_result
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败: {str(e)}"
        )

@router.get("/ai_report/files", summary="获取已上传文件列表")
async def get_uploaded_files():
    """
    获取已上传的文件列表
    """
    try:
        files = []
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "upload_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return {
            "success": True,
            "files": files,
            "total": len(files)
        }
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取文件列表失败: {str(e)}"
        )

@router.delete("/ai_report/files/{file_id}", summary="删除文件")
async def delete_file(file_id: str):
    """
    删除指定的文件
    """
    try:
        # 查找文件
        file_path = None
        for file in UPLOAD_DIR.iterdir():
            if file.is_file() and file.stem == file_id:
                file_path = file
                break
        
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 删除文件
        file_path.unlink()
        
        logger.info(f"文件删除成功: {file_id}")
        
        return {
            "success": True,
            "message": "文件删除成功",
            "file_id": file_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件删除失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"文件删除失败: {str(e)}"
        )
