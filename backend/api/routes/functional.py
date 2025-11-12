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
import tempfile

# 添加父目录到Python路径
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.services.functional_service import FunctionalService
from services.db import materialize_uploaded_file, save_report_file, get_report_file_by_name

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
        report_id = str(uuid.uuid4())
        report_name = f"functional_report-{report_id}.xlsx"

        try:
            with materialize_uploaded_file(request.file_id) as (file_path, _meta):
                if request.config_path:
                    config_path = Path(request.config_path)
                    if not config_path.exists():
                        raise HTTPException(status_code=404, detail=f"配置文件 {request.config_path} 不存在")
                    temp_config_context = None
                elif request.functional_calc:
                    temp_config_context = tempfile.TemporaryDirectory(prefix="functional_config_")
                    tmp_config_dir = Path(temp_config_context.name)
                    config_path = tmp_config_dir / "config.json"
                    config = {
                        "reportConfig": {
                            "functionalCalc": request.functional_calc
                        }
                    }
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                else:
                    raise HTTPException(status_code=400, detail="必须提供 config_path 或 functional_calc 配置")

                try:
                    with tempfile.TemporaryDirectory(prefix="functional_report_") as tmp_dir:
                        tmp_dir_path = Path(tmp_dir)
                        report_output_path = tmp_dir_path / report_name
                        service = FunctionalService()
                        report_path = service.generate_report_simple(
                            str(config_path),
                            str(file_path),
                            str(report_output_path)
                        )
                        report_bytes = Path(report_path).read_bytes()
                        save_report_file(
                            file_id=request.file_id,
                            report_name=report_name,
                            content=report_bytes,
                        )
                finally:
                    if temp_config_context is not None:
                        temp_config_context.cleanup()

        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"文件 {request.file_id} 不存在")

        download_path = f"/api/reports/functional/{report_id}/download"
        return FunctionalResponse(
            report_id=report_id,
            message="功能计算报表生成成功",
            file_path=download_path
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
        report_name = f"functional_report-{report_id}.xlsx"
        row = get_report_file_by_name(report_name)
        if not row:
            raise HTTPException(status_code=404, detail="报表文件不存在")

        report_name, content_type, content = row

        from fastapi.responses import Response
        headers = {"Content-Disposition": f'attachment; filename="{report_name}"'}
        return Response(content=bytes(content), media_type=content_type, headers=headers)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载报表失败: {str(e)}")

