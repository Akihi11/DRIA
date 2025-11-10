import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.combined_report_service import CombinedReportService

logger = logging.getLogger(__name__)
router = APIRouter()
from pathlib import Path as _PathAlias
from fastapi.responses import FileResponse


class CombinedReportRequest(BaseModel):
    file_id: str = Field(..., description="上传的数据文件ID（对应 uploads 下的 csv）")
    steady_config_path: Optional[str] = Field(None, description="稳态配置文件路径（config.json）")
    functional_config_path: Optional[str] = Field(None, description="功能计算配置文件路径（config.json）")
    status_eval_config_path: Optional[str] = Field(None, description="状态评估配置文件路径（config.json）")
    # 如果未提供路径，可按需在前端先落盘生成；这里简单化为必填三者之一


class CombinedReportResponse(BaseModel):
    report_id: str
    message: str
    file_path: str


@router.post("/reports/combined/generate", response_model=CombinedReportResponse, summary="生成合并报表（3表合一Excel）")
async def generate_combined_report(request: CombinedReportRequest):
    try:
        # 计算项目根目录，避免从 api.main 导入以打破循环依赖
        project_root = Path(__file__).parent.parent.parent

        # 校验数据文件
        uploads_dir = project_root / "uploads"
        file_path = uploads_dir / f"{request.file_id}.csv"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件 {request.file_id} 不存在")

        # 校验配置路径
        if not request.steady_config_path or not Path(request.steady_config_path).exists():
            raise HTTPException(status_code=400, detail="必须提供有效的稳态配置 steady_config_path")
        if not request.functional_config_path or not Path(request.functional_config_path).exists():
            raise HTTPException(status_code=400, detail="必须提供有效的功能计算配置 functional_config_path")
        if not request.status_eval_config_path or not Path(request.status_eval_config_path).exists():
            raise HTTPException(status_code=400, detail="必须提供有效的状态评估配置 status_eval_config_path")

        report_id = str(uuid.uuid4())
        reports_dir = project_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        merged_report_path = reports_dir / f"combined_report-{report_id}.xlsx"

        service = CombinedReportService()
        result_path = service.generate_all_and_merge(
            request.steady_config_path,
            request.functional_config_path,
            request.status_eval_config_path,
            str(file_path),
            str(merged_report_path)
        )

        return CombinedReportResponse(
            report_id=report_id,
            message="合并报表生成成功（稳态/功能计算/状态评估三表合一）",
            file_path=result_path
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成合并报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成合并报表失败: {str(e)}")


@router.get("/reports/combined/{report_id}/download", summary="下载合并报表（三表合一）")
async def download_combined_report(report_id: str):
    """
    下载合并报表文件
    """
    try:
        # 计算项目根目录，避免从 api.main 导入以打破循环依赖
        project_root = _PathAlias(__file__).parent.parent.parent
        reports_dir = project_root / "reports"
        report_file = reports_dir / f"combined_report-{report_id}.xlsx"

        if not report_file.exists():
            raise HTTPException(status_code=404, detail="合并报表文件不存在")

        return FileResponse(
            path=str(report_file),
            filename=f"combined_report-{report_id}.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载合并报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载合并报表失败: {str(e)}")


