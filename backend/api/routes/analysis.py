"""
数据分析API - 通道统计分析
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import os
import logging

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.models.api_models import (
    ChannelAnalysisRequest, 
    ChannelAnalysisResponse, 
    ChannelStatistics,
    ErrorResponse
)

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analysis/channels", response_model=ChannelAnalysisResponse, summary="通道统计分析")
async def analyze_channels(request: ChannelAnalysisRequest):
    """
    分析CSV文件中的通道数据，计算每个通道的统计值
    
    - **file_id**: 上传文件的ID
    """
    
    try:
        # 构建文件路径
        uploads_dir = Path(__file__).parent.parent.parent / "uploads"
        file_path = uploads_dir / f"{request.file_id}.csv"
        
        # 检查文件是否存在
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件 {request.file_id} 不存在"
            )
        
        # 读取CSV文件
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"无法读取CSV文件: {str(e)}"
            )
        
        # 检查数据是否为空
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV文件为空"
            )
        
        # 获取通道列（排除时间列）
        time_columns = ['time', 'time[s]', 'Time', 'Time[s]', 'timestamp', 'Timestamp']
        channel_columns = [col for col in df.columns if col.lower() not in [t.lower() for t in time_columns]]
        
        if not channel_columns:
            raise HTTPException(
                status_code=400,
                detail="未找到有效的通道数据列"
            )
        
        # 计算每个通道的统计值
        channels_stats = []
        
        for channel in channel_columns:
            try:
                # 获取数值数据，排除NaN值
                data = pd.to_numeric(df[channel], errors='coerce').dropna()
                
                if len(data) == 0:
                    logger.warning(f"通道 {channel} 没有有效数据")
                    continue
                
                # 计算统计值
                mean_val = float(data.mean())
                max_val = float(data.max())
                min_val = float(data.min())
                std_val = float(data.std())
                count_val = int(len(data))
                
                channel_stat = ChannelStatistics(
                    channel_name=channel,
                    mean=mean_val,
                    max_value=max_val,
                    min_value=min_val,
                    std_dev=std_val,
                    count=count_val
                )
                
                channels_stats.append(channel_stat)
                
            except Exception as e:
                logger.warning(f"处理通道 {channel} 时出错: {str(e)}")
                continue
        
        if not channels_stats:
            raise HTTPException(
                status_code=400,
                detail="没有找到有效的通道数据"
            )
        
        # 返回分析结果
        return ChannelAnalysisResponse(
            file_id=request.file_id,
            total_channels=len(channels_stats),
            channels=channels_stats,
            analysis_time=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"通道分析错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"分析过程中出现错误: {str(e)}"
        )


@router.get("/analysis/channels/{file_id}", response_model=ChannelAnalysisResponse, summary="获取通道分析结果")
async def get_channel_analysis(file_id: str):
    """
    获取指定文件的通道分析结果
    
    - **file_id**: 文件ID
    """
    
    # 这里可以实现缓存机制，暂时直接调用分析函数
    request = ChannelAnalysisRequest(file_id=file_id)
    return await analyze_channels(request)
