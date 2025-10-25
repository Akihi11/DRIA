"""
报表配置管理API - 状态驱动的配置流程
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import sys
from pathlib import Path
import logging

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from enum import Enum
from pydantic import BaseModel, Field

router = APIRouter()

# 配置状态枚举
class ConfigState(str, Enum):
    INITIAL = "initial"
    CHANNEL_SELECTION = "channel_selection"
    PARAMETER_CONFIG = "parameter_config"
    CONFIRMATION = "confirmation"
    GENERATING = "generating"
    COMPLETED = "completed"

# 报表类型枚举
class ReportType(str, Enum):
    STEADY_STATE = "steady_state"
    FUNCTION_CALC = "function_calc"
    STATUS_EVAL = "status_eval"
    COMPLETE = "complete"

# 请求/响应模型
class ConfigStartRequest(BaseModel):
    session_id: str
    report_type: str

class ConfigUpdateRequest(BaseModel):
    session_id: str
    action: str
    value: Optional[Any] = None

class ConfigResponse(BaseModel):
    session_id: str
    state: ConfigState
    message: str
    suggested_actions: List[str]
    current_params: Dict[str, Any]
    is_complete: bool = False

# 配置管理器
class ReportConfigManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    def start_config(self, session_id: str, report_type: str) -> ConfigResponse:
        """开始配置流程"""
        default_params = self.get_default_params(report_type)
        
        self.sessions[session_id] = {
            'state': ConfigState.CHANNEL_SELECTION,
            'report_type': report_type,
            'params': default_params,
            'step': 0,
            'created_at': datetime.now()
        }
        
        return ConfigResponse(
            session_id=session_id,
            state=ConfigState.CHANNEL_SELECTION,
            message=self.get_step_message(report_type, ConfigState.CHANNEL_SELECTION),
            suggested_actions=self.get_channel_options(),
            current_params=default_params
        )
    
    def update_config(self, session_id: str, action: str, value: Any = None) -> ConfigResponse:
        """更新配置"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")
        
        current_state = session['state']
        report_type = session['report_type']
        params = session['params']
        
        # 根据当前状态和操作更新配置
        if current_state == ConfigState.CHANNEL_SELECTION:
            if action in ['使用 Ng(rpm)', '使用 Temperature(°C)', '使用 Pressure(kPa)']:
                channel_map = {
                    '使用 Ng(rpm)': 'Ng(rpm)',
                    '使用 Temperature(°C)': 'Temperature(°C)',
                    '使用 Pressure(kPa)': 'Pressure(kPa)'
                }
                params['channel'] = channel_map[action]
                session['state'] = ConfigState.PARAMETER_CONFIG
                
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=self.get_step_message(report_type, ConfigState.PARAMETER_CONFIG),
                    suggested_actions=self.get_parameter_options(report_type),
                    current_params=params
                )
        
        elif current_state == ConfigState.PARAMETER_CONFIG:
            if action == '修改统计方法':
                params['statistic'] = value or '平均值'
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=f"已更新统计方法为 {params['statistic']}。还有其他参数需要修改吗？",
                    suggested_actions=self.get_parameter_options(report_type),
                    current_params=params
                )
            elif action == '修改阈值':
                if value:
                    params['threshold'] = value
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=f"已更新阈值为 {params['threshold']}。还有其他参数需要修改吗？",
                    suggested_actions=self.get_parameter_options(report_type),
                    current_params=params
                )
            elif action == '确认配置':
                session['state'] = ConfigState.CONFIRMATION
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.CONFIRMATION,
                    message=self.get_confirmation_message(report_type, params),
                    suggested_actions=['确认生成', '修改配置', '取消配置'],
                    current_params=params
                )
        
        elif current_state == ConfigState.CONFIRMATION:
            if action == '确认生成':
                session['state'] = ConfigState.GENERATING
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.GENERATING,
                    message="正在生成报表，请稍候...",
                    suggested_actions=[],
                    current_params=params,
                    is_complete=True
                )
            elif action == '修改配置':
                session['state'] = ConfigState.PARAMETER_CONFIG
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message="请修改配置参数：",
                    suggested_actions=self.get_parameter_options(report_type),
                    current_params=params
                )
            elif action == '取消配置':
                del self.sessions[session_id]
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.INITIAL,
                    message="配置已取消，回到对话模式。",
                    suggested_actions=[],
                    current_params={}
                )
        
        # 默认返回当前状态
        return ConfigResponse(
            session_id=session_id,
            state=current_state,
            message="请选择下一步操作：",
            suggested_actions=self.get_current_actions(current_state, report_type),
            current_params=params
        )
    
    def get_default_params(self, report_type: str) -> Dict[str, Any]:
        """获取默认参数"""
        if report_type == ReportType.STEADY_STATE:
            return {
                'channel': 'Ng(rpm)',
                'statistic': '平均值',
                'duration': 0.1,
                'logic': '>',
                'threshold': 14000,
                'time_window': 10
            }
        elif report_type == ReportType.FUNCTION_CALC:
            return {
                'metrics': ['time_baseline', 'startup_time', 'acceleration_time'],
                'channels': ['Ng(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
            }
        elif report_type == ReportType.STATUS_EVAL:
            return {
                'projects': ['overtemp_detection', 'ng_residual_rotation', 'vibration_analysis'],
                'thresholds': {
                    'temperature': 200,
                    'ng_residual': 50,
                    'vibration': 0.5
                }
            }
        else:
            return {}
    
    def get_step_message(self, report_type: str, state: ConfigState) -> str:
        """获取步骤消息"""
        if report_type == ReportType.STEADY_STATE:
            if state == ConfigState.CHANNEL_SELECTION:
                return "稳态分析配置 - 第1步：选择主要通道\n\n请选择用于判断稳定状态的主要通道："
            elif state == ConfigState.PARAMETER_CONFIG:
                return "稳态分析配置 - 第2步：配置参数\n\n请选择您要修改的参数："
        elif report_type == ReportType.FUNCTION_CALC:
            if state == ConfigState.CHANNEL_SELECTION:
                return "功能计算配置 - 第1步：选择计算指标\n\n请选择需要计算的指标："
            elif state == ConfigState.PARAMETER_CONFIG:
                return "功能计算配置 - 第2步：配置参数\n\n请选择您要修改的参数："
        elif report_type == ReportType.STATUS_EVAL:
            if state == ConfigState.CHANNEL_SELECTION:
                return "状态评估配置 - 第1步：选择评估项目\n\n请选择需要评估的项目："
            elif state == ConfigState.PARAMETER_CONFIG:
                return "状态评估配置 - 第2步：配置参数\n\n请选择您要修改的参数："
        
        return "请选择下一步操作："
    
    def get_channel_options(self) -> List[str]:
        """获取通道选择选项"""
        return ['使用 Ng(rpm)', '使用 Temperature(°C)', '使用 Pressure(kPa)', '自定义通道']
    
    def get_parameter_options(self, report_type: str) -> List[str]:
        """获取参数配置选项"""
        if report_type == ReportType.STEADY_STATE:
            return ['修改统计方法', '修改阈值', '修改时间窗口', '确认配置', '取消配置']
        elif report_type == ReportType.FUNCTION_CALC:
            return ['修改指标', '修改通道', '确认配置', '取消配置']
        elif report_type == ReportType.STATUS_EVAL:
            return ['修改项目', '修改阈值', '确认配置', '取消配置']
        else:
            return ['确认配置', '取消配置']
    
    def get_current_actions(self, state: ConfigState, report_type: str) -> List[str]:
        """获取当前状态的操作选项"""
        if state == ConfigState.CHANNEL_SELECTION:
            return self.get_channel_options()
        elif state == ConfigState.PARAMETER_CONFIG:
            return self.get_parameter_options(report_type)
        elif state == ConfigState.CONFIRMATION:
            return ['确认生成', '修改配置', '取消配置']
        else:
            return []
    
    def get_confirmation_message(self, report_type: str, params: Dict[str, Any]) -> str:
        """获取确认消息"""
        if report_type == ReportType.STEADY_STATE:
            return f"""配置确认：

主要通道：{params.get('channel', 'Ng(rpm)')}
统计方法：{params.get('statistic', '平均值')}
持续时间：{params.get('duration', 0.1)}秒
判断逻辑：{params.get('logic', '>')}
阈值：{params.get('threshold', 14000)}
时间窗口：{params.get('time_window', 10)}秒

请确认是否使用以上配置生成报表？"""
        else:
            return f"配置确认：\n\n{params}\n\n请确认是否使用以上配置生成报表？"

# 全局配置管理器实例
config_manager = ReportConfigManager()

@router.post("/report_config/start", response_model=ConfigResponse, summary="开始报表配置")
async def start_report_config(request: ConfigStartRequest):
    """
    开始报表配置流程
    
    - **session_id**: 会话ID
    - **report_type**: 报表类型 (steady_state/function_calc/status_eval/complete)
    """
    try:
        return config_manager.start_config(request.session_id, request.report_type)
    except Exception as e:
        logger.error(f"Start config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/report_config/update", response_model=ConfigResponse, summary="更新报表配置")
async def update_report_config(request: ConfigUpdateRequest):
    """
    更新报表配置
    
    - **session_id**: 会话ID
    - **action**: 操作类型
    - **value**: 操作值（可选）
    """
    try:
        return config_manager.update_config(request.session_id, request.action, request.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Update config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report_config/status/{session_id}", response_model=ConfigResponse, summary="获取配置状态")
async def get_config_status(session_id: str):
    """
    获取当前配置状态
    
    - **session_id**: 会话ID
    """
    try:
        session = config_manager.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return ConfigResponse(
            session_id=session_id,
            state=session['state'],
            message="当前配置状态",
            suggested_actions=config_manager.get_current_actions(session['state'], session['report_type']),
            current_params=session['params']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
