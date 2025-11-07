"""
状态评估报表API
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

from backend.services.status_evaluation_service import StatusEvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()

# 请求模型
class StatusEvaluationRequest(BaseModel):
    """状态评估报表请求"""
    file_id: str = Field(..., description="数据文件ID")
    config_path: str = Field(..., description="配置文件路径（可选，如果提供则使用配置文件）")
    evaluations: List[Dict[str, Any]] = Field(default_factory=list, description="评估项配置列表（可选）")


class StatusEvaluationResponse(BaseModel):
    """状态评估报表响应"""
    report_id: str = Field(..., description="报表ID")
    message: str = Field(..., description="响应消息")
    file_path: str = Field(..., description="报表文件路径")


@router.post("/reports/status_evaluation/generate", response_model=StatusEvaluationResponse, summary="生成状态评估报表")
async def generate_status_evaluation_report(request: StatusEvaluationRequest):
    """
    生成状态评估报表
    
    根据配置对数据流进行"地毯式"扫描，实现"一票否决"机制。
    一旦任何时刻触发失败条件，就将评估结论翻转为"否"。
    
    评估项配置格式：
    {
        "item": "评估项ID",
        "assessmentName": "评估项目名称",
        "type": "continuous_check",  # 可选，如果所有评估项相同，会自动提取为全局默认值
        "conditionLogic": "AND",     # 可选，如果所有评估项相同，会自动提取为全局默认值
        "conditions": [
            {
                "channel": "通道名",
                "statistic": "平均值|最大值|最小值|有效值|瞬时值|difference",
                "duration": 1.0,
                "logic": ">|<|>=|<=",
                "threshold": 100.0
            }
        ]
    }
    
    注意：如果所有评估项的 type 和 conditionLogic 都相同，它们会被提取到 statusEval 层级作为全局默认值。
    如果某个评估项需要不同的值，可以在该评估项中单独指定。
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
        else:
            # 创建临时配置文件
            report_id = str(uuid.uuid4())
            reports_dir = parent_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建临时目录用于存储配置文件
            temp_config_dir = reports_dir / report_id
            temp_config_dir.mkdir(parents=True, exist_ok=True)
            config_path = temp_config_dir / "config.json"
            
            # 构建配置
            # 提取全局默认值（从第一个评估项中提取，如果所有评估项都有相同的值）
            default_type = 'continuous_check'
            default_condition_logic = 'AND'
            
            if request.evaluations:
                first_type = request.evaluations[0].get('type')
                first_logic = request.evaluations[0].get('conditionLogic')
                
                # 检查是否所有评估项都有相同的type和conditionLogic
                all_same_type = all(eval_item.get('type', first_type) == first_type for eval_item in request.evaluations)
                all_same_logic = all(eval_item.get('conditionLogic', first_logic) == first_logic for eval_item in request.evaluations)
                
                if all_same_type and first_type:
                    default_type = first_type
                if all_same_logic and first_logic:
                    default_condition_logic = first_logic
            
            # 构建evaluations（移除type和conditionLogic，因为它们现在是全局的）
            evaluations_clean = []
            for eval_item in request.evaluations:
                eval_clean = {
                    'item': eval_item.get('item'),
                    'assessmentName': eval_item.get('assessmentName'),
                    'conditions': eval_item.get('conditions', [])
                }
                evaluations_clean.append(eval_clean)
            
            config = {
                "reportConfig": {
                    "statusEval": {
                        "type": default_type,
                        "conditionLogic": default_condition_logic,
                        "evaluations": evaluations_clean
                    }
                }
            }
            
            # 保存配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 3. 调用服务生成报表
        report_id = str(uuid.uuid4())
        reports_dir = parent_dir / "reports"
        report_file_path = reports_dir / f"status_evaluation_report-{report_id}.xlsx"
        
        service = StatusEvaluationService()
        report_path = service.generate_report(
            str(config_path),
            str(file_path),
            str(report_file_path)
        )
        
        # 4. 返回结果
        return StatusEvaluationResponse(
            report_id=report_id,
            message="状态评估报表生成成功",
            file_path=report_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成状态评估报表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成报表失败: {str(e)}")


@router.get("/reports/status_evaluation/{report_id}/download", summary="下载状态评估报表")
async def download_status_evaluation_report(report_id: str):
    """
    下载状态评估报表
    
    - **report_id**: 报表ID
    """
    try:
        reports_dir = parent_dir / "reports"
        report_file = reports_dir / f"status_evaluation_report-{report_id}.xlsx"
        
        if not report_file.exists():
            raise HTTPException(status_code=404, detail="报表文件不存在")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(report_file),
            filename=f"status_evaluation_report-{report_id}.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载报表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载报表失败: {str(e)}")

