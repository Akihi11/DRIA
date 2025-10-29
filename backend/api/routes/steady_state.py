"""
稳定状态报表API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from pathlib import Path
import sys
import logging
import uuid
import json

# 添加父目录到Python路径
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.services.steady_state_service import SteadyStateService

logger = logging.getLogger(__name__)

router = APIRouter()

# 请求模型
class SteadyStateRequest(BaseModel):
    """稳定状态报表请求"""
    file_id: str = Field(..., description="数据文件ID")
    display_channels: List[str] = Field(..., description="显示通道列表")
    condition_logic: str = Field(default="AND", description="条件组合逻辑: AND, Cond1_Only, Cond2_Only")
    condition1: Dict[str, Any] = Field(default_factory=dict, description="条件1配置")
    condition2: Dict[str, Any] = Field(default_factory=dict, description="条件2配置")


class SteadyStateResponse(BaseModel):
    """稳定状态报表响应"""
    report_id: str = Field(..., description="报表ID")
    message: str = Field(..., description="响应消息")
    file_path: str = Field(..., description="报表文件路径")


@router.post("/reports/steady_state/generate", response_model=SteadyStateResponse, summary="生成稳定状态报表")
async def generate_steady_state_report(request: SteadyStateRequest):
    """
    生成稳定状态报表
    
    根据配置的条件，从数据流中抓取满足条件的时刻快照，生成Excel报表。
    
    条件1（统计型）：
    - type: statistic
    - channel: 通道名
    - statistic: 统计方法（平均值/最大值/最小值/有效值）
    - duration: 时间窗口（秒）
    - logic: 逻辑操作（>, <, >=, <=）
    - threshold: 阈值
    
    条件2（变化率型）：
    - type: amplitude_change
    - channel: 通道名
    - duration: 时间窗口（秒）
    - logic: 逻辑操作（>, <, >=, <=）
    - threshold: 阈值
    """
    try:
        # 1. 获取数据文件路径
        uploads_dir = parent_dir / "uploads"
        file_path = uploads_dir / f"{request.file_id}.csv"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件 {request.file_id} 不存在")
        
        # 2. 创建临时配置文件
        report_id = str(uuid.uuid4())
        output_dir = parent_dir / "reports" / report_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = output_dir / "config.json"
        config = {
            "reportConfig": {
                "stableState": {
                    "displayChannels": request.display_channels,
                    "conditionLogic": request.condition_logic,
                    "conditions": []
                }
            }
        }
        
        # 添加条件1
        if request.condition1 and request.condition1.get('enabled', False):
            condition1 = {
                "type": "statistic",
                "channel": request.condition1.get('channel'),
                "statistic": request.condition1.get('statistic', '平均值'),
                "duration": request.condition1.get('duration_sec', 1.0),
                "logic": request.condition1.get('logic', '>'),
                "threshold": request.condition1.get('threshold', 0.0)
            }
            config["reportConfig"]["stableState"]["conditions"].append(condition1)
        
        # 添加条件2
        if request.condition2 and request.condition2.get('enabled', False):
            condition2 = {
                "type": "amplitude_change",
                "channel": request.condition2.get('channel'),
                "duration": request.condition2.get('duration_sec', 1.0),
                "logic": request.condition2.get('logic', '<'),
                "threshold": request.condition2.get('threshold', 0.0)
            }
            config["reportConfig"]["stableState"]["conditions"].append(condition2)
        
        # 保存配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 3. 调用服务生成报表
        service = SteadyStateService()
        report_path = service.generate_report(
            str(config_path),
            str(file_path),
            str(output_dir)
        )
        
        # 4. 返回结果
        return SteadyStateResponse(
            report_id=report_id,
            message="稳定状态报表生成成功",
            file_path=report_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成稳定状态报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成报表失败: {str(e)}")


@router.get("/reports/steady_state/{report_id}/download", summary="下载稳定状态报表")
async def download_steady_state_report(report_id: str):
    """
    下载稳定状态报表
    
    - **report_id**: 报表ID
    """
    try:
        reports_dir = parent_dir / "reports" / report_id
        report_file = reports_dir / "steady_state_report.xlsx"
        
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="报表文件不存在")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(report_file),
            filename=f"steady_state_report_{report_id}.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载报表失败: {str(e)}")

