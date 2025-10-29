"""
配置对话API接口 - 支持自然语言配置
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import time

# 导入服务
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.config_manager import config_manager, ConfigStatus
from backend.services.config_dialogue_parser import config_parser

logger = logging.getLogger(__name__)

router = APIRouter()

# 请求/响应模型
class StartConfigRequest(BaseModel):
    """开始配置请求"""
    report_type: str = Field(..., description="报表类型")
    user_id: str = Field(..., description="用户ID")
    file_id: Optional[str] = Field(default=None, description="上传文件ID，用于读取可选通道")

class StartConfigResponse(BaseModel):
    """开始配置响应"""
    session_id: str
    config: Dict[str, Any]
    status: str
    message: str
    suggested_actions: Optional[list] = None

class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    session_id: str = Field(..., description="会话ID")
    user_input: str = Field(..., description="用户输入文本")

class UpdateConfigResponse(BaseModel):
    """更新配置响应"""
    success: bool
    message: str
    config: Dict[str, Any]
    status: str
    suggested_actions: Optional[list] = None

class CompleteConfigRequest(BaseModel):
    """完成配置请求"""
    session_id: str = Field(..., description="会话ID")

class CompleteConfigResponse(BaseModel):
    """完成配置响应"""
    success: bool
    message: str
    config: Dict[str, Any]
    status: str

class CancelConfigRequest(BaseModel):
    """取消配置请求"""
    session_id: str = Field(..., description="会话ID")

class CancelConfigResponse(BaseModel):
    """取消配置响应"""
    success: bool
    message: str

class ConfigStatusResponse(BaseModel):
    """配置状态响应"""
    isConfiguring: bool
    reportType: Optional[str] = None
    sessionId: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

@router.post("/start-config", response_model=StartConfigResponse, summary="开始配置对话")
async def start_config_dialogue(request: StartConfigRequest):
    """
    开始配置对话会话
    
    用户点击报表按钮后，系统进入配置模式，支持通过自然语言对话配置参数
    对于steady_state类型，使用状态驱动的ReportConfigManager
    """
    try:
        # 对于steady_state，使用状态驱动的ReportConfigManager
        if request.report_type == "steady_state":
            # 延迟导入避免循环导入
            from backend.api.routes.report_config import config_manager as report_config_manager
            session_id = f"{request.user_id}_{request.report_type}_{int(time.time())}"
            config_response = report_config_manager.start_config(session_id, request.report_type, request.file_id)
            
            return StartConfigResponse(
                session_id=config_response.session_id,
                config=config_response.current_params,
                status=config_response.state,
                message=config_response.message,
                suggested_actions=config_response.suggested_actions
            )
        else:
            # 其他类型使用旧的ConfigManager
            session_info = await config_manager.start_config_session(
                report_type=request.report_type,
                user_id=request.user_id
            )
            return StartConfigResponse(**session_info)
        
    except Exception as e:
        logger.error(f"开始配置对话失败: {e}")
        raise HTTPException(status_code=500, detail=f"开始配置失败: {str(e)}")

@router.post("/update-config", response_model=UpdateConfigResponse, summary="更新配置参数")
async def update_config_dialogue(request: UpdateConfigRequest):
    """
    通过自然语言更新配置参数
    
    支持自然语言表达，如：
    - "使用转速通道" → 转速通道 = true
    - "阈值改成15000" → 阈值 = 15000
    - "使用平均值" → 统计方法 = 平均值
    - "完成通道选择" → 状态驱动操作
    """
    try:
        # 延迟导入避免循环导入
        from backend.api.routes.report_config import config_manager as report_config_manager
        
        # 先检查是否在ReportConfigManager中（状态驱动配置）
        if request.session_id in report_config_manager.sessions:
            # 使用状态驱动的ReportConfigManager
            try:
                config_response = report_config_manager.update_config(
                    request.session_id,
                    request.user_input,
                    None
                )
                return UpdateConfigResponse(
                    success=True,
                    message=config_response.message,
                    config=config_response.current_params,
                    status=config_response.state,
                    suggested_actions=config_response.suggested_actions or []
                )
            except ValueError as ve:
                raise HTTPException(status_code=404, detail=str(ve))
            except Exception as e:
                logger.error(f"ReportConfigManager更新失败: {e}", exc_info=True)
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")
        
        # 否则使用旧的ConfigManager
        session = config_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="配置会话不存在")
        
        # 混合解析用户输入
        parsed_action = config_parser.parse_user_intent(
            request.user_input, 
            session["config"]
        )
        
        if parsed_action:
            if parsed_action["action"] == "update":
                # 更新配置参数
                updates = {parsed_action["field"]: parsed_action["value"]}
                config_response = await config_manager.update_config(
                    session_id=request.session_id,
                    updates=updates
                )
                
                return UpdateConfigResponse(
                    success=True,
                    message=parsed_action.get("message", "配置已更新"),
                    config=config_response["config"],
                    status=config_response["status"],
                    suggested_actions=config_parser.get_suggested_actions(
                        str(config_response["status"]).lower(), 
                        config_response["config"]
                    )
                )
            
            elif parsed_action["action"] == "confirm":
                # 确认配置
                complete_response = await config_manager.complete_config(request.session_id)
                return UpdateConfigResponse(
                    success=True,
                    message=parsed_action["message"],
                    config=complete_response["config"],
                    status=complete_response["status"],
                    suggested_actions=config_parser.get_suggested_actions(
                        str(complete_response["status"]).lower(),
                        complete_response["config"]
                    )
                )
            
            elif parsed_action["action"] == "cancel":
                # 取消配置
                cancel_response = await config_manager.cancel_config(request.session_id)
                return UpdateConfigResponse(
                    success=True,
                    message=parsed_action["message"],
                    config=cancel_response["config"],
                    status=cancel_response["status"],
                    suggested_actions=config_parser.get_suggested_actions(
                        str(cancel_response["status"]).lower(),
                        cancel_response["config"]
                    )
                )
            
            elif parsed_action["action"] == "reset":
                # 重置配置
                session = config_manager.get_session(request.session_id)
                if session:
                    default_config = config_manager.get_default_config(session["report_type"])
                    await config_manager.update_config(
                        session_id=request.session_id,
                        updates=default_config
                    )
                    return UpdateConfigResponse(
                        success=True,
                        message=parsed_action["message"],
                        config=default_config,
                        status=ConfigStatus.CONFIGURING,
                        suggested_actions=config_parser.get_suggested_actions(
                            str(ConfigStatus.CONFIGURING).lower(),
                            default_config
                        )
                    )
        
        else:
            # 解析失败，提供帮助信息
            return UpdateConfigResponse(
                success=False,
                message="抱歉，我没有理解您的意思。您可以尝试说：\n- '使用转速通道'\n- '阈值改成15000'\n- '使用平均值'\n- '确认配置'",
                config=session["config"],
                status=session["status"],
                suggested_actions=config_parser.get_suggested_actions(
                    str(session["status"]).lower(), 
                    session["config"]
                )
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@router.post("/complete-config", response_model=CompleteConfigResponse, summary="完成配置")
async def complete_config_dialogue(request: CompleteConfigRequest):
    """
    完成配置对话
    
    第一次点击：进入确认状态
    第二次点击：真正完成配置，开始生成报表
    """
    try:
        config_response = await config_manager.complete_config(request.session_id)
        
        return CompleteConfigResponse(
            success=True,
            message=config_response["message"],
            config=config_response["config"],
            status=config_response["status"]
        )
        
    except Exception as e:
        logger.error(f"完成配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"完成配置失败: {str(e)}")

@router.post("/cancel-config", response_model=CancelConfigResponse, summary="取消配置")
async def cancel_config_dialogue(request: CancelConfigRequest):
    """
    取消配置对话
    """
    try:
        config_response = await config_manager.cancel_config(request.session_id)
        
        return CancelConfigResponse(
            success=True,
            message=config_response["message"]
        )
        
    except Exception as e:
        logger.error(f"取消配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消配置失败: {str(e)}")

@router.get("/config-status", response_model=ConfigStatusResponse, summary="获取配置状态")
async def get_config_status(user_id: Optional[str] = None):
    """
    获取当前配置状态
    
    用于前端轮询检查是否有活跃的配置会话
    """
    try:
        active_session = config_manager.get_active_session(user_id)
        
        if active_session:
            return ConfigStatusResponse(
                isConfiguring=True,
                reportType=active_session["report_type"],
                sessionId=active_session["session_id"],
                config=active_session["config"],
                status=active_session["status"]
            )
        else:
            return ConfigStatusResponse(isConfiguring=False)
            
    except Exception as e:
        logger.error(f"获取配置状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置状态失败: {str(e)}")

@router.get("/config-history/{session_id}", summary="获取配置历史")
async def get_config_history(session_id: str):
    """
    获取配置历史记录
    
    用于调试和审计
    """
    try:
        history = config_manager.get_config_history(session_id)
        return {"session_id": session_id, "history": history}
        
    except Exception as e:
        logger.error(f"获取配置历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置历史失败: {str(e)}")

@router.get("/debug/sessions", summary="获取所有会话（调试用）")
async def get_all_sessions():
    """
    获取所有会话信息（仅用于调试）
    """
    try:
        sessions = config_manager.get_all_sessions()
        return {"sessions": sessions}
        
    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话信息失败: {str(e)}")
