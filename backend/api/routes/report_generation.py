"""
Report generation API endpoints
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from datetime import datetime
import uuid
from pathlib import Path
from typing import Dict, Any
import sys

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from config import settings
from models.api_models import ReportGenerationRequest, ReportGenerationResponse
from models.report_config import ReportConfig

router = APIRouter()

# Mock report storage
mock_reports: Dict[str, Dict[str, Any]] = {}


@router.post("/reports/generate", response_model=ReportGenerationResponse, summary="生成报表")
async def generate_report(request: ReportGenerationRequest, background_tasks: BackgroundTasks):
    """
    根据配置生成报表文件
    
    - **session_id**: 会话ID
    - **file_id**: 源数据文件ID
    - **config**: 报表配置参数
    """
    
    try:
        # Validate configuration
        report_config = ReportConfig(**request.config)
        
        # Generate unique report ID
        report_id = str(uuid.uuid4())
        
        # Mock report generation (in production, this would be done in background)
        report_filename = f"report_{report_id}.xlsx"
        report_path = settings.REPORT_OUTPUT_DIR / report_filename
        
        # Create mock Excel file
        await create_mock_excel_report(report_path, report_config)
        
        # Store report metadata
        mock_reports[report_id] = {
            "session_id": request.session_id,
            "file_id": request.file_id,
            "config": request.config,
            "report_path": str(report_path),
            "generation_time": datetime.now().isoformat(),
            "file_size": report_path.stat().st_size if report_path.exists() else 0
        }
        
        report_url = f"/api/reports/download/{report_id}"
        
        return ReportGenerationResponse(
            session_id=request.session_id,
            report_id=report_id,
            report_url=report_url,
            generation_time=datetime.now().isoformat(),
            file_size=mock_reports[report_id]["file_size"],
            success=True
        )
        
    except Exception as e:
        return ReportGenerationResponse(
            session_id=request.session_id,
            report_id="",
            report_url="",
            generation_time=datetime.now().isoformat(),
            file_size=0,
            success=False,
            error_message=str(e)
        )


async def create_mock_excel_report(report_path: Path, config: ReportConfig):
    """创建模拟Excel报表文件"""
    
    # This is a mock implementation
    # In production, this would use openpyxl to create actual Excel files
    
    mock_excel_content = f"""
Mock Excel Report Generated at {datetime.now()}

Configuration:
- Source File ID: {config.source_file_id}
- Sections: {config.report_config.sections}

Report Contents:
{generate_mock_report_content(config)}
"""
    
    # Create directory if it doesn't exist
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write mock content
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(mock_excel_content)


def generate_mock_report_content(config: ReportConfig) -> str:
    """生成模拟报表内容"""
    
    content = []
    
    if "stableState" in config.report_config.sections:
        content.append("""
=== 稳定状态参数汇总表 ===
时间段          | Ng(rpm)    | Temperature(°C)
2023-01-01 10:00-10:30 | 15234.5   | 650.2
2023-01-01 10:45-11:15 | 15187.3   | 648.9
2023-01-01 11:30-12:00 | 15298.7   | 652.1
""")
    
    if "functionalCalc" in config.report_config.sections:
        content.append("""
=== 功能计算汇总表 ===
指标名称    | 计算结果
时间基准    | 45.2秒
启动时间    | 12.8秒  
点火时间    | 3.5秒
Ng余转时间  | 28.7秒
""")
    
    if "statusEval" in config.report_config.sections:
        content.append("""
=== 状态评估表 ===
评估项      | 评估结果 | 状态
超温        | 正常     | ✓
Ng余转时间  | 正常     | ✓
压力异常    | 正常     | ✓
""")
    
    return "\n".join(content)


@router.get("/reports/download/{report_id}", summary="下载报表文件")
async def download_report(report_id: str):
    """
    下载生成的报表文件
    
    - **report_id**: 报表ID
    """
    
    if report_id not in mock_reports:
        raise HTTPException(
            status_code=404,
            detail=f"报表 {report_id} 不存在"
        )
    
    report_info = mock_reports[report_id]
    report_path = Path(report_info["report_path"])
    
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="报表文件不存在"
        )
    
    return FileResponse(
        path=report_path,
        filename=f"report_{report_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/reports/{report_id}/info", summary="获取报表信息")
async def get_report_info(report_id: str):
    """
    获取报表的详细信息
    
    - **report_id**: 报表ID
    """
    
    if report_id not in mock_reports:
        raise HTTPException(
            status_code=404,
            detail=f"报表 {report_id} 不存在"
        )
    
    return {
        "report_id": report_id,
        "report_info": mock_reports[report_id]
    }


@router.delete("/reports/{report_id}", summary="删除报表")
async def delete_report(report_id: str):
    """
    删除指定的报表文件
    
    - **report_id**: 要删除的报表ID
    """
    
    if report_id not in mock_reports:
        raise HTTPException(
            status_code=404,
            detail=f"报表 {report_id} 不存在"
        )
    
    # Delete file
    report_info = mock_reports[report_id]
    report_path = Path(report_info["report_path"])
    if report_path.exists():
        report_path.unlink()
    
    # Remove from storage
    del mock_reports[report_id]
    
    return {"message": f"报表 {report_id} 已成功删除"}


@router.get("/reports", summary="获取报表列表")
async def list_reports(session_id: str = None):
    """
    获取报表列表
    
    - **session_id**: 可选的会话ID过滤
    """
    
    reports = []
    for report_id, report_info in mock_reports.items():
        if session_id is None or report_info["session_id"] == session_id:
            reports.append({
                "report_id": report_id,
                "session_id": report_info["session_id"],
                "generation_time": report_info["generation_time"],
                "file_size": report_info["file_size"],
                "download_url": f"/api/reports/download/{report_id}"
            })
    
    return {
        "reports": reports,
        "total": len(reports)
    }