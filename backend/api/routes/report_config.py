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
import json

import pandas as pd

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from enum import Enum
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# 配置状态枚举
class ConfigState(str, Enum):
    INITIAL = "initial"
    DISPLAY_CHANNELS = "display_channels"  # 选择展示通道（至少包含一个转速通道）
    SELECT_RPM_STANDARD = "select_rpm_standard"  # 选择转速通道作为判断标准
    TRIGGER_COMBO = "trigger_combo"        # 选择条件组合逻辑（仅用1/仅用2/AND）
    PARAMETER_CONFIG = "parameter_config"   # 微调参数
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
    file_id: Optional[str] = Field(default=None, description="上传文件ID，用于读取可选通道")

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
    
    def start_config(self, session_id: str, report_type: str, file_id: Optional[str] = None) -> ConfigResponse:
        """开始配置流程"""
        default_params = self.get_default_params(report_type)
        
        # 从上传文件中提取可用通道（仅稳态）
        if report_type == ReportType.STEADY_STATE and file_id:
            try:
                uploads_dir = Path(__file__).parent.parent.parent / "uploads"
                file_path = None
                for ext in [".csv", ".xlsx", ".xls"]:
                    candidate = uploads_dir / f"{file_id}{ext}"
                    if candidate.exists():
                        file_path = candidate
                        break
                if file_path is not None:
                    channels = self._extract_channels(str(file_path))
                    default_params['availableChannels'] = channels
                else:
                    default_params['availableChannels'] = ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
            except Exception as e:
                logger.warning(f"读取上传文件通道失败: {e}")
                default_params['availableChannels'] = ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
        elif report_type == ReportType.STEADY_STATE:
            default_params.setdefault('availableChannels', ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)'])
        
        # 如果提供了file_id，尝试从JSON文件中获取configFileName
        config_file_name = None
        if file_id:
            try:
                backend_dir = Path(__file__).resolve().parent.parent.parent
                config_dir = backend_dir / "config_sessions"
                for json_file in config_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                            if cfg.get("fileId") == file_id:
                                config_file_name = cfg.get("configFileName") or json_file.name
                                break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"读取configFileName失败: {e}")
        
        self.sessions[session_id] = {
            'state': ConfigState.DISPLAY_CHANNELS,
            'report_type': report_type,
            'params': default_params,
            'step': 0,
            'created_at': datetime.now(),
            'file_id': file_id,
            'config_file_name': config_file_name  # 保存JSON文件名，避免后续遍历所有文件
        }
        
        return ConfigResponse(
            session_id=session_id,
            state=ConfigState.DISPLAY_CHANNELS,
            message=self.get_step_message(report_type, ConfigState.DISPLAY_CHANNELS),
            suggested_actions=self.get_channel_options(report_type, default_params),
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
        if current_state == ConfigState.DISPLAY_CHANNELS:
            # 选择展示通道与完成通道选择
            selectable = params.get('availableChannels') or ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
            if action.startswith('选择 ') or action.startswith('使用 '):
                # 兼容“使用 xxx通道”与“选择 xxx”
                ch = action.replace('选择 ', '').replace('使用 ', '')
                if ch in selectable:
                    display = params.setdefault('displayChannels', [])
                    if ch not in display:
                        display.append(ch)
                # 留在本步骤，继续引导
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.DISPLAY_CHANNELS,
                    message=f"已选择展示通道：{params.get('displayChannels', [])}\n\n您可以继续选择其它通道，或点击‘完成通道选择’。要求：至少包含一个转速通道（含 rpm）。",
                    suggested_actions=self.get_channel_options(report_type, params),
                    current_params=params
                )
            elif action in ['完成通道选择', '完成选择']:
                display = params.get('displayChannels', []) or []
                # 判断是否包含转速通道：名称包含rpm、Ng或Np（不区分大小写）
                has_rpm = any('rpm' in c.lower() or c.lower() in ['ng', 'np'] or c.lower().startswith('ng') or c.lower().startswith('np') for c in display)
                if not has_rpm:
                    # 未满足强约束，不允许进入下一步
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.DISPLAY_CHANNELS,
                        message="必须至少选择一个转速通道（名称包含 rpm）。请继续选择后再完成。",
                        suggested_actions=self.get_channel_options(report_type, params),
                        current_params=params
                    )
                # 设置默认条件一/二
                params.setdefault('triggerLogic', {})
                params['triggerLogic'] = {
                    'combination': 'AND',
                    'condition1': {
                        'enabled': True,
                        'channel': next((c for c in display if 'ng' in c.lower() or 'np' in c.lower() or 'rpm' in c.lower()), 'Ng(rpm)'),
                        'statistic': '平均值',
                        'duration_sec': 1,
                        'logic': '>',
                        'threshold': 10000
                    },
                    'condition2': {
                        'enabled': True,
                        'channel': next((c for c in display if 'ng' in c.lower() or 'np' in c.lower() or 'rpm' in c.lower()), 'Ng(rpm)'),
                        'statistic': '变化率',
                        'duration_sec': 10,
                        'logic': '<',
                        'threshold': 100
                    }
                }
                # 提取已选择的转速通道，进入选择判断标准状态
                # 匹配规则：包含rpm、或者名称是Ng/Np、或者以Ng/Np开头
                rpm_channels = [c for c in display if 'rpm' in c.lower() or c.lower() == 'ng' or c.lower() == 'np' or c.lower().startswith('ng') or c.lower().startswith('np')]
                params['availableRpmChannels'] = rpm_channels
                
                # 保存displayChannels到JSON文件（必须执行，不能因为异常而跳过）
                print(f"[DEBUG] ========== 准备保存displayChannels ==========")
                print(f"[DEBUG] display: {display}")
                print(f"[DEBUG] session['file_id']: {session.get('file_id')}")
                print(f"[DEBUG] params['displayChannels']: {params.get('displayChannels')}")
                self._save_display_channels_to_json(session, params)
                print(f"[DEBUG] ========== 保存displayChannels调用完成 ==========")
                
                session['state'] = ConfigState.SELECT_RPM_STANDARD
                
                # 构建建议操作，确保rpm_channels不为空
                suggested_actions = []
                if rpm_channels:
                    suggested_actions = [f"选择 {ch}" for ch in rpm_channels]
                suggested_actions.append('返回修改通道')
                
                print(f"[DEBUG] 准备返回ConfigResponse:")
                print(f"[DEBUG]   state: {ConfigState.SELECT_RPM_STANDARD}")
                print(f"[DEBUG]   rpm_channels: {rpm_channels}")
                print(f"[DEBUG]   suggested_actions: {suggested_actions}")
                print(f"[DEBUG]   params keys: {list(params.keys())}")
                
                try:
                    response = ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.SELECT_RPM_STANDARD,
                        message="请选择哪个转速通道作为判断标准：",
                        suggested_actions=suggested_actions,
                        current_params=params
                    )
                    print(f"[DEBUG] ConfigResponse创建成功")
                    return response
                except Exception as resp_err:
                    print(f"[ERROR] ConfigResponse创建失败: {resp_err}")
                    import traceback
                    traceback.print_exc()
                    raise
            
        elif current_state == ConfigState.SELECT_RPM_STANDARD:
            # 选择转速通道作为判断标准
            rpm_channels = params.get('availableRpmChannels', [])
            selected_rpm = None
            if action.startswith('选择 '):
                channel_name = action.replace('选择 ', '')
                if channel_name in rpm_channels:
                    params['rpmStandardChannel'] = channel_name
                    selected_rpm = channel_name
                
                # 设置默认条件一/二，使用选定的转速通道
                params.setdefault('triggerLogic', {})
                params['triggerLogic'] = {
                    'combination': 'AND',
                    'condition1': {
                        'enabled': True,
                        'channel': selected_rpm or rpm_channels[0],
                        'statistic': '平均值',
                        'duration_sec': 1,
                        'logic': '>',
                        'threshold': 10000
                    },
                    'condition2': {
                        'enabled': True,
                        'channel': selected_rpm or rpm_channels[0],
                        'statistic': '变化率',
                        'duration_sec': 10,
                        'logic': '<',
                        'threshold': 100
                    }
                }
                session['state'] = ConfigState.TRIGGER_COMBO
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.TRIGGER_COMBO,
                    message=(
                        f"已选择 {selected_rpm or rpm_channels[0]} 作为判断标准。\n\n"
                        f"已为您填充默认条件一/二：\n"
                        f"条件一：{params['triggerLogic']['condition1']}\n"
                        f"条件二：{params['triggerLogic']['condition2']}\n\n"
                        "请选择组合逻辑：仅用条件一 / 仅用条件二 / AND。"
                    ),
                    suggested_actions=['仅用条件一', '仅用条件二', 'AND', '返回修改通道'],
                    current_params=params
                )
            elif action == '返回修改通道':
                session['state'] = ConfigState.DISPLAY_CHANNELS
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.DISPLAY_CHANNELS,
                    message=self.get_step_message(report_type, ConfigState.DISPLAY_CHANNELS),
                    suggested_actions=self.get_channel_options(report_type, params),
                    current_params=params
                )
            
        elif current_state == ConfigState.TRIGGER_COMBO:
            if action in ['仅用条件一', '仅用条件二', 'AND']:
                comb_map = {
                    '仅用条件一': 'Cond1_Only',
                    '仅用条件二': 'Cond2_Only',
                    'AND': 'AND'
                }
                params.setdefault('triggerLogic', {})['combination'] = comb_map[action]
                session['state'] = ConfigState.PARAMETER_CONFIG
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=self.get_step_message(report_type, ConfigState.PARAMETER_CONFIG),
                    suggested_actions=self.get_parameter_options(report_type),
                    current_params=params
                )
            elif action == '返回修改通道':
                session['state'] = ConfigState.DISPLAY_CHANNELS
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.DISPLAY_CHANNELS,
                    message=self.get_step_message(report_type, ConfigState.DISPLAY_CHANNELS),
                    suggested_actions=self.get_channel_options(report_type),
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
                # 持久化配置到 backend/config_sessions/{file_id}.json（如果上传时已创建则更新，否则创建新文件）
                try:
                    backend_dir = Path(__file__).resolve().parent.parent.parent  # backend 目录
                    out_dir = backend_dir / "config_sessions"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 通过file_id查找对应的JSON文件（文件名是时间戳格式）
                    file_id = session.get('file_id')
                    out_path = None
                    existing_config = {}
                    
                    if file_id:
                        # 查找所有JSON文件，找到fileId匹配的
                        for json_file in out_dir.glob("*.json"):
                            try:
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    cfg = json.load(f)
                                    if cfg.get("fileId") == file_id:
                                        out_path = json_file
                                        existing_config = cfg
                                        break
                            except Exception:
                                continue
                    
                    # 如果没找到，创建一个新的（使用时间戳格式，包含毫秒）
                    if out_path is None:
                        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # 包含毫秒
                        out_path = out_dir / f"{timestamp_str}.json"
                        existing_config = {}
                    
                    # 读取现有配置（如果找到但还没读取）
                    if out_path.exists() and not existing_config:
                        try:
                            with open(out_path, 'r', encoding='utf-8') as f:
                                existing_config = json.load(f)
                        except Exception as read_err:
                            logger.warning(f"读取已有配置文件失败: {read_err}")
                    
                    # 构建稳态配置
                    steady_cfg = self._build_steady_state_config(params)
                    
                    # 合并配置：保留已有信息（sourceFileId, fileId, uploadTime, channels），更新reportConfig
                    final_config = {
                        **existing_config,  # 保留已有字段
                        "reportConfig": steady_cfg.get("reportConfig", {})
                    }
                    # 如果没有sourceFileId等字段，则添加
                    if "sourceFileId" not in final_config:
                        final_config["sourceFileId"] = existing_config.get("sourceFileId", "")
                    if "fileId" not in final_config:
                        final_config["fileId"] = file_id
                    if "uploadTime" not in final_config:
                        final_config["uploadTime"] = existing_config.get("uploadTime", datetime.now().isoformat())
                    if "channels" not in final_config:
                        final_config["channels"] = existing_config.get("channels", [])
                    
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(final_config, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"已保存配置到: {out_path}")
                    print(f"[DEBUG] 已保存配置到: {out_path.absolute()}")
                except Exception as e:
                    logger.error(f"保存稳态配置失败: {e}", exc_info=True)
                    print(f"[ERROR] 保存稳态配置失败: {e}")
                    import traceback
                    traceback.print_exc()
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
            suggested_actions=self.get_current_actions(current_state, report_type, params),
            current_params=params
        )
    
    def get_default_params(self, report_type: str) -> Dict[str, Any]:
        """获取默认参数"""
        if report_type == ReportType.STEADY_STATE:
            return {
                'displayChannels': [],
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
            if state == ConfigState.DISPLAY_CHANNELS:
                return "稳态分析配置 - 第1步：选择展示通道\n\n请从检测到的通道中选择需要展示的通道，且至少包含一个转速通道（含 rpm）。选择完成后点击‘完成通道选择’。"
            elif state == ConfigState.TRIGGER_COMBO:
                return "稳态分析配置 - 第2步：选择组合逻辑\n\n系统已为您填充默认条件一/条件二，请选择使用方式：仅用条件一 / 仅用条件二 / AND。"
            elif state == ConfigState.PARAMETER_CONFIG:
                return "稳态分析配置 - 第3步：配置参数\n\n您可以修改统计方法、阈值或时间窗口，或直接确认配置。"
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
    
    def get_channel_options(self, report_type: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """获取通道选择选项"""
        if report_type == ReportType.STEADY_STATE:
            channels = (params or {}).get('availableChannels') or ['Ng(rpm)', 'Np(rpm)', 'Temperature(°C)', 'Pressure(kPa)']
            actions = [f"选择 {c}" for c in channels]
            actions.extend(['完成通道选择', '取消配置'])
            return actions
        return ['取消配置']
    
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
    
    def get_current_actions(self, state: ConfigState, report_type: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """获取当前状态的操作选项"""
        if state == ConfigState.DISPLAY_CHANNELS:
            return self.get_channel_options(report_type, params)
        elif state == ConfigState.SELECT_RPM_STANDARD:
            # 只显示已选择的转速通道
            rpm_channels = (params or {}).get('availableRpmChannels', [])
            actions = [f"选择 {ch}" for ch in rpm_channels]
            actions.append('返回修改通道')
            return actions
        elif state == ConfigState.TRIGGER_COMBO:
            return ['仅用条件一', '仅用条件二', 'AND', '返回修改通道']
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

展示通道：{params.get('displayChannels', [])}
组合逻辑：{params.get('triggerLogic', {}).get('combination', 'AND')}
条件一：{params.get('triggerLogic', {}).get('condition1')}
条件二：{params.get('triggerLogic', {}).get('condition2')}
时间窗口：{params.get('time_window', 10)}秒

请确认是否使用以上配置生成报表？"""
        else:
            return f"配置确认：\n\n{params}\n\n请确认是否使用以上配置生成报表？"

    def _save_display_channels_to_json(self, session: Dict[str, Any], params: Dict[str, Any]) -> None:
        """保存displayChannels到JSON文件"""
        file_id = session.get('file_id')
        config_file_name = session.get('config_file_name')  # 从session中直接获取文件名
        display_channels = params.get('displayChannels', [])
        
        print(f"[DEBUG] ====== 开始保存displayChannels ======")
        print(f"[DEBUG] file_id={file_id}")
        print(f"[DEBUG] config_file_name={config_file_name}")
        print(f"[DEBUG] displayChannels={display_channels}")
        
        if not file_id:
            error_msg = "session中没有file_id，无法保存displayChannels到JSON"
            logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            return
        
        try:
            backend_dir = Path(__file__).resolve().parent.parent.parent
            config_dir = backend_dir / "config_sessions"
            
            print(f"[DEBUG] backend_dir: {backend_dir}")
            print(f"[DEBUG] config_dir: {config_dir}")
            print(f"[DEBUG] config_dir.exists(): {config_dir.exists()}")
            
            # 优先使用session中保存的config_file_name，避免遍历所有文件
            config_file_name = session.get('config_file_name')
            if config_file_name:
                config_path = config_dir / config_file_name
                if config_path.exists():
                    print(f"[DEBUG] 使用session中的config_file_name: {config_file_name}（无需遍历文件）")
                else:
                    print(f"[WARNING] session中的config_file_name对应的文件不存在: {config_file_name}，将尝试查找")
                    config_path = None
            else:
                config_path = None
            
            # 如果config_file_name不可用，才遍历文件查找（向后兼容）
            if not config_path:
                print(f"[DEBUG] 遍历JSON文件查找fileId={file_id}...")
                all_json_files = list(config_dir.glob("*.json"))
                print(f"[DEBUG] 找到 {len(all_json_files)} 个JSON文件")
                for json_file in all_json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                            if cfg.get("fileId") == file_id:
                                config_path = json_file
                                # 保存到session中，下次直接使用
                                session['config_file_name'] = json_file.name
                                print(f"[DEBUG] 找到匹配文件: {json_file.name}，已保存到session")
                                break
                    except Exception:
                        continue
            
            if not config_path:
                error_msg = f"找不到fileId={file_id}对应的JSON文件"
                logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
                return
            
            print(f"[DEBUG] 找到匹配的JSON文件: {config_path}")
            
            # 读取现有配置
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"[DEBUG] 读取的config结构: reportConfig={'reportConfig' in config}, steadyState={'steadyState' in config.get('reportConfig', {})}")
            
            # 更新displayChannels
            if 'reportConfig' not in config:
                config['reportConfig'] = {}
            if 'steadyState' not in config['reportConfig']:
                config['reportConfig']['steadyState'] = {}
            
            config['reportConfig']['steadyState']['displayChannels'] = display_channels
            
            print(f"[DEBUG] 准备写入: {config['reportConfig']['steadyState']}")
            
            # 保存回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 验证保存是否成功
            with open(config_path, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                saved_channels = saved_config.get('reportConfig', {}).get('steadyState', {}).get('displayChannels', [])
                print(f"[DEBUG] 验证保存: {saved_channels}")
                if saved_channels == display_channels:
                    print(f"[SUCCESS] ✓ displayChannels已成功保存到: {config_path}")
                    logger.info(f"已保存displayChannels到JSON文件: {config_path}")
                else:
                    print(f"[ERROR] ✗ 保存验证失败! 期望: {display_channels}, 实际: {saved_channels}")
                    
        except Exception as e:
            logger.error(f"保存displayChannels到JSON文件失败: {e}", exc_info=True)
            print(f"[ERROR] 保存displayChannels失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"[DEBUG] ====== 保存displayChannels完成 ======")

    def _extract_channels(self, file_path: str) -> List[str]:
        """从上传文件读取列名作为通道，排除常见时间列"""
        suffix = Path(file_path).suffix.lower()
        if suffix == '.csv':
            df = pd.read_csv(file_path, nrows=1)
        else:
            df = pd.read_excel(file_path, nrows=1)
        time_columns = {'time', 'time[s]', 'timestamp', '时间', 'Time', 'Time[s]', 'Timestamp'}
        channels = [col for col in df.columns if str(col).strip() not in time_columns]
        return channels

    def _build_steady_state_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建稳态配置JSON，供后续计算模块使用"""
        trigger = params.get('triggerLogic', {})
        conditions: List[Dict[str, Any]] = []
        if trigger.get('condition1', {}).get('enabled', True):
            conditions.append({
                "type": "statistic",
                "channel": trigger.get('condition1', {}).get('channel'),
                "statistic": trigger.get('condition1', {}).get('statistic', '平均值'),
                "duration": trigger.get('condition1', {}).get('duration_sec', 1),
                "logic": trigger.get('condition1', {}).get('logic', '>'),
                "threshold": trigger.get('condition1', {}).get('threshold', 0)
            })
        if trigger.get('condition2', {}).get('enabled', True):
            conditions.append({
                "type": "amplitude_change",
                "channel": trigger.get('condition2', {}).get('channel'),
                "duration": trigger.get('condition2', {}).get('duration_sec', 10),
                "logic": trigger.get('condition2', {}).get('logic', '<'),
                "threshold": trigger.get('condition2', {}).get('threshold', 0)
            })
        return {
            "reportConfig": {
                "stableState": {
                    "displayChannels": params.get('displayChannels', []),
                    "conditionLogic": trigger.get('combination', 'AND'),
                    "conditions": conditions
                }
            }
        }

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
        return config_manager.start_config(request.session_id, request.report_type, getattr(request, 'file_id', None))
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
            suggested_actions=config_manager.get_current_actions(session['state'], session['report_type'], session.get('params')),
            current_params=session['params']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
