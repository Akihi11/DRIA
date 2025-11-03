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
current_dir = Path(__file__).resolve().parent  # backend/api/routes
parent_dir = current_dir.parent.parent  # backend 目录 (routes -> api -> backend)
sys.path.insert(0, str(parent_dir))

from config import settings
from models.api_models import ErrorResponse
from services.channel_analysis_service import ChannelAnalysisService
import json

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

# 配置唯一化
CONFIG_PATH = parent_dir / "config_sessions" / "config_session.json"

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
        
        # 确保分析结果有效
        if not analysis_result or not analysis_result.get("success"):
            logger.warning(f"文件分析可能失败，但仍继续创建JSON文件。结果: {analysis_result}")
        
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

        # 创建基于config_full.json模板的配置文件，存储通道信息和统计值
        # 必须在 recreate 异常捕获之前执行，确保即使失败也能看到错误
        try:
            # 存放在 backend/config_sessions/ 目录
            # upload.py 位于 backend/api/routes/upload.py
            # __file__ 的 parent.parent.parent 就是 backend 目录
            # 但也可以使用代码中已定义的 parent_dir（第16行已计算好）
            config_dir = CONFIG_PATH.parent
            
            config_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用年月日时分秒毫秒格式命名：YYYYMMDDHHmmssSSS.json（添加毫秒避免同一秒内冲突）
            # timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # %f是微秒，取前3位即毫秒
            # config_filename = f"{timestamp_str}.json"
            # config_path = config_dir / config_filename
            
            # 构建符合config_full.json模板结构的配置
            channels_data = []
            channels_list = analysis_result.get("channels", []) if analysis_result else []
            
            if not channels_list:
                logger.warning("分析结果中没有通道数据，将创建空的channels数组")
            
            for ch in channels_list:
                if not ch or not ch.get("channel_name"):
                    logger.warning(f"跳过无效的通道数据: {ch}")
                    continue
                try:
                    channels_data.append({
                        "channel_name": ch.get("channel_name"),
                        "statistics": {
                            "count": ch.get("count", 0),
                            "mean": ch.get("mean", 0.0),
                            "max_value": ch.get("max_value", 0.0),
                            "min_value": ch.get("min_value", 0.0),
                            "std_dev": ch.get("std_dev", 0.0),
                            "range": ch.get("range", 0.0),
                            "median": ch.get("median", 0.0),
                            "q25": ch.get("q25", 0.0),
                            "q75": ch.get("q75", 0.0),
                            "variance": ch.get("variance", 0.0)
                        }
                    })
                except Exception as ch_err:
                    logger.warning(f"处理通道 {ch.get('channel_name', 'unknown')} 时出错: {ch_err}")
                    continue
            
            # 提取通道名列表作为 availableChannels（供功能计算等使用）
            # 注意：必须按照上传文件的通道顺序保存，保持与原始文件列顺序一致
            available_channels = [ch.get("channel_name") for ch in channels_data if ch.get("channel_name")]
            
            config_content = {
                "sourceFileId": file.filename,
                "fileId": file_id,  # 保存原始的UUID格式file_id
                "configFileName": "config_session.json",  # 保存配置文件名（时间戳格式）
                "uploadTime": response_data["upload_time"],
                "channels": channels_data,
                "availableChannels": available_channels,  # 添加可用通道列表
                "reportConfig": {
                    "sections": []
                }
            }

            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(config_content, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 已创建配置文件: {CONFIG_PATH}")
        except Exception as config_err:
            logger.error(f"❌ 创建配置文件失败: {config_err}", exc_info=True)

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


@router.post("/ai_report/meta/{file_id}/report_type", summary="更新配置文件中的报表类型")
async def update_upload_meta_report_type(file_id: str, report_type: str = Form(...)):
    """
    更新上传文件对应的配置JSON中的报表类型字段。
    前端在用户选择报表类型后调用。
    统一使用 backend/config_sessions/ 目录存储。
    """
    try:
        # 使用 backend/config_sessions/ 目录
        # backend_dir = Path(__file__).resolve().parent.parent.parent
        # config_dir = backend_dir / "config_sessions"
        
        # 通过fileId查找对应的JSON文件
        config_path = CONFIG_PATH
        
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="配置文件不存在，请先上传文件")

        # 读取现有配置
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        # 更新报表类型
        config["reportType"] = report_type
        # 可选：记录一次历史
        if "history" not in config:
            config["history"] = []
        config["history"].append({
            "timestamp": datetime.now().isoformat(),
            "action": "set_report_type",
            "value": report_type
        })

        # 保存更新后的配置
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info(f"已更新报表类型: {file_id} -> {report_type}")
        return {"success": True, "file_id": file_id, "report_type": report_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新报表类型失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新报表类型失败: {str(e)}")
