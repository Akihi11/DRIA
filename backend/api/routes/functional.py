"""
功能计算报表API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
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

from backend.services.functional_service import FunctionalService

logger = logging.getLogger(__name__)

router = APIRouter()

# 请求模型
class FunctionalRequest(BaseModel):
    """功能计算报表请求"""
    file_id: str = Field(..., description="数据文件ID")
    config_path: Optional[str] = Field(None, description="配置文件路径（可选，如果提供则使用配置文件）")
    functional_calc: Optional[Dict[str, Any]] = Field(None, description="功能计算配置（可选，如果提供则使用此配置）")


class FunctionalResponse(BaseModel):
    """功能计算报表响应"""
    report_id: str = Field(..., description="报表ID")
    message: str = Field(..., description="响应消息")
    file_path: str = Field(..., description="报表文件路径")


@router.post("/reports/functional/generate", response_model=FunctionalResponse, summary="生成功能计算报表")
async def generate_functional_report(request: FunctionalRequest):
    """
    生成功能计算报表
    
    根据配置分析完整的试验数据流，识别出一个或多个"升速-降速"循环，并计算每个循环中的关键性能指标。
    
    功能计算配置格式：
    {
        "time_base": {
            "channel": "通道名",
            "statistic": "平均值|最大值|最小值|有效值",
            "duration": 1.0,
            "logic": ">|<|>=|<=",
            "threshold": 500.0
        },
        "startup_time": {
            "channel": "通道名",
            "statistic": "平均值|最大值|最小值|有效值",
            "duration": 1.0,
            "logic": ">|<|>=|<=",
            "threshold": 100.0
        },
        "ignition_time": {
            "channel": "通道名",
            "type": "difference",
            "duration": 10.0,
            "logic": ">|<|>=|<=",
            "threshold": 500.0
        },
        "rundown_ng": {
            "channel": "Ng",
            "statistic": "平均值|最大值|最小值|有效值",
            "duration": 1.0,
            "threshold1": 2000.0,
            "threshold2": 200.0
        },
        "rundown_np": {
            "channel": "Np",
            "statistic": "平均值|最大值|最小值|有效值",
            "duration": 1.0,
            "threshold1": 6000.0,
            "threshold2": 500.0
        }
    }
    """
    try:
        # 1. 获取数据文件路径
        uploads_dir = parent_dir / "uploads"
        file_path = uploads_dir / f"{request.file_id}.csv"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件 {request.file_id} 不存在")
        
        # 2. 确定配置文件路径
        if request.config_path:
            # 使用提供的配置文件路径
            config_path = Path(request.config_path)
            if not config_path.exists():
                raise HTTPException(status_code=404, detail=f"配置文件 {request.config_path} 不存在")
        elif request.functional_calc:
            # 创建临时配置文件
            report_id = str(uuid.uuid4())
            reports_dir = parent_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建临时目录用于存储配置文件
            temp_config_dir = reports_dir / report_id
            temp_config_dir.mkdir(parents=True, exist_ok=True)
            config_path = temp_config_dir / "config.json"
            
            # 构建配置
            config = {
                "reportConfig": {
                    "functionalCalc": request.functional_calc
                }
            }
            
            # 保存配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        else:
            raise HTTPException(status_code=400, detail="必须提供 config_path 或 functional_calc 配置")
        
        # 3. 调用服务生成报表
        report_id = str(uuid.uuid4())
        reports_dir = parent_dir / "reports"
        report_file_path = reports_dir / f"functional_report-{report_id}.xlsx"
        
        service = FunctionalService()
        report_path = service.generate_report_simple(
            str(config_path),
            str(file_path),
            str(report_file_path)
        )
        
        # 4. 返回结果
        return FunctionalResponse(
            report_id=report_id,
            message="功能计算报表生成成功",
            file_path=report_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成功能计算报表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成报表失败: {str(e)}")


@router.get("/reports/functional/{report_id}/download", summary="下载功能计算报表")
async def download_functional_report(report_id: str):
    """
    下载功能计算报表
    
    - **report_id**: 报表ID
    """
    try:
        # 新格式：reports/functional_report-{uuid}.xlsx
        reports_dir = parent_dir / "reports"
        report_file = reports_dir / f"functional_report-{report_id}.xlsx"
        
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="报表文件不存在")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(report_file),
            filename=f"functional_report-{report_id}.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载报表失败: {str(e)}")

