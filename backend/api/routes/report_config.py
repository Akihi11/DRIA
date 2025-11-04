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
import os
import re

import pandas as pd

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from enum import Enum
from pydantic import BaseModel, Field

import backend.llm
from backend.llm import LLMClient, LLMConfig, ModelProvider, Message
from backend.config import settings
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# 配置状态枚举
class ConfigState(str, Enum):
    INITIAL = "initial"
    DISPLAY_CHANNELS = "display_channels"  # 选择展示通道
    TRIGGER_COMBO = "trigger_combo"        # 选择条件组合逻辑（仅用1/仅用2/AND）
    PARAMETER_CONFIG = "parameter_config"   # 微调参数
    SELECT_JUDGE_CHANNEL = "select_judge_channel"  # 选择判断通道（通过自然语言）
    TIME_BASE_CONFIG = "time_base_config"  # 功能计算：时间（基准时刻）配置
    STARTUP_TIME_CONFIG = "startup_time_config"  # 功能计算：启动时间配置
    IGNITION_TIME_CONFIG = "ignition_time_config"  # 功能计算：点火时间配置
    RUNDOWN_NG_CONFIG = "rundown_ng_config"  # 功能计算：Ng余转时间配置
    RUNDOWN_NP_CONFIG = "rundown_np_config"  # 功能计算：Np余转时间配置
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
    action: str = ""
    value: Optional[Any] = None
    utterance: Optional[str] = Field(default=None, description="自然语言配置指令", example="把条件一阈值调9000，统计法最大值")

class ConfigResponse(BaseModel):
    session_id: str
    state: ConfigState
    message: str
    suggested_actions: List[str]
    current_params: Dict[str, Any]
    is_complete: bool = False
    parsed_by_llm: bool = Field(default=False, description="是否由大模型解析")
    error_message: Optional[str] = Field(default=None, description="错误信息（如果有）")

# 配置管理器
class ReportConfigManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    @staticmethod
    def format_condition_description(condition: Dict[str, Any]) -> str:
        """将条件对象转换为一句完整的自然语言描述"""
        if not condition:
            return ""
        
        channel = condition.get('channel', '')
        statistic = condition.get('statistic', '')
        duration_sec = condition.get('duration_sec', 1)
        logic = condition.get('logic', '')
        threshold = condition.get('threshold', 0)
        condition_type = condition.get('type', '统计值')
        
        # 逻辑映射
        logic_map = {
            '大于': '大于',
            '小于': '小于',
            '>': '大于',
            '<': '小于',
            '>=': '大于等于',
            '<=': '小于等于'
        }
        logic_text = logic_map.get(logic, logic)
        
        # 根据条件类型生成描述
        if condition_type == '统计值':
            # 统计值类型：当通道的统计值（平均值/最大值/最小值等）在X秒内大于/小于阈值时成立
            return f"当 {channel} 的{statistic}在{duration_sec}秒内{logic_text}{threshold} 时成立"
        elif condition_type == '变化幅度':
            # 变化幅度类型：当通道的变化率在X秒内大于/小于阈值时成立
            return f"当 {channel} 的{statistic}在{duration_sec}秒内{logic_text}{threshold} 时成立"
        else:
            # 通用格式
            return f"当 {channel} 的{statistic}在{duration_sec}秒内{logic_text}{threshold} 时成立"
    
    def start_config(self, session_id: str, report_type: str, file_id: Optional[str] = None) -> ConfigResponse:
        """开始配置流程"""
        # 优先从JSON配置文件中读取availableChannels（如果存在）
        available_channels = None
        if file_id:
            try:
                backend_dir = Path(__file__).parent.parent.parent
                config_dir = backend_dir / "config_sessions"
                
                # 查找匹配的配置文件
                config_path = None
                for json_file in config_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                            if cfg.get("fileId") == file_id:
                                config_path = json_file
                                # 从JSON文件中读取availableChannels
                                available_channels = cfg.get("availableChannels")
                                if available_channels:
                                    logger.info(f"从配置文件 {json_file.name} 读取到 availableChannels: {available_channels}")
                                break
                    except Exception:
                        continue
                
                # 如果没找到匹配的，尝试默认的 config_session.json
                if not available_channels:
                    default_path = config_dir / "config_session.json"
                    if default_path.exists():
                        try:
                            with open(default_path, 'r', encoding='utf-8') as f:
                                cfg = json.load(f)
                                if not file_id or cfg.get("fileId") == file_id:
                                    available_channels = cfg.get("availableChannels")
                                    if available_channels:
                                        logger.info(f"从默认配置文件读取到 availableChannels: {available_channels}")
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"从配置文件读取availableChannels失败: {e}")
        
        # 如果从配置文件读取失败，尝试从文件提取（仅稳态和功能计算）
        if not available_channels:
            if report_type in [ReportType.STEADY_STATE, ReportType.FUNCTION_CALC] and file_id:
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
                        available_channels = channels
                        logger.info(f"从文件 {file_path.name} 提取到通道: {available_channels}")
                except Exception as e:
                    logger.warning(f"从上传文件提取通道失败: {e}")
        
        # 对于功能计算和稳态分析，如果无法获取可用通道，提示用户重新上传文件
        if report_type in [ReportType.STEADY_STATE, ReportType.FUNCTION_CALC]:
            if not available_channels or len(available_channels) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="无法获取可用通道列表。请确保已上传数据文件，或重新上传文件。"
                )
        
        # 使用availableChannels生成默认参数
        default_params = self.get_default_params(report_type, available_channels)
        
        # 确定初始状态
        if report_type == ReportType.FUNCTION_CALC:
            initial_state = ConfigState.TIME_BASE_CONFIG
        else:
            initial_state = ConfigState.DISPLAY_CHANNELS
        
        # 保存file_id到session中，用于后续查找配置文件
        self.sessions[session_id] = {
            'state': initial_state,
            'report_type': report_type,
            'params': default_params,
            'step': 0,
            'created_at': datetime.now(),
            'file_id': file_id,  # 保存file_id，用于查找对应的配置文件
            'config_file_name': "config_session.json"
        }
        
        # 设置建议按钮
        if initial_state == ConfigState.DISPLAY_CHANNELS:
            suggested_actions = self.get_channel_options(report_type, default_params)
        elif initial_state == ConfigState.TIME_BASE_CONFIG:
            suggested_actions = ['下一步']
        else:
            suggested_actions = []
        
        return ConfigResponse(
            session_id=session_id,
            state=initial_state,
            message=self.get_step_message(report_type, initial_state, default_params),
            suggested_actions=suggested_actions,
            current_params=default_params
        )
    
    def _check_channels(self, available_channels: List[str]) -> Dict[str, bool]:
        """
        检查availableChannels中是否有Ng和Np通道（大小写不敏感）
        
        Returns:
            Dict with keys 'has_ng' and 'has_np'
        """
        has_ng = False
        has_np = False
        if available_channels:
            for channel in available_channels:
                channel_lower = channel.lower()
                if channel_lower == 'ng':
                    has_ng = True
                elif channel_lower == 'np':
                    has_np = True
        return {'has_ng': has_ng, 'has_np': has_np}
    
    def _extract_value_from_action(self, action: str, field_name: str) -> Any:
        """
        从action字符串中提取value
        例如："把阈值改成2000" -> 2000
             "修改统计方法为最大值" -> "最大值"
        """
        import re
        # 提取数值
        if field_name in ['threshold', 'duration_sec', 'duration']:
            # 查找数字（支持小数）
            numbers = re.findall(r'\d+(?:\.\d+)?', action)
            if numbers:
                try:
                    return float(numbers[0]) if '.' in numbers[0] else int(numbers[0])
                except:
                    pass
        # 提取字符串值（统计方法、判断依据）
        elif field_name == 'statistic':
            if '最大' in action:
                return '最大值'
            elif '最小' in action:
                return '最小值'
            elif '平均' in action:
                return '平均值'
            elif '变化' in action or '变化率' in action or '变化幅度' in action:
                return '变化率'
            elif '有效值' in action or 'rms' in action.lower():
                return '有效值'
        elif field_name == 'logic':
            if '大于' in action:
                return '大于'
            elif '小于' in action:
                return '小于'
            elif '等于' in action or '==' in action:
                return '等于'
        return None
    
    def _normalize_logic_value(self, value: Any) -> str:
        """
        规范化logic值：将中文转换为符号，去除空格
        例如："小于等于" -> "<=", ">=" -> ">=", " <= " -> "<="
        """
        if value is None:
            return value
        
        value_str = str(value).strip()
        
        # 逻辑值映射：中文 -> 符号
        logic_map = {
            '大于': '>',
            '小于': '<',
            '等于': '==',
            '大于等于': '>=',
            '小于等于': '<=',
            '>': '>',
            '<': '<',
            '==': '==',
            '>=': '>=',
            '<=': '<='
        }
        
        # 如果已经是符号格式，直接返回（去除空格后）
        normalized = logic_map.get(value_str, value_str)
        
        return normalized
    
    def _match_channel_name(self, value: Any, action: str, display_channels: List[str]) -> Optional[str]:
        """
        匹配通道名称，支持大小写不敏感匹配
        
        Args:
            value: LLM解析出的通道名（可能大小写不一致，如Np/np/NP）
            action: 用户输入的原始action字符串
            display_channels: 可选的通道列表（使用原始大小写）
        
        Returns:
            匹配到的通道名（使用display_channels中的原始大小写），如果未匹配到则返回None
        """
        # 优先使用value参数（LLM解析出的值）
        if value:
            value_str = str(value).strip()
            # 大小写不敏感匹配：遍历display_channels，找到匹配的通道
            for channel in display_channels:
                if channel.lower() == value_str.lower():
                    return channel
        
        # 如果value不存在或未匹配到，从action中匹配
        action_lower = action.lower()
        for channel in display_channels:
            # 完整匹配（大小写不敏感）
            if channel.lower() == action_lower:
                return channel
            # 部分匹配：检查通道名是否在action中（大小写不敏感）
            if channel.lower() in action_lower or channel in action:
                return channel
        
        return None
    
    def update_config(self, session_id: str, action: str, value: Any = None, parsed_by_llm: bool = False) -> ConfigResponse:
        """更新配置"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")
        
        # 存储parsed_by_llm标志，用于所有返回的响应
        self._current_parsed_by_llm = parsed_by_llm
        
        current_state = session['state']
        report_type = session['report_type']
        params = session['params']
        
        # 辅助方法：创建ConfigResponse并自动添加parsed_by_llm标志
        def create_response(**kwargs) -> ConfigResponse:
            kwargs.setdefault('parsed_by_llm', parsed_by_llm)
            return ConfigResponse(**kwargs)
        
        # 根据当前状态和操作更新配置
        if current_state == ConfigState.INITIAL:
            # 处理缺少Ng或Np通道时的"继续配置"和"取消"
            if action == '继续配置' or action == '继续':
                # 即使缺少Ng或Np，也继续配置流程
                if report_type == ReportType.FUNCTION_CALC:
                    # 重新生成默认参数并进入配置流程
                    available_channels = params.get('availableChannels', [])
                    default_params = self.get_default_params(report_type, available_channels)
                    session['params'] = default_params
                    session['state'] = ConfigState.TIME_BASE_CONFIG
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.TIME_BASE_CONFIG,
                        message=self.get_step_message(report_type, ConfigState.TIME_BASE_CONFIG, default_params),
                        suggested_actions=['下一步'],
                        current_params=default_params
                    )
            elif action == '取消' or action == '取消配置':
                del self.sessions[session_id]
                return create_response(
                    session_id=session_id,
                    state=ConfigState.INITIAL,
                    message="配置已取消，回到对话模式。",
                    suggested_actions=[],
                    current_params={}
                )
        
        if current_state == ConfigState.DISPLAY_CHANNELS:
            # 选择展示通道与完成通道选择
            selectable = params.get('availableChannels')
            
            # 如果params中没有availableChannels或为空，尝试从配置文件重新加载
            if not selectable or len(selectable) == 0:
                file_id = session.get('file_id')
                if file_id:
                    try:
                        backend_dir = Path(__file__).parent.parent.parent
                        config_dir = backend_dir / "config_sessions"
                        
                        # 查找匹配的配置文件
                        for json_file in config_dir.glob("*.json"):
                            try:
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    cfg = json.load(f)
                                    if cfg.get("fileId") == file_id:
                                        available_channels = cfg.get("availableChannels")
                                        if available_channels:
                                            # 更新params中的availableChannels
                                            params['availableChannels'] = available_channels
                                            selectable = available_channels
                                            logger.info(f"从配置文件 {json_file.name} 重新加载 availableChannels: {available_channels}")
                                            break
                            except Exception:
                                continue
                        
                        # 如果没找到匹配的，尝试默认的 config_session.json
                        if not selectable or len(selectable) == 0:
                            default_path = config_dir / "config_session.json"
                            if default_path.exists():
                                try:
                                    with open(default_path, 'r', encoding='utf-8') as f:
                                        cfg = json.load(f)
                                        if not file_id or cfg.get("fileId") == file_id:
                                            available_channels = cfg.get("availableChannels")
                                            if available_channels:
                                                params['availableChannels'] = available_channels
                                                selectable = available_channels
                                                logger.info(f"从默认配置文件重新加载 availableChannels: {available_channels}")
                                except Exception:
                                    pass
                    except Exception as e:
                        logger.warning(f"从配置文件重新加载availableChannels失败: {e}")
            
            # 如果仍然没有可用通道，返回错误
            if not selectable or len(selectable) == 0:
                return ConfigResponse(
                    session_id=session_id,
                    state=current_state,
                    message="无法获取可用通道列表。请重新上传数据文件。",
                    suggested_actions=[],
                    current_params=params
                )
            if action.startswith('选择 ') or action.startswith('使用 '):
                # 兼容"使用 xxx通道"与"选择 xxx"
                ch = action.replace('选择 ', '').replace('使用 ', '').strip()
                
                # 尝试精确匹配
                matched_channel = None
                if ch in selectable:
                    matched_channel = ch
                else:
                    # 尝试大小写不敏感的匹配
                    ch_lower = ch.lower()
                    for available_ch in selectable:
                        if available_ch.lower() == ch_lower:
                            matched_channel = available_ch
                            break
                
                if matched_channel:
                    display = params.setdefault('displayChannels', [])
                    if matched_channel not in display:
                        display.append(matched_channel)
                        logger.info(f"已添加通道到displayChannels: {matched_channel}, 当前列表: {display}")
                    else:
                        logger.info(f"通道已存在于displayChannels: {matched_channel}, 当前列表: {display}")
                else:
                    logger.warning(f"通道选择失败：'{ch}' 不在可选通道列表中。可选通道：{selectable}")
                
                # 留在本步骤，继续引导
                return create_response(
                    session_id=session_id,
                    state=ConfigState.DISPLAY_CHANNELS,
                    message=f"已选择展示通道：{params.get('displayChannels', [])}\n\n您可以继续选择其它通道，或点击'完成通道选择'。",
                    suggested_actions=self.get_channel_options(report_type, params),
                    current_params=params
                )
            elif action in ['完成通道选择', '完成选择']:
                display = params.get('displayChannels', []) or []
                if not display:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.DISPLAY_CHANNELS,
                        message="请至少选择一个通道。",
                        suggested_actions=self.get_channel_options(report_type, params),
                        current_params=params
                    )
                # 设置默认条件一/二，使用默认值
                params.setdefault('triggerLogic', {})
                # 使用第一个通道作为默认判断通道
                default_channel = display[0] if display else 'Ng'
                params['triggerLogic'] = {
                    'combination': 'AND',
                    'condition1': {
                        'enabled': True,
                        'channel': default_channel,
                        'type': '统计值',
                        'statistic': '平均值',  # 默认值：平均值
                        'duration_sec': 1,  # 默认值：1s
                        'logic': '>',  # 默认值：>
                        'threshold': 100  # 默认值：100
                    },
                    'condition2': {
                        'enabled': True,
                        'channel': default_channel,
                        'type': '变化幅度',
                        'statistic': '变化率',  # 默认值：变化率（可修改为其他统计方法）
                        'duration_sec': 1,  # 默认值：1s
                        'logic': '>',  # 默认值：>
                        'threshold': 100  # 默认值：100
                    }
                }
                # 新增：生成条件描述params['triggerDesc']
                cond1 = params['triggerLogic']['condition1']
                cond2 = params['triggerLogic']['condition2']
                logic_map = {'>': '大于', '<': '小于', '>=': '大于等于', '<=': '小于等于', '==': '等于'}
                logic_combo = params['triggerLogic']['combination']
                ch1 = cond1['channel']
                desc1 = f"当 {ch1} 的{cond1['statistic']}持续{cond1['duration_sec']}秒{logic_map.get(cond1['logic'], cond1['logic'])}{cond1['threshold']} 时成立"
                desc2 = f"当 {ch1} 的{cond2['statistic']}持续{cond2['duration_sec']}秒{logic_map.get(cond2['logic'], cond2['logic'])}{cond2['threshold']} 时成立"
                if logic_combo == 'AND':
                    trigger_desc = f"条件一：{desc1}，且 条件二：{desc2}。"
                elif logic_combo == '仅用条件一':
                    trigger_desc = f"仅条件一：{desc1}。"
                elif logic_combo == '仅用条件二':
                    trigger_desc = f"仅条件二：{desc2}。"
                else:
                    trigger_desc = f"条件描述：{desc1} 和 {desc2}"
                params['triggerDesc'] = trigger_desc
                
                # 保存displayChannels到JSON文件（必须执行，不能因为异常而跳过）
                self._save_display_channels_to_json(session, params)
                # _save_display_channels_to_json会直接修改params['displayChannels']为排序后的顺序
                display = params.get('displayChannels', display)  # 使用排序后的顺序
                
                # 直接进入TRIGGER_COMBO状态，跳过选择转速通道步骤
                session['state'] = ConfigState.TRIGGER_COMBO
                
                # 先显示用户选择的通道列表（已按照文件顺序排序）
                channels_text = "您已选择的通道：" + "、".join(display) + "\n\n"
                
                return create_response(
                    session_id=session_id,
                    state=ConfigState.TRIGGER_COMBO,
                    message=channels_text + "已为您填充默认条件一/二：\n条件一：{}\n条件二：{}\n\n请选择组合逻辑：仅用条件一 / 仅用条件二 / AND。".format(desc1, desc2),
                    suggested_actions=['仅用条件一', '仅用条件二', 'AND'],
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
                
                # 获取当前选择的条件的默认参数信息
                trigger_logic = params.get('triggerLogic', {})
                combination = trigger_logic.get('combination', 'AND')
                
                # 构建详细的参数信息消息
                def _build_condition_params_message(cond: dict, cond_name: str) -> str:
                    """构建条件的参数信息"""
                    return f"""
【{cond_name}默认参数】：
- 监控通道: {cond.get('channel', '未设置')}
- 统计方法: {cond.get('statistic', '未设置')}
- 持续时长: {cond.get('duration_sec', '未设置')}秒
- 判断依据: {cond.get('logic', '未设置')}
- 阈值: {cond.get('threshold', '未设置')}"""
                
                # 根据组合逻辑生成消息
                if combination == 'Cond1_Only':
                    cond1 = trigger_logic.get('condition1', {})
                    cond1_desc = self.format_condition_description(cond1)
                    # 保存条件一到JSON文件
                    self._save_conditions_to_json(session, params)
                    message_text = (
                        f"已选择：仅用条件一\n\n"
                        f"条件描述：{cond1_desc}\n"
                        f"{_build_condition_params_message(cond1, '条件一')}\n\n"
                        f"【可修改的参数】：\n"
                        f"- 监控通道（channel）：可从已选择的通道中选择\n"
                        f"- 统计方法（statistic）：可改为 平均值/最大值/最小值/中位数 等\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判断依据（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件一的阈值改为9000\"\n"
                        f"- \"将统计方法改为最大值\"\n"
                        f"- \"修改持续时长为5秒\"\n"
                        f"- \"监控通道改为系统电压\""
                    )
                elif combination == 'Cond2_Only':
                    cond2 = trigger_logic.get('condition2', {})
                    cond2_desc = self.format_condition_description(cond2)
                    # 保存条件二到JSON文件
                    self._save_conditions_to_json(session, params)
                    message_text = (
                        f"已选择：仅用条件二\n\n"
                        f"条件描述：{cond2_desc}\n"
                        f"{_build_condition_params_message(cond2, '条件二')}\n\n"
                        f"【可修改的参数】：\n"
                        f"- 监控通道（channel）：可从已选择的通道中选择\n"
                        f"- 统计方法（statistic）：默认\"变化率\"，可改为 平均值/最大值/最小值/有效值/变化率\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判断依据（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件二的阈值改为100\"\n"
                        f"- \"修改持续时长为15秒\"\n"
                        f"- \"监控通道改为系统电压\""
                    )
                else:  # AND
                    cond1 = trigger_logic.get('condition1', {})
                    cond2 = trigger_logic.get('condition2', {})
                    cond1_desc = self.format_condition_description(cond1)
                    cond2_desc = self.format_condition_description(cond2)
                    # 保存条件一到JSON文件（AND情况下保存两个条件）
                    self._save_conditions_to_json(session, params)
                    message_text = (
                        f"已选择：AND（同时满足条件一和条件二）\n\n"
                        f"条件描述：\n"
                        f"条件一：{cond1_desc}\n"
                        f"条件二：{cond2_desc}\n\n"
                        f"{_build_condition_params_message(cond1, '条件一')}\n"
                        f"{_build_condition_params_message(cond2, '条件二')}\n\n"
                        f"【可修改的参数】：\n\n"
                        f"条件一：\n"
                        f"- 监控通道（channel）：可从已选择的通道中选择\n"
                        f"- 统计方法（statistic）：可改为 平均值/最大值/最小值/中位数 等\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判断依据（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"条件二：\n"
                        f"- 监控通道（channel）：可从已选择的通道中选择\n"
                        f"- 统计方法（statistic）：默认\"变化率\"，可改为 平均值/最大值/最小值/有效值/变化率\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判断依据（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件一的阈值改为9000\"\n"
                        f"- \"修改条件一的持续时长为5秒\"\n"
                        f"- \"条件一的监控通道改为系统电压\"\n"
                        f"- \"把条件二的阈值改为100\"\n"
                        f"- \"修改条件二的持续时长为15秒\""
                    )
                
                session['state'] = ConfigState.PARAMETER_CONFIG
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=message_text,
                    suggested_actions=[],  # 不使用按钮，让用户用自然语言对话
                    current_params=params
                )
        
        elif current_state == ConfigState.PARAMETER_CONFIG:
            trigger_logic = params.get('triggerLogic', {})
            combination = trigger_logic.get('combination', 'AND')
            # 允许编辑参数列表（包括监控通道）
            display_channels = params.get('displayChannels', [])
            def _msg_for_condition(cond: dict, cond_name: str):
                statistic = cond.get('statistic', '')
                # 如果条件二没有设置statistic，默认显示"变化率"
                if cond_name == '条件二' and not statistic:
                    statistic = '变化率'
                
                return f"\n【当前为{cond_name}，参数如下】\n" \
                       f"- 监控通道: {cond.get('channel', '')} (可选通道: {', '.join(display_channels)})\n" \
                       f"- 统计方法: {statistic}\n" \
                       f"- 持续时长(秒): {cond.get('duration_sec', '')}\n" \
                       f"- 判断依据: {cond.get('logic', '')}\n" \
                       f"- 阈值: {cond.get('threshold', '')}"
            #########################################################################################
            if combination == 'Cond1_Only':
                condition = trigger_logic.get('condition1', {})
                # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                    field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                    # 处理监控通道修改：支持"监控通道"和"通道"两种说法
                    if '监控通道' in action or '通道' in action or 'channel' in action.lower():
                        # 使用辅助函数匹配通道名，支持大小写不敏感匹配
                        new_channel = self._match_channel_name(value, action, display_channels)
                        if new_channel:
                            condition['channel'] = new_channel
                            params['triggerLogic']['condition1'] = condition
                            # 记录最后一次操作的条件
                            session['last_modified_condition'] = '条件一'
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改监控通道为 {new_channel}。{_msg_for_condition(condition, '条件一')}",
                                suggested_actions=[],
                                current_params=params
                            )
                        else:
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"未能识别您要选择的通道。可选通道：{', '.join(display_channels)}\n{_msg_for_condition(condition, '条件一')}\n请明确指定通道名，例如：'监控通道改为 {display_channels[0] if display_channels else '通道名'}'。",
                                suggested_actions=[],
                                current_params=params
                            )
                    # 尝试匹配字段并更新
                    field_updated = False
                    for k, v in field_map.items():
                        # 对于"判断依据"字段，同时支持"判断依据"、"逻辑"和"判据"三种说法
                        if k == '判断依据':
                            matched = '判断依据' in action or '逻辑' in action or '判据' in action
                        else:
                            matched = k in action
                        
                        if matched:
                            # 优先使用value参数（LLM解析出的值），如果value为None，尝试从action字符串中提取
                            extracted_value = None
                            if value is not None:
                                # 如果value存在，直接使用（支持LLM解析出的值）
                                extracted_value = value
                            else:
                                # 如果value为None，尝试从action字符串中提取
                                extracted_value = self._extract_value_from_action(action, v)
                            
                            if extracted_value is not None:
                                # 验证统计时长：0.1s~50s
                                if v == 'duration_sec':
                                    if extracted_value < 0.1 or extracted_value > 50:
                                        return ConfigResponse(
                                            session_id=session_id,
                                            state=ConfigState.PARAMETER_CONFIG,
                                            message=f"统计时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。",
                                            suggested_actions=[],
                                            current_params=params
                                        )
                                # 规范化logic值：将中文转换为符号，去除空格
                                if v == 'logic':
                                    extracted_value = self._normalize_logic_value(extracted_value)
                                condition[v] = extracted_value
                                field_updated = True
                                break
                    
                    if field_updated:
                        params['triggerLogic']['condition1'] = condition
                        # 记录最后一次操作的条件
                        session['last_modified_condition'] = '条件一'
                        self._save_display_channels_to_json(session, params)  # 立即保存
                        self._save_conditions_to_json(session, params)  # 保存conditions
                        # 获取field_name，支持"逻辑"、"判断依据"和"判据"三种说法
                        field_name = None
                        for k in field_map.keys():
                            if k == '判断依据':
                                if '判断依据' in action or '逻辑' in action or '判据' in action:
                                    field_name = k
                                    break
                            elif k in action:
                                field_name = k
                                break
                        field_name = field_name or '参数'
                        
                        # 获取field_key，支持"逻辑"、"判断依据"和"判据"三种说法
                        field_key = None
                        for k, v in field_map.items():
                            if k == '判断依据':
                                if '判断依据' in action or '逻辑' in action or '判据' in action:
                                    field_key = v
                                    break
                            elif k in action:
                                field_key = v
                                break
                        actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition, '条件一')}",
                            suggested_actions=[],
                            current_params=params
                        )
                    else:
                        # 如果无法识别具体字段，提示用户
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"未能识别要修改的参数。{_msg_for_condition(condition, '条件一')}\n请明确说明要修改的参数，例如：'把阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                elif action in ['确认', '下一步', '下一步骤', '继续', '确认配置', '好了', 'ok']:
                    # 确认配置，保存并进入生成状态
                    self._save_display_channels_to_json(session, params)
                    self._save_conditions_to_json(session, params)
                    session['state'] = ConfigState.GENERATING
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.GENERATING,
                        message="配置已确认，正在准备生成报表。\n如需修改配置，请直接使用自然语言修改参数，例如：'把条件一的阈值改为2000'。",
                        suggested_actions=[],
                        current_params=params
                    )
                else:
                    # 没有匹配到action，可能是纯自然语言输入，提示用户如何表达
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message=_msg_for_condition(condition, '条件一') + "\n您可以使用自然语言修改参数，例如：'把阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'、'监控通道改为系统电压'。",
                        suggested_actions=[],
                        current_params=params
                    )
            #########################################################################################
            elif combination == 'Cond2_Only':
                condition = trigger_logic.get('condition2', {})
                # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                    field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                    # 处理监控通道修改：支持"监控通道"和"通道"两种说法
                    if '监控通道' in action or '通道' in action or 'channel' in action.lower():
                        # 使用辅助函数匹配通道名，支持大小写不敏感匹配
                        new_channel = self._match_channel_name(value, action, display_channels)
                        if new_channel:
                            condition['channel'] = new_channel
                            params['triggerLogic']['condition2'] = condition
                            # 记录最后一次操作的条件
                            session['last_modified_condition'] = '条件二'
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改监控通道为 {new_channel}。{_msg_for_condition(condition, '条件二')}",
                                suggested_actions=[],
                                current_params=params
                            )
                        else:
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"未能识别您要选择的通道。可选通道：{', '.join(display_channels)}\n{_msg_for_condition(condition, '条件二')}\n请明确指定通道名，例如：'监控通道改为 {display_channels[0] if display_channels else '通道名'}'。",
                                suggested_actions=[],
                                current_params=params
                            )
                    # 尝试匹配字段并更新
                    field_updated = False
                    for k, v in field_map.items():
                        # 对于"判断依据"字段，同时支持"判断依据"、"逻辑"和"判据"三种说法
                        if k == '判断依据':
                            matched = '判断依据' in action or '逻辑' in action or '判据' in action
                        else:
                            matched = k in action
                        
                        if matched:
                            # 优先使用value参数（LLM解析出的值），如果value为None，尝试从action字符串中提取
                            extracted_value = None
                            if value is not None:
                                extracted_value = value
                            else:
                                extracted_value = self._extract_value_from_action(action, v)
                            if extracted_value is not None:
                                # 验证统计时长：0.1s~50s
                                if v == 'duration_sec':
                                    if extracted_value < 0.1 or extracted_value > 50:
                                        return ConfigResponse(
                                            session_id=session_id,
                                            state=ConfigState.PARAMETER_CONFIG,
                                            message=f"统计时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。",
                                            suggested_actions=[],
                                            current_params=params
                                        )
                                # 规范化logic值：将中文转换为符号，去除空格
                                if v == 'logic':
                                    extracted_value = self._normalize_logic_value(extracted_value)
                                condition[v] = extracted_value
                                field_updated = True
                                break
                    
                    if field_updated:
                        params['triggerLogic']['condition2'] = condition
                        # 记录最后一次操作的条件
                        session['last_modified_condition'] = '条件二'
                        self._save_display_channels_to_json(session, params)
                        self._save_conditions_to_json(session, params)  # 保存conditions
                        # 获取field_name，支持"逻辑"、"判断依据"和"判据"三种说法
                        field_name = None
                        for k in field_map.keys():
                            if k == '判断依据':
                                if '判断依据' in action or '逻辑' in action or '判据' in action:
                                    field_name = k
                                    break
                            elif k in action:
                                field_name = k
                                break
                        field_name = field_name or '参数'
                        
                        # 获取field_key，支持"逻辑"、"判断依据"和"判据"三种说法
                        field_key = None
                        for k, v in field_map.items():
                            if k == '判断依据':
                                if '判断依据' in action or '逻辑' in action or '判据' in action:
                                    field_key = v
                                    break
                            elif k in action:
                                field_key = v
                                break
                        actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition, '条件二')}",
                            suggested_actions=[],
                            current_params=params
                        )
                    else:
                        # 如果无法识别具体字段，提示用户
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"未能识别要修改的参数。{_msg_for_condition(condition, '条件二')}\n请明确说明要修改的参数，例如：'把阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                elif action in ['确认', '下一步', '下一步骤', '继续', '确认配置', '好了', 'ok']:
                    # 确认配置，保存并进入生成状态
                    self._save_display_channels_to_json(session, params)
                    self._save_conditions_to_json(session, params)
                    session['state'] = ConfigState.GENERATING
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.GENERATING,
                        message="配置已确认，正在准备生成报表。\n如需修改配置，请直接使用自然语言修改参数，例如：'把条件一的阈值改为2000'。",
                        suggested_actions=[],
                        current_params=params
                    )
                else:
                    # 没有匹配到action，可能是纯自然语言输入，提示用户如何表达
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message=_msg_for_condition(condition, '条件二') + "\n您可以使用自然语言修改参数，例如：'把阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。",
                        suggested_actions=[],
                        current_params=params
                    )
            #########################################################################################
            elif combination == 'AND':
                # 优先级：1. 用户明确指定"条件一"或"条件二" -> 使用指定的条件
                #        2. 用户未指定 -> 使用last_modified_condition（上一次修改的条件）
                #        3. 都没有 -> 默认条件一
                target_condition = None
                if action and '条件一' in action:
                    target_condition = 'condition1'
                elif action and '条件二' in action:
                    target_condition = 'condition2'
                
                if not target_condition:
                    # 如果用户没有明确指定条件，优先使用last_modified_condition
                    last_modified_condition = session.get('last_modified_condition')
                    if last_modified_condition == '条件一':
                        target_condition = 'condition1'
                    elif last_modified_condition == '条件二':
                        target_condition = 'condition2'
                    else:
                        # 如果last_modified_condition也没有，默认条件一
                        target_condition = 'condition1'
                
                # 根据目标条件决定处理哪个条件
                if target_condition == 'condition1':
                    condition = trigger_logic.get('condition1', {})
                    # 从action中移除"条件一"，以便后续字段匹配
                    action_for_match = action
                    if target_condition == 'condition1' and action:
                        action_for_match = action.replace('条件一', '').strip()
                    # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                    if action_for_match and ('修改' in action_for_match or '改为' in action_for_match or '改成' in action_for_match or '设置为' in action_for_match or '设置成' in action_for_match):
                        field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                        # 处理监控通道修改：支持"监控通道"和"通道"两种说法
                        if '监控通道' in action_for_match or '通道' in action_for_match or 'channel' in action_for_match.lower():
                            # 使用辅助函数匹配通道名，支持大小写不敏感匹配
                            new_channel = self._match_channel_name(value, action_for_match, display_channels)
                            if new_channel:
                                condition['channel'] = new_channel
                                params['triggerLogic']['condition1'] = condition
                                # 记录最后一次操作的条件
                                session['last_modified_condition'] = '条件一'
                                self._save_display_channels_to_json(session, params)
                                self._save_conditions_to_json(session, params)
                                return ConfigResponse(
                                    session_id=session_id,
                                    state=ConfigState.PARAMETER_CONFIG,
                                    message=f"已更改监控通道为 {new_channel}。{_msg_for_condition(condition, '条件一')}",
                                    suggested_actions=[],
                                    current_params=params
                                )
                            else:
                                return ConfigResponse(
                                    session_id=session_id,
                                    state=ConfigState.PARAMETER_CONFIG,
                                    message=f"未能识别您要选择的通道。可选通道：{', '.join(display_channels)}\n{_msg_for_condition(condition, '条件一')}\n请明确指定通道名，例如：'监控通道改为 {display_channels[0] if display_channels else '通道名'}'。",
                                    suggested_actions=[],
                                    current_params=params
                                )
                        # 尝试匹配字段并更新
                        field_updated = False
                        for k, v in field_map.items():
                            # 对于"判断依据"字段，支持"判断依据"、"逻辑"和"判据"三种说法
                            if k == '判断依据':
                                matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                            else:
                                matched = k in action_for_match
                            
                            if matched:
                                # 优先使用value参数（LLM解析出的值），如果value为None，尝试从action字符串中提取
                                extracted_value = None
                                if value is not None:
                                    # 如果value存在，直接使用（支持LLM解析出的值）
                                    extracted_value = value
                                else:
                                    # 如果value为None，尝试从action字符串中提取
                                    extracted_value = self._extract_value_from_action(action_for_match, v)
                                
                                if extracted_value is not None:
                                    # 验证统计时长：0.1s~50s
                                    if v == 'duration_sec':
                                        if extracted_value < 0.1 or extracted_value > 50:
                                            return ConfigResponse(
                                                session_id=session_id,
                                                state=ConfigState.PARAMETER_CONFIG,
                                                message=f"统计时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。",
                                                suggested_actions=[],
                                                current_params=params
                                            )
                                    condition[v] = extracted_value
                                    field_updated = True
                                    break
                        
                        if field_updated:
                            params['triggerLogic']['condition1'] = condition
                            # 记录最后一次操作的条件
                            session['last_modified_condition'] = '条件一'
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)  # 保存conditions
                            # 获取field_name，支持"逻辑"、"判断依据"和"判据"三种说法
                            field_name = None
                            for k in field_map.keys():
                                if k == '判断依据':
                                    if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                        field_name = k
                                        break
                                elif k in action_for_match:
                                    field_name = k
                                    break
                            field_name = field_name or '参数'
                            
                            # 获取field_key，支持"逻辑"、"判断依据"和"判据"三种说法
                            field_key = None
                            for k, v in field_map.items():
                                if k == '判断依据':
                                    if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                        field_key = v
                                        break
                                elif k in action_for_match:
                                    field_key = v
                                    break
                            actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition,'条件一')}",
                                suggested_actions=[],
                                current_params=params
                            )
                        else:
                            # 如果无法识别具体字段，提示用户
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"未能识别要修改的参数。{_msg_for_condition(condition, '条件一')}\n请明确说明要修改的参数，例如：'把条件一的阈值改为2000'、'修改统计方法为最大值'。",
                                suggested_actions=[],
                                current_params=params
                            )
                    elif action in ['下一步', '下一步骤', '继续']:
                        # 记录条件一的displayChannels（复制列表，避免引用问题）
                        condition['displayChannels'] = list(params.get('displayChannels', []))
                        params['triggerLogic']['condition1'] = condition
                        # 更新last_modified_condition为条件二，以便后续默认编辑条件二
                        session['last_modified_condition'] = '条件二'
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(trigger_logic.get('condition2', {}), '条件二')+"\n请继续编辑条件二，您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'、'监控通道改为系统电压'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    elif action in ['确认', '确认配置', '好了', 'ok']:
                        # 确认配置，保存并进入生成状态
                        self._save_display_channels_to_json(session, params)
                        self._save_conditions_to_json(session, params)
                        session['state'] = ConfigState.GENERATING
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.GENERATING,
                            message="配置已确认，正在准备生成报表。\n如需修改配置，请回复'返回上一步'或'修改配置'，或直接使用自然语言修改参数，例如：'把条件一的阈值改为2000'。",
                            suggested_actions=['返回上一步', '修改配置'],
                            current_params=params
                        )
                    else:
                        # 没有匹配到action，可能是纯自然语言输入
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(condition, '条件一')+ "\n您可以使用自然语言修改参数，例如：'把条件一的阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。",
                            suggested_actions=[],
                            current_params=params
                        )
                elif target_condition == 'condition2':
                    condition = trigger_logic.get('condition2', {})
                    # 从action中移除"条件二"，以便后续字段匹配
                    action_for_match = action
                    if target_condition == 'condition2' and action:
                        action_for_match = action.replace('条件二', '').strip()
                    # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                    if action_for_match and ('修改' in action_for_match or '改为' in action_for_match or '改成' in action_for_match or '设置为' in action_for_match or '设置成' in action_for_match):
                        field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                        # 处理监控通道修改：支持"监控通道"和"通道"两种说法
                        if '监控通道' in action_for_match or '通道' in action_for_match or 'channel' in action_for_match.lower():
                            # 使用辅助函数匹配通道名，支持大小写不敏感匹配
                            new_channel = self._match_channel_name(value, action_for_match, display_channels)
                            if new_channel:
                                condition['channel'] = new_channel
                                params['triggerLogic']['condition2'] = condition
                                # 记录最后一次操作的条件
                                session['last_modified_condition'] = '条件二'
                                self._save_display_channels_to_json(session, params)
                                self._save_conditions_to_json(session, params)
                                return ConfigResponse(
                                    session_id=session_id,
                                    state=ConfigState.PARAMETER_CONFIG,
                                    message=f"已更改监控通道为 {new_channel}。{_msg_for_condition(condition, '条件二')}",
                                    suggested_actions=[],
                                    current_params=params
                                )
                            else:
                                return ConfigResponse(
                                    session_id=session_id,
                                    state=ConfigState.PARAMETER_CONFIG,
                                    message=f"未能识别您要选择的通道。可选通道：{', '.join(display_channels)}\n{_msg_for_condition(condition, '条件二')}\n请明确指定通道名，例如：'监控通道改为 {display_channels[0] if display_channels else '通道名'}'。",
                                    suggested_actions=[],
                                    current_params=params
                                )
                        # 尝试匹配字段并更新
                        field_updated = False
                        for k, v in field_map.items():
                            # 对于"判断依据"字段，支持"判断依据"、"逻辑"和"判据"三种说法
                            if k == '判断依据':
                                matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                            else:
                                matched = k in action_for_match
                            
                            if matched:
                                # 优先使用value参数（LLM解析出的值），如果value为None，尝试从action字符串中提取
                                extracted_value = None
                                if value is not None:
                                    extracted_value = value
                                else:
                                    extracted_value = self._extract_value_from_action(action_for_match, v)
                                if extracted_value is not None:
                                    # 验证统计时长：0.1s~50s
                                    if v == 'duration_sec':
                                        if extracted_value < 0.1 or extracted_value > 50:
                                            return ConfigResponse(
                                                session_id=session_id,
                                                state=ConfigState.PARAMETER_CONFIG,
                                                message=f"统计时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。",
                                                suggested_actions=[],
                                                current_params=params
                                            )
                                    condition[v] = extracted_value
                                    field_updated = True
                                    break
                        
                        if field_updated:
                            params['triggerLogic']['condition2'] = condition
                            # 记录最后一次操作的条件
                            session['last_modified_condition'] = '条件二'
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)  # 保存conditions
                            # 获取field_name，支持"逻辑"、"判断依据"和"判据"三种说法
                            field_name = None
                            for k in field_map.keys():
                                if k == '判断依据':
                                    if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                        field_name = k
                                        break
                                elif k in action_for_match:
                                    field_name = k
                                    break
                            field_name = field_name or '参数'
                            
                            # 获取field_key，支持"逻辑"、"判断依据"和"判据"三种说法
                            field_key = None
                            for k, v in field_map.items():
                                if k == '判断依据':
                                    if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                        field_key = v
                                        break
                                elif k in action_for_match:
                                    field_key = v
                                    break
                            actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition,'条件二')}",
                                suggested_actions=[],
                                current_params=params
                            )
                        else:
                            # 如果无法识别具体字段，提示用户
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"未能识别要修改的参数。{_msg_for_condition(condition, '条件二')}\n请明确说明要修改的参数，例如：'把条件二的阈值改为2000'、'修改统计方法为最大值'。",
                                suggested_actions=[],
                                current_params=params
                            )
                    elif action in ['确认', '确认配置', '好了', 'ok']:
                        # 确认配置，保存并进入生成状态
                        self._save_display_channels_to_json(session, params)
                        self._save_conditions_to_json(session, params)
                        session['state'] = ConfigState.GENERATING
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.GENERATING,
                            message="配置已确认，正在准备生成报表。\n如需修改配置，请回复'返回上一步'或'修改配置'，或直接使用自然语言修改参数，例如：'把条件一的阈值改为2000'。",
                            suggested_actions=['返回上一步', '修改配置'],
                            current_params=params
                        )
                    else:
                        # 没有匹配到action，可能是纯自然语言输入
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(condition, '条件二') + "\n您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。",
                            suggested_actions=[],
                            current_params=params
                        )
                else:
                    # 兜底：如果target_condition仍然是None（理论上不应该发生）
                    # 默认处理条件一
                    condition = trigger_logic.get('condition1', {})
                    condition_name = '条件一'
                    
                    # 检查是否是确认操作
                    if action in ['确认', '下一步', '下一步骤', '继续', '确认配置']:
                        # 确认配置，保存并进入生成状态
                        self._save_display_channels_to_json(session, params)
                        self._save_conditions_to_json(session, params)
                        session['state'] = ConfigState.GENERATING
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.GENERATING,
                            message="配置已确认，准备生成报表。",
                            suggested_actions=[],
                            current_params=params
                        )
                    
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message=f"未能识别您要修改的条件。{_msg_for_condition(condition, condition_name)}\n请明确指定要修改的条件，例如：'把条件一的阈值改为2000'、'修改条件二的统计方法为最大值'。",
                        suggested_actions=[],
                        current_params=params
                    )
            # 兜底：如果没有匹配到任何组合逻辑，提示用户
            return ConfigResponse(
                session_id=session_id,
                state=ConfigState.PARAMETER_CONFIG,
                message="未能识别您的操作。请使用自然语言修改参数，例如：'把阈值改为2000'、'修改统计方法为最大值'。",
                suggested_actions=[],
                current_params=params
            )
        
        elif current_state == ConfigState.SELECT_JUDGE_CHANNEL:
            # 通过自然语言选择判断通道
            display_channels = params.get('displayChannels', [])
            selected_channel = None
            
            # 尝试从用户输入中匹配通道名
            action_lower = action.lower() if action else ""
            for channel in display_channels:
                channel_lower = channel.lower()
                # 检查用户输入是否包含通道名或通道名的关键词
                if channel in action or channel_lower in action_lower:
                    # 进一步检查是否是"使用"、"选择"等关键词
                    use_keywords = ['使用', '选择', '用', 'use', 'select']
                    if any(keyword in action for keyword in use_keywords):
                        selected_channel = channel
                        break
            
            if selected_channel:
                # 保存判断通道
                params['judgeChannel'] = selected_channel
                # 更新条件中的通道（如果需要）
                trigger_logic = params.get('triggerLogic', {})
                if trigger_logic.get('condition1'):
                    trigger_logic['condition1']['channel'] = selected_channel
                if trigger_logic.get('condition2'):
                    trigger_logic['condition2']['channel'] = selected_channel
                params['triggerLogic'] = trigger_logic
                
                # 保存配置
                self._save_display_channels_to_json(session, params)
                self._save_conditions_to_json(session, params)
                
                return create_response(
                    session_id=session_id,
                    state=ConfigState.SELECT_JUDGE_CHANNEL,
                    message=f"已选择 {selected_channel} 作为判断通道。",
                    suggested_actions=[],
                    current_params=params
                )
            else:
                # 未能识别通道，提示用户
                return create_response(
                    session_id=session_id,
                    state=ConfigState.SELECT_JUDGE_CHANNEL,
                    message=f"未能识别您要选择的通道。\n可选通道：{', '.join(display_channels)}\n\n请使用自然语言选择，例如：\"使用 {display_channels[0] if display_channels else '通道名'} 作为判断通道\"。",
                    suggested_actions=[],
                    current_params=params
                )
        
        # 功能计算相关状态处理
        elif current_state == ConfigState.TIME_BASE_CONFIG:
            # 配置"时间"（基准时刻）
            time_base = params.setdefault('time_base', {})
            available_channels = params.get('availableChannels', [])
            
            # 增强自然语言解析：支持"修改"、"改为"等格式
            if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                field_map = {'统计方法': 'statistic', '持续时长': 'duration', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                action_for_match = action
                
                # 处理监控通道修改
                if '监控通道' in action_for_match or '通道' in action_for_match or 'channel' in action_for_match.lower():
                    new_channel = self._match_channel_name(value, action_for_match, available_channels)
                    if new_channel:
                        time_base['channel'] = new_channel
                        params['time_base'] = time_base
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.TIME_BASE_CONFIG,
                            message=f"已更改监控通道为 {new_channel}。\n\n" + self._get_time_base_config_message(time_base, available_channels),
                            suggested_actions=['下一步'],
                            current_params=params
                        )
                    else:
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.TIME_BASE_CONFIG,
                            message=f"未能识别您要选择的通道。可选通道：{', '.join(available_channels)}\n\n" + self._get_time_base_config_message(time_base, available_channels) + "\n请明确指定通道名。",
                            suggested_actions=['下一步'],
                            current_params=params
                        )
                
                # 尝试匹配字段并更新
                field_updated = False
                for k, v in field_map.items():
                    if k == '判断依据':
                        matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                    else:
                        matched = k in action_for_match
                    
                    if matched:
                        extracted_value = None
                        if value is not None:
                            extracted_value = value
                        else:
                            extracted_value = self._extract_value_from_action(action_for_match, v)
                        
                        if extracted_value is not None:
                            # 验证持续时长：0.1s~50s
                            if v == 'duration':
                                if extracted_value < 0.1 or extracted_value > 50:
                                    return create_response(
                                        session_id=session_id,
                                        state=ConfigState.TIME_BASE_CONFIG,
                                        message=f"持续时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。\n\n" + self._get_time_base_config_message(time_base, available_channels),
                                        suggested_actions=['下一步'],
                                        current_params=params
                                    )
                            time_base[v] = extracted_value
                            field_updated = True
                            break
                
                if field_updated:
                    params['time_base'] = time_base
                    self._save_function_calc_config_to_json(session, params)
                    field_name = None
                    for k in field_map.keys():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_name = k
                                break
                        elif k in action_for_match:
                            field_name = k
                            break
                    field_name = field_name or '参数'
                    field_key = None
                    for k, v in field_map.items():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_key = v
                                break
                        elif k in action_for_match:
                            field_key = v
                            break
                    actual_value = value if value is not None else (time_base.get(field_key) if field_key else None)
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.TIME_BASE_CONFIG,
                        message=f"已更改{field_name}为{actual_value}。\n\n" + self._get_time_base_config_message(time_base, available_channels),
                        suggested_actions=['下一步'],
                        current_params=params
                    )
                else:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.TIME_BASE_CONFIG,
                        message=f"未能识别要修改的参数。\n\n" + self._get_time_base_config_message(time_base, available_channels) + "\n请明确说明要修改的参数。",
                        suggested_actions=['下一步'],
                        current_params=params
                    )
            elif action in ['确认', '下一步', '下一步骤', '继续']:
                # 进入下一步：启动时间配置
                # 在切换步骤前保存当前步骤的配置
                self._save_function_calc_config_to_json(session, params)
                session['state'] = ConfigState.STARTUP_TIME_CONFIG
                startup_time = params.setdefault('startup_time', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.STARTUP_TIME_CONFIG,
                    message=self._get_startup_time_config_message(startup_time, available_channels),
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            else:
                # 没有匹配到action，提示用户
                return create_response(
                    session_id=session_id,
                    state=ConfigState.TIME_BASE_CONFIG,
                    message=self._get_time_base_config_message(time_base, available_channels) + "\n您可以使用自然语言修改参数，例如：'把阈值改为600'、'修改统计方法为最大值'。",
                    suggested_actions=['下一步'],
                    current_params=params
                )
        
        elif current_state == ConfigState.STARTUP_TIME_CONFIG:
            # 配置"启动时间"
            startup_time = params.setdefault('startup_time', {})
            available_channels = params.get('availableChannels', [])
            
            if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                field_map = {'统计方法': 'statistic', '持续时长': 'duration', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                action_for_match = action
                
                if '监控通道' in action_for_match or '通道' in action_for_match or 'channel' in action_for_match.lower():
                    new_channel = self._match_channel_name(value, action_for_match, available_channels)
                    if new_channel:
                        startup_time['channel'] = new_channel
                        params['startup_time'] = startup_time
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.STARTUP_TIME_CONFIG,
                            message=f"已更改监控通道为 {new_channel}。\n\n" + self._get_startup_time_config_message(startup_time, available_channels),
                            suggested_actions=['返回上一步', '下一步'],
                            current_params=params
                        )
                    else:
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.STARTUP_TIME_CONFIG,
                            message=f"未能识别您要选择的通道。可选通道：{', '.join(available_channels)}\n\n" + self._get_startup_time_config_message(startup_time, available_channels) + "\n请明确指定通道名。",
                            suggested_actions=['返回上一步', '下一步'],
                            current_params=params
                        )
                
                field_updated = False
                for k, v in field_map.items():
                    if k == '判断依据':
                        matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                    else:
                        matched = k in action_for_match
                    
                    if matched:
                        extracted_value = None
                        if value is not None:
                            extracted_value = value
                        else:
                            extracted_value = self._extract_value_from_action(action_for_match, v)
                        
                        if extracted_value is not None:
                            if v == 'duration':
                                if extracted_value < 0.1 or extracted_value > 50:
                                    return create_response(
                                        session_id=session_id,
                                        state=ConfigState.STARTUP_TIME_CONFIG,
                                        message=f"持续时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。\n\n" + self._get_startup_time_config_message(startup_time, available_channels),
                                        suggested_actions=['返回上一步', '下一步'],
                                        current_params=params
                                    )
                            startup_time[v] = extracted_value
                            field_updated = True
                            break
                
                if field_updated:
                    params['startup_time'] = startup_time
                    self._save_function_calc_config_to_json(session, params)
                    field_name = None
                    for k in field_map.keys():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_name = k
                                break
                        elif k in action_for_match:
                            field_name = k
                            break
                    field_name = field_name or '参数'
                    field_key = None
                    for k, v in field_map.items():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_key = v
                                break
                        elif k in action_for_match:
                            field_key = v
                            break
                    actual_value = value if value is not None else (startup_time.get(field_key) if field_key else None)
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.STARTUP_TIME_CONFIG,
                        message=f"已更改{field_name}为{actual_value}。\n\n" + self._get_startup_time_config_message(startup_time, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
                else:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.STARTUP_TIME_CONFIG,
                        message=f"未能识别要修改的参数。\n\n" + self._get_startup_time_config_message(startup_time, available_channels) + "\n请明确说明要修改的参数。",
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
            elif action in ['返回上一步', '上一步', '返回', '返回上一级', '返回上一页']:
                # 返回上一步：时间（基准时刻）配置
                session['state'] = ConfigState.TIME_BASE_CONFIG
                time_base = params.setdefault('time_base', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.TIME_BASE_CONFIG,
                    message=self._get_time_base_config_message(time_base, available_channels),
                    suggested_actions=['确认', '下一步'],
                    current_params=params
                )
            elif action in ['确认', '下一步', '下一步骤', '继续']:
                # 进入下一步：点火时间配置
                # 在切换步骤前保存当前步骤的配置
                self._save_function_calc_config_to_json(session, params)
                session['state'] = ConfigState.IGNITION_TIME_CONFIG
                ignition_time = params.setdefault('ignition_time', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.IGNITION_TIME_CONFIG,
                    message=self._get_ignition_time_config_message(ignition_time, available_channels),
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            else:
                return create_response(
                    session_id=session_id,
                    state=ConfigState.STARTUP_TIME_CONFIG,
                    message=self._get_startup_time_config_message(startup_time, available_channels) + "\n您可以使用自然语言修改参数，例如：'把阈值改为150'、'修改统计方法为最大值'。",
                        suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
        
        elif current_state == ConfigState.IGNITION_TIME_CONFIG:
            # 配置"点火时间"
            ignition_time = params.setdefault('ignition_time', {})
            available_channels = params.get('availableChannels', [])
            
            # 检查是否尝试修改不可修改的参数（type/计算类型）
            if action and ('计算类型' in action or 'type' in action.lower() or ('类型' in action and ('修改' in action or '改为' in action or '改成' in action))):
                return create_response(
                    session_id=session_id,
                    state=ConfigState.IGNITION_TIME_CONFIG,
                    message=f"计算类型（差值计算）是不可修改的参数。\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels) + "\n您可以修改其他参数，例如：监控通道、持续时长、判断依据、阈值。",
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            
            if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                field_map = {'持续时长': 'duration', '判断依据': 'logic', '阈值': 'threshold', '监控通道': 'channel'}
                action_for_match = action
                
                if '监控通道' in action_for_match or '通道' in action_for_match or 'channel' in action_for_match.lower():
                    new_channel = self._match_channel_name(value, action_for_match, available_channels)
                    if new_channel:
                        ignition_time['channel'] = new_channel
                        params['ignition_time'] = ignition_time
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.IGNITION_TIME_CONFIG,
                            message=f"已更改监控通道为 {new_channel}。\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels),
                            suggested_actions=['返回上一步', '下一步'],
                            current_params=params
                        )
                    else:
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.IGNITION_TIME_CONFIG,
                            message=f"未能识别您要选择的通道。可选通道：{', '.join(available_channels)}\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels) + "\n请明确指定通道名。",
                            suggested_actions=['返回上一步', '下一步'],
                            current_params=params
                        )
                
                field_updated = False
                for k, v in field_map.items():
                    if k == '判断依据':
                        matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                    else:
                        matched = k in action_for_match
                    
                    if matched:
                        extracted_value = None
                        if value is not None:
                            extracted_value = value
                        else:
                            extracted_value = self._extract_value_from_action(action_for_match, v)
                        
                        if extracted_value is not None:
                            if v == 'duration':
                                if extracted_value < 0.1 or extracted_value > 50:
                                    return create_response(
                                        session_id=session_id,
                                        state=ConfigState.IGNITION_TIME_CONFIG,
                                        message=f"持续时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels),
                                        suggested_actions=['返回上一步', '下一步'],
                                        current_params=params
                                    )
                            ignition_time[v] = extracted_value
                            field_updated = True
                            break
                
                if field_updated:
                    params['ignition_time'] = ignition_time
                    self._save_function_calc_config_to_json(session, params)
                    field_name = None
                    for k in field_map.keys():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_name = k
                                break
                        elif k in action_for_match:
                            field_name = k
                            break
                    field_name = field_name or '参数'
                    field_key = None
                    for k, v in field_map.items():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_key = v
                                break
                        elif k in action_for_match:
                            field_key = v
                            break
                    actual_value = value if value is not None else (ignition_time.get(field_key) if field_key else None)
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.IGNITION_TIME_CONFIG,
                        message=f"已更改{field_name}为{actual_value}。\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
                else:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.IGNITION_TIME_CONFIG,
                        message=f"未能识别要修改的参数。\n\n" + self._get_ignition_time_config_message(ignition_time, available_channels) + "\n请明确说明要修改的参数。",
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
            elif action in ['返回上一步', '上一步', '返回', '返回上一级', '返回上一页']:
                # 返回上一步：启动时间配置
                session['state'] = ConfigState.STARTUP_TIME_CONFIG
                startup_time = params.setdefault('startup_time', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.STARTUP_TIME_CONFIG,
                    message=self._get_startup_time_config_message(startup_time, available_channels),
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            elif action in ['确认', '下一步', '下一步骤', '继续']:
                # 在切换步骤前保存当前步骤的配置
                self._save_function_calc_config_to_json(session, params)
                # 检查是否有Ng和Np通道
                channel_check = self._check_channels(available_channels)
                has_ng = channel_check['has_ng']
                has_np = channel_check['has_np']
                
                # 如果缺少Ng和Np，提示并允许完成配置
                if not has_ng and not has_np:
                    session['state'] = ConfigState.CONFIRMATION
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.CONFIRMATION,
                        message="上传的文件中缺少Ng和Np通道。\n\nNg余转时间配置需要使用Ng通道，Np余转时间配置需要使用Np通道。\n\n由于缺少这些通道，无法完成功能计算的完整配置。\n\n现在可以点击上方完成配置生成报表。",
                        suggested_actions=['返回上一步'],
                        current_params=params
                    )
                
                # 如果只缺少Ng，提示没有Ng，允许继续到Np配置阶段
                if not has_ng:
                    # 虽然缺少Ng，但允许继续到Np配置（跳过Ng配置）
                    session['state'] = ConfigState.RUNDOWN_NP_CONFIG
                    rundown_np = params.setdefault('rundown_np', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NP_CONFIG,
                        message="上传的文件中缺少Ng通道。\n\nNg余转时间配置需要使用Ng通道，由于缺少此通道，将跳过Ng余转时间配置。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels),
                        suggested_actions=['返回上一步', '确认生成'],
                        current_params=params
                    )
                
                # 正常情况：有Ng，进入Ng余转时间配置
                session['state'] = ConfigState.RUNDOWN_NG_CONFIG
                rundown_ng = params.setdefault('rundown_ng', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NG_CONFIG,
                    message=self._get_rundown_ng_config_message(rundown_ng, available_channels),
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            else:
                return create_response(
                    session_id=session_id,
                    state=ConfigState.IGNITION_TIME_CONFIG,
                    message=self._get_ignition_time_config_message(ignition_time, available_channels) + "\n您可以使用自然语言修改参数，例如：'把阈值改为500'、'设置持续时长为10秒'。",
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
        
        elif current_state == ConfigState.RUNDOWN_NG_CONFIG:
            # 配置"Ng余转时间"
            rundown_ng = params.setdefault('rundown_ng', {})
            available_channels = params.get('availableChannels', [])
            
            # 强制设置为Ng通道（从availableChannels中找到匹配的Ng通道，大小写不敏感）
            ng_channel = None
            if available_channels:
                for channel in available_channels:
                    if channel.lower() == 'ng':
                        ng_channel = channel
                        break
            if ng_channel:
                rundown_ng['channel'] = ng_channel
            
            # 检查是否尝试修改不可修改的参数（channel/监控通道）
            if action and ('监控通道' in action or '通道' in action or 'channel' in action.lower()) and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NG_CONFIG,
                    message=f"Ng余转时间的监控通道固定为Ng，不可修改。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels) + "\n您可以修改其他参数，例如：统计方法、持续时长、判断依据、高阈值、低阈值。",
                    suggested_actions=[],
                    current_params=params
                )
            
            if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                field_map = {'统计方法': 'statistic', '持续时长': 'duration', '判断依据': 'logic', '阈值': 'threshold', '高阈值': 'threshold1', '低阈值': 'threshold2'}
                action_for_match = action
                
                # 优先处理高阈值和低阈值（需要在阈值之前匹配）
                if '高阈值' in action_for_match or 'T1' in action_for_match.upper():
                    extracted_value = None
                    if value is not None:
                        extracted_value = value
                    else:
                        extracted_value = self._extract_value_from_action(action_for_match, 'threshold1')
                    if extracted_value is not None:
                        rundown_ng['threshold1'] = extracted_value
                        params['rundown_ng'] = rundown_ng
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.RUNDOWN_NG_CONFIG,
                            message=f"已更改高阈值为 {extracted_value}。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels),
                            suggested_actions=[],
                            current_params=params
                        )
                
                if '低阈值' in action_for_match or 'T2' in action_for_match.upper():
                    extracted_value = None
                    if value is not None:
                        extracted_value = value
                    else:
                        extracted_value = self._extract_value_from_action(action_for_match, 'threshold2')
                    if extracted_value is not None:
                        rundown_ng['threshold2'] = extracted_value
                        params['rundown_ng'] = rundown_ng
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.RUNDOWN_NG_CONFIG,
                            message=f"已更改低阈值为 {extracted_value}。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels),
                            suggested_actions=[],
                            current_params=params
                        )
                
                field_updated = False
                for k, v in field_map.items():
                    if k == '判断依据':
                        matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                    elif k in ['高阈值', '低阈值']:
                        # 高阈值和低阈值已经在上面处理了，跳过
                        continue
                    else:
                        matched = k in action_for_match
                    
                    if matched:
                        extracted_value = None
                        if value is not None:
                            extracted_value = value
                        else:
                            extracted_value = self._extract_value_from_action(action_for_match, v)
                        
                        if extracted_value is not None:
                            if v == 'duration':
                                if extracted_value < 0.1 or extracted_value > 50:
                                    return create_response(
                                        session_id=session_id,
                                        state=ConfigState.RUNDOWN_NG_CONFIG,
                                        message=f"持续时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels),
                                        suggested_actions=['返回上一步', '下一步'],
                                        current_params=params
                                    )
                            # 如果用户只说"阈值"而没有明确说高阈值或低阈值，默认处理为高阈值（threshold1）
                            if v == 'threshold' and '阈值' in action_for_match and '高' not in action_for_match and '低' not in action_for_match:
                                rundown_ng['threshold1'] = extracted_value
                            else:
                                rundown_ng[v] = extracted_value
                            field_updated = True
                            break
                
                if field_updated:
                    params['rundown_ng'] = rundown_ng
                    self._save_function_calc_config_to_json(session, params)
                    field_name = None
                    for k in field_map.keys():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_name = k
                                break
                        elif k in action_for_match:
                            field_name = k
                            break
                    field_name = field_name or '参数'
                    field_key = None
                    for k, v in field_map.items():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_key = v
                                break
                        elif k in action_for_match:
                            field_key = v
                            break
                    actual_value = value if value is not None else (rundown_ng.get(field_key) if field_key else None)
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NG_CONFIG,
                        message=f"已更改{field_name}为{actual_value}。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
                else:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NG_CONFIG,
                        message=f"未能识别要修改的参数。\n\n" + self._get_rundown_ng_config_message(rundown_ng, available_channels) + "\n请明确说明要修改的参数。",
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
            elif action in ['返回上一步', '上一步', '返回', '返回上一级', '返回上一页']:
                # 返回上一步：点火时间配置
                session['state'] = ConfigState.IGNITION_TIME_CONFIG
                ignition_time = params.setdefault('ignition_time', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.IGNITION_TIME_CONFIG,
                    message=self._get_ignition_time_config_message(ignition_time, available_channels),
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
            elif action in ['确认', '下一步', '下一步骤', '继续']:
                # 在切换步骤前保存当前步骤的配置
                self._save_function_calc_config_to_json(session, params)
                # 检查是否有Np通道
                channel_check = self._check_channels(available_channels)
                has_np = channel_check['has_np']
                
                # 如果缺少Np，提示并允许完成配置
                if not has_np:
                    session['state'] = ConfigState.CONFIRMATION
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.CONFIRMATION,
                        message="上传的文件中缺少Np通道。\n\nNp余转时间配置需要使用Np通道，由于缺少此通道，无法完成Np余转时间配置。\n\n现在可以点击上方完成配置生成报表。",
                        suggested_actions=['返回上一步'],
                        current_params=params
                    )
                
                # 正常情况：有Np，进入Np余转时间配置
                session['state'] = ConfigState.RUNDOWN_NP_CONFIG
                rundown_np = params.setdefault('rundown_np', {})
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NP_CONFIG,
                    message=self._get_rundown_np_config_message(rundown_np, available_channels),
                    suggested_actions=['返回上一步', '确认生成'],
                    current_params=params
                )
            else:
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NG_CONFIG,
                    message=self._get_rundown_ng_config_message(rundown_ng, available_channels) + "\n您可以使用自然语言修改参数，例如：'把阈值改为100'、'修改统计方法为最小值'。",
                    suggested_actions=['返回上一步', '下一步'],
                    current_params=params
                )
        
        elif current_state == ConfigState.RUNDOWN_NP_CONFIG:
            # 配置"Np余转时间"
            rundown_np = params.setdefault('rundown_np', {})
            available_channels = params.get('availableChannels', [])
            
            # 强制设置为Np通道（从availableChannels中找到匹配的Np通道，大小写不敏感）
            np_channel = None
            if available_channels:
                for channel in available_channels:
                    if channel.lower() == 'np':
                        np_channel = channel
                        break
            if np_channel:
                rundown_np['channel'] = np_channel
            
            # 检查是否尝试修改不可修改的参数（channel/监控通道）
            if action and ('监控通道' in action or '通道' in action or 'channel' in action.lower()) and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NP_CONFIG,
                    message=f"Np余转时间的监控通道固定为Np，不可修改。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels) + "\n您可以修改其他参数，例如：统计方法、持续时长、判断依据、高阈值、低阈值。",
                    suggested_actions=['返回上一步', '确认生成'],
                    current_params=params
                )
            
            if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                field_map = {'统计方法': 'statistic', '持续时长': 'duration', '判断依据': 'logic', '阈值': 'threshold', '高阈值': 'threshold1', '低阈值': 'threshold2'}
                action_for_match = action
                
                # 优先处理高阈值和低阈值（需要在阈值之前匹配）
                if '高阈值' in action_for_match or 'T1' in action_for_match.upper():
                    extracted_value = None
                    if value is not None:
                        extracted_value = value
                    else:
                        extracted_value = self._extract_value_from_action(action_for_match, 'threshold1')
                    if extracted_value is not None:
                        rundown_np['threshold1'] = extracted_value
                        params['rundown_np'] = rundown_np
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.RUNDOWN_NP_CONFIG,
                            message=f"已更改高阈值为 {extracted_value}。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels),
                            suggested_actions=['返回上一步', '确认生成'],
                            current_params=params
                        )
                
                if '低阈值' in action_for_match or 'T2' in action_for_match.upper():
                    extracted_value = None
                    if value is not None:
                        extracted_value = value
                    else:
                        extracted_value = self._extract_value_from_action(action_for_match, 'threshold2')
                    if extracted_value is not None:
                        rundown_np['threshold2'] = extracted_value
                        params['rundown_np'] = rundown_np
                        self._save_function_calc_config_to_json(session, params)
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.RUNDOWN_NP_CONFIG,
                            message=f"已更改低阈值为 {extracted_value}。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels),
                            suggested_actions=['返回上一步', '确认生成'],
                            current_params=params
                        )
                
                field_updated = False
                for k, v in field_map.items():
                    if k == '判断依据':
                        matched = '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match
                    elif k in ['高阈值', '低阈值']:
                        # 高阈值和低阈值已经在上面处理了，跳过
                        continue
                    else:
                        matched = k in action_for_match
                    
                    if matched:
                        extracted_value = None
                        if value is not None:
                            extracted_value = value
                        else:
                            extracted_value = self._extract_value_from_action(action_for_match, v)
                        
                        if extracted_value is not None:
                            if v == 'duration':
                                if extracted_value < 0.1 or extracted_value > 50:
                                    return create_response(
                                        session_id=session_id,
                                        state=ConfigState.RUNDOWN_NP_CONFIG,
                                        message=f"持续时长必须在0.1s~50s之间，您输入的值为{extracted_value}。请重新输入。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels),
                                        suggested_actions=['返回上一步', '确认生成'],
                                        current_params=params
                                    )
                            # 如果用户只说"阈值"而没有明确说高阈值或低阈值，默认处理为高阈值（threshold1）
                            if v == 'threshold' and '阈值' in action_for_match and '高' not in action_for_match and '低' not in action_for_match:
                                rundown_np['threshold1'] = extracted_value
                            else:
                                rundown_np[v] = extracted_value
                            field_updated = True
                            break
                
                if field_updated:
                    params['rundown_np'] = rundown_np
                    self._save_function_calc_config_to_json(session, params)
                    field_name = None
                    for k in field_map.keys():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_name = k
                                break
                        elif k in action_for_match:
                            field_name = k
                            break
                    field_name = field_name or '参数'
                    field_key = None
                    for k, v in field_map.items():
                        if k == '判断依据':
                            if '判断依据' in action_for_match or '逻辑' in action_for_match or '判据' in action_for_match:
                                field_key = v
                                break
                        elif k in action_for_match:
                            field_key = v
                            break
                    actual_value = value if value is not None else (rundown_np.get(field_key) if field_key else None)
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NP_CONFIG,
                        message=f"已更改{field_name}为{actual_value}。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels),
                        suggested_actions=['返回上一步', '确认生成'],
                        current_params=params
                    )
                else:
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NP_CONFIG,
                        message=f"未能识别要修改的参数。\n\n" + self._get_rundown_np_config_message(rundown_np, available_channels) + "\n请明确说明要修改的参数。",
                        suggested_actions=['返回上一步', '确认生成'],
                        current_params=params
                    )
            elif action in ['返回上一步', '上一步', '返回', '返回上一级', '返回上一页']:
                # 返回上一步：判断是否有Ng通道，如果有则返回到RUNDOWN_NG_CONFIG，否则返回到IGNITION_TIME_CONFIG
                channel_check = self._check_channels(available_channels)
                has_ng = channel_check['has_ng']
                
                if has_ng:
                    # 有Ng通道，返回到Ng余转时间配置
                    session['state'] = ConfigState.RUNDOWN_NG_CONFIG
                    rundown_ng = params.setdefault('rundown_ng', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NG_CONFIG,
                        message=self._get_rundown_ng_config_message(rundown_ng, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
                else:
                    # 没有Ng通道，返回到点火时间配置
                    session['state'] = ConfigState.IGNITION_TIME_CONFIG
                    ignition_time = params.setdefault('ignition_time', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.IGNITION_TIME_CONFIG,
                        message=self._get_ignition_time_config_message(ignition_time, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
            elif action in ['确认', '下一步', '下一步骤', '继续', '确认配置', '确认生成']:
                # 进入确认状态前，保存最后一步的配置
                self._save_function_calc_config_to_json(session, params)
                session['state'] = ConfigState.CONFIRMATION
                return create_response(
                    session_id=session_id,
                    state=ConfigState.CONFIRMATION,
                    message=self.get_confirmation_message(report_type, params),
                    suggested_actions=['返回上一步'],
                    current_params=params
                )
            else:
                return create_response(
                    session_id=session_id,
                    state=ConfigState.RUNDOWN_NP_CONFIG,
                    message=self._get_rundown_np_config_message(rundown_np, available_channels) + "\n您可以使用自然语言修改参数，例如：'把阈值改为100'、'修改统计方法为最小值'。",
                    suggested_actions=['返回上一步', '确认生成'],
                    current_params=params
                )
        
        elif current_state == ConfigState.CONFIRMATION:
            if action in ['返回上一步', '上一步', '返回', '返回上一级', '返回上一页']:
                # 根据通道情况返回到合适的步骤
                available_channels = params.get('availableChannels', [])
                channel_check = self._check_channels(available_channels)
                has_ng = channel_check['has_ng']
                has_np = channel_check['has_np']
                
                # 如果有Np通道，返回到Np余转时间配置
                if has_np:
                    session['state'] = ConfigState.RUNDOWN_NP_CONFIG
                    rundown_np = params.setdefault('rundown_np', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NP_CONFIG,
                        message=self._get_rundown_np_config_message(rundown_np, available_channels),
                        suggested_actions=['返回上一步', '确认生成'],
                        current_params=params
                    )
                # 如果有Ng通道但没有Np通道，返回到Ng余转时间配置
                elif has_ng:
                    session['state'] = ConfigState.RUNDOWN_NG_CONFIG
                    rundown_ng = params.setdefault('rundown_ng', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.RUNDOWN_NG_CONFIG,
                        message=self._get_rundown_ng_config_message(rundown_ng, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
                # 如果既没有Ng也没有Np通道，返回到点火时间配置
                else:
                    session['state'] = ConfigState.IGNITION_TIME_CONFIG
                    ignition_time = params.setdefault('ignition_time', {})
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.IGNITION_TIME_CONFIG,
                        message=self._get_ignition_time_config_message(ignition_time, available_channels),
                        suggested_actions=['返回上一步', '下一步'],
                        current_params=params
                    )
            elif action == '确认生成':
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
                    
                    # 根据报表类型构建配置
                    if report_type == ReportType.STEADY_STATE:
                        report_cfg = self._build_steady_state_config(params)
                    elif report_type == ReportType.FUNCTION_CALC:
                        report_cfg = self._build_function_calc_config(params)
                    else:
                        # 其他类型暂不支持，使用空配置
                        report_cfg = {"reportConfig": {}}
                    
                    # 合并配置：保留已有信息（sourceFileId, fileId, uploadTime, channels），更新reportConfig
                    final_config = {
                        **existing_config,  # 保留已有字段
                        "reportConfig": report_cfg.get("reportConfig", {})
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
                except Exception as e:
                    logger.error(f"保存配置失败: {e}", exc_info=True)
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
            elif action == '修改配置' or action in ['返回上一步', '返回修改', '修改', '返回']:
                session['state'] = ConfigState.PARAMETER_CONFIG
                # 根据报表类型和组合逻辑，返回合适的提示信息
                if report_type == ReportType.STEADY_STATE:
                    trigger_logic = params.get('triggerLogic', {})
                    combination = trigger_logic.get('combination', 'AND')
                    last_modified = session.get('last_modified_condition', None)
                    display_channels = params.get('displayChannels', [])
                    
                    # 辅助函数：生成条件信息
                    def _msg_for_condition_helper(cond: dict, cond_name: str, display_channels: list):
                        if not cond:
                            return f"{cond_name}尚未配置。"
                        threshold = cond.get('threshold', '未设置')
                        stat_method = cond.get('statMethod', '未设置')
                        duration = cond.get('duration', '未设置')
                        monitor_channel = cond.get('monitorChannel', '未设置')
                        return f"{cond_name}当前配置：阈值={threshold}, 统计方法={stat_method}, 持续时长={duration}秒, 监控通道={monitor_channel}"
                    
                    # 根据最后修改的条件或组合逻辑，显示对应的条件信息
                    if combination == 'AND':
                        condition_to_show = last_modified if last_modified else '条件一'
                        condition = trigger_logic.get('condition1' if condition_to_show == '条件一' else 'condition2', {})
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, condition_to_show, display_channels)}\n您可以使用自然语言修改参数，例如：'把{condition_to_show}的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    elif combination == 'Cond1_Only':
                        condition = trigger_logic.get('condition1', {})
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, '条件一', display_channels)}\n您可以使用自然语言修改参数，例如：'把条件一的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    elif combination == 'Cond2_Only':
                        condition = trigger_logic.get('condition2', {})
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, '条件二', display_channels)}\n您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                else:
                    # 功能计算报表
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message="已返回配置修改状态。请修改配置参数：",
                        suggested_actions=[],
                        current_params=params
                    )
            elif action == '取消配置' or action == '取消':
                del self.sessions[session_id]
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.INITIAL,
                    message="配置已取消，回到对话模式。",
                    suggested_actions=[],
                    current_params={}
                )
        
        # 处理GENERATING状态：支持返回修改配置
        if current_state == ConfigState.GENERATING:
            # 辅助函数：生成条件信息（与PARAMETER_CONFIG状态中的定义保持一致）
            def _msg_for_condition_helper(cond: dict, cond_name: str, display_channels: list):
                statistic = cond.get('statistic', '')
                statistic_modifiable = not (cond_name == '条件二' and statistic == '变化率')
                statistic_label = f"{statistic} (不可修改)" if not statistic_modifiable else statistic
                
                return f"\n【当前为{cond_name}，参数如下】\n" \
                       f"- 监控通道: {cond.get('channel', '')} (可选通道: {', '.join(display_channels)})\n" \
                       f"- 统计方法: {statistic_label}\n" \
                       f"- 持续时长(秒): {cond.get('duration_sec', '')}\n" \
                       f"- 判断依据: {cond.get('logic', '')}\n" \
                       f"- 阈值: {cond.get('threshold', '')}"
            
            # 检查是否是明确的返回操作（允许通过自然语言返回修改配置）
            if action in ['返回上一步', '修改配置', '返回修改', '修改', '返回']:
                session['state'] = ConfigState.PARAMETER_CONFIG
                # 根据报表类型和组合逻辑，返回合适的提示信息
                if report_type == ReportType.STEADY_STATE:
                    trigger_logic = params.get('triggerLogic', {})
                    combination = trigger_logic.get('combination', 'AND')
                    last_modified = session.get('last_modified_condition', None)
                    display_channels = params.get('displayChannels', [])
                    
                    # 根据最后修改的条件或组合逻辑，显示对应的条件信息
                    if combination == 'AND':
                        condition_to_show = last_modified if last_modified else '条件一'
                        condition = trigger_logic.get('condition1' if condition_to_show == '条件一' else 'condition2', {})
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, condition_to_show, display_channels)}\n您可以使用自然语言修改参数，例如：'把{condition_to_show}的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    elif combination == 'Cond1_Only':
                        condition = trigger_logic.get('condition1', {})
                        display_channels = params.get('displayChannels', [])
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, '条件一', display_channels)}\n您可以使用自然语言修改参数，例如：'把条件一的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    elif combination == 'Cond2_Only':
                        condition = trigger_logic.get('condition2', {})
                        display_channels = params.get('displayChannels', [])
                        return create_response(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已返回配置修改状态。{_msg_for_condition_helper(condition, '条件二', display_channels)}\n您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'、'修改统计方法为最大值'。",
                            suggested_actions=[],
                            current_params=params
                        )
                else:
                    # 功能计算报表
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message="已返回配置修改状态。请修改配置参数：",
                        suggested_actions=[],  # 使用自然语言对话，不使用无法直接触发的按钮
                        current_params=params
                    )
            
            # 检查是否是修改相关的自然语言输入（包含修改关键词）
            modification_keywords = ['修改', '改为', '改成', '设置为', '设置成', '调整', '变更', 
                                   '阈值', '统计方法', '持续时长', '判断依据', '逻辑', '判据', 
                                   '监控通道', '通道', '条件一', '条件二']
            if action and any(keyword in action for keyword in modification_keywords):
                # 自动切回PARAMETER_CONFIG状态，然后递归调用自身处理修改操作
                session['state'] = ConfigState.PARAMETER_CONFIG
                # 递归调用update_config处理修改操作（此时状态已经是PARAMETER_CONFIG）
                return self.update_config(session_id, action, value, parsed_by_llm)
            
            # 如果既不是返回操作，也不是修改操作，提示用户
            return create_response(
                session_id=session_id,
                state=ConfigState.GENERATING,
                message="配置已确认，正在准备生成报表。\n如需修改配置，请直接使用自然语言修改参数，例如：'把条件一的阈值改为2000'。",
                suggested_actions=[],
                current_params=params
            )
        
        # 默认返回当前状态
        return ConfigResponse(
            session_id=session_id,
            state=current_state,
            message="请选择下一步操作：",
            suggested_actions=self.get_current_actions(current_state, report_type, params),
            current_params=params
        )
    
    def get_default_params(self, report_type: str, available_channels: Optional[List[str]] = None) -> Dict[str, Any]:
        """获取默认参数
        
        Args:
            report_type: 报表类型
            available_channels: 可用通道列表，如果提供则从中选择默认通道
        """
        if report_type == ReportType.STEADY_STATE:
            return {
                'displayChannels': [],
                'time_window': 10,
                'availableChannels': available_channels if available_channels else []
            }
        elif report_type == ReportType.FUNCTION_CALC:
            # 如果没有提供available_channels，抛出错误提示用户重新上传文件
            if not available_channels or len(available_channels) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="无法获取可用通道列表。请确保已上传数据文件，或重新上传文件。"
                )
            
            # 从available_channels中选择默认通道
            # 优先查找常见的通道名（不区分大小写）
            def find_channel(priorities: List[str]) -> str:
                """从available_channels中查找优先级最高的通道"""
                for priority in priorities:
                    for ch in available_channels:
                        if ch.lower() == priority.lower():
                            return ch
                # 如果都找不到，返回第一个通道（此时available_channels一定不为空，因为前面已检查）
                return available_channels[0]
            
            # 各步骤的默认通道选择策略
            default_ng = find_channel(['Ng', 'ng', 'NG'])
            default_np = find_channel(['Np', 'np', 'NP'])
            default_pressure = find_channel(['Pressure(kPa)', 'Pressure', 'pressure', '压力'])
            
            return {
                'availableChannels': available_channels,
                'time_base': {
                    'channel': default_ng,
                    'statistic': '平均值',
                    'duration': 1,
                    'logic': '>',
                    'threshold': 100
                },
                'startup_time': {
                    'channel': default_ng,
                    'statistic': '平均值',
                    'duration': 1,
                    'logic': '>',
                    'threshold': 100
                },
                'ignition_time': {
                    'channel': default_pressure,
                    'type': 'difference',  # 不可修改
                    'duration': 1,
                    'logic': '>',
                    'threshold': 100
                },
                'rundown_ng': {
                    'channel': default_ng,
                    'statistic': '平均值',
                    'duration': 1,
                    'threshold1': 100,
                    'threshold2': 200
                },
                'rundown_np': {
                    'channel': default_np,
                    'statistic': '平均值',
                    'duration': 1,
                    'threshold1': 100,
                    'threshold2': 200
                }
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
    
    def get_step_message(self, report_type: str, state: ConfigState, params: Optional[Dict[str, Any]] = None) -> str:
        """获取步骤消息"""
        if report_type == ReportType.STEADY_STATE:
            if state == ConfigState.DISPLAY_CHANNELS:
                return "稳态分析配置 - 第1步：选择展示通道\n\n请从检测到的通道中选择需要展示的通道。选择完成后点击'完成通道选择'。"
            elif state == ConfigState.TRIGGER_COMBO:
                return "稳态分析配置 - 第2步：选择组合逻辑\n\n系统已为您填充默认条件一/条件二，请选择使用方式：仅用条件一 / 仅用条件二 / AND。"
            elif state == ConfigState.PARAMETER_CONFIG:
                return "稳态分析配置 - 第3步：配置参数\n\n您可以修改统计方法、阈值或时间窗口，或直接确认配置。"
            elif state == ConfigState.SELECT_JUDGE_CHANNEL:
                return "稳态分析配置 - 第4步：选择判断通道\n\n请通过自然语言选择判断通道。"
        elif report_type == ReportType.FUNCTION_CALC:
            params = params or {}
            available_channels = params.get('availableChannels', [])
            channels_text = ""
            if available_channels:
                channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
            if state == ConfigState.TIME_BASE_CONFIG:
                time_base = params.get('time_base', {})
                return f"""功能计算配置 - 第1步：配置"时间"（基准时刻）
{channels_text}
【当前默认参数】：
- 监控通道: {time_base.get('channel', 'Ng')}
- 统计方法: {time_base.get('statistic', '平均值')}
- 持续时长: {time_base.get('duration', 1)}秒
- 判断依据: {time_base.get('logic', '>')}
- 阈值: {time_base.get('threshold', 100)}

说明："时间"是一个基准时刻点，用于后续计算的参考。当指定通道的统计值在持续时长内第一次满足判断条件时，记录该时刻。

您可以通过自然语言修改参数，例如：
- "监控通道改为 Np"
- "把阈值改为600"
- "统计方法改为最大值"
- "持续时长改为2秒"

修改完成后输入"确认"或"下一步"继续。"""
            elif state == ConfigState.STARTUP_TIME_CONFIG:
                startup_time = params.get('startup_time', {})
                return f"""功能计算配置 - 第2步：配置"启动时间"
{channels_text}
【当前默认参数】：
- 监控通道: {startup_time.get('channel', 'Ng')}
- 统计方法: {startup_time.get('statistic', '平均值')}
- 持续时长: {startup_time.get('duration', 1)}秒
- 判断依据: {startup_time.get('logic', '>')}
- 阈值: {startup_time.get('threshold', 100)}

说明："启动时间"是计算从启动点到基准点的相对时长。系统会找到满足条件的启动时刻点，然后计算它与"时间"（基准时刻）的差值。

您可以通过自然语言修改参数，例如：
- "监控通道改为 Np"
- "把阈值改为150"
- "确认"或"下一步"继续"""
            elif state == ConfigState.IGNITION_TIME_CONFIG:
                ignition_time = params.get('ignition_time', {})
                return f"""功能计算配置 - 第3步：配置"点火时间"
{channels_text}
【当前默认参数】：
- 监控通道: {ignition_time.get('channel', 'Pressure(kPa)')}
- 计算类型: {ignition_time.get('type', 'difference')}（差值计算）（不可修改）
- 持续时长: {ignition_time.get('duration', 1)}秒
- 判断依据: {ignition_time.get('logic', '>')}
- 阈值: {ignition_time.get('threshold', 100)}

说明："点火时间"是计算点火时刻相对于基准点的相对时长。系统会计算当前值与N秒前值的差值，当差值第一次满足条件时记录该时刻。

您可以通过自然语言修改参数，例如：
- "监控通道改为 排气温度"
- "把阈值改为600"
- "持续时长改为15秒"

注意：计算类型（差值计算）不可修改。

修改完成后输入"确认"或"下一步"继续。"""
            elif state == ConfigState.RUNDOWN_NG_CONFIG:
                rundown_ng = params.get('rundown_ng', {})
                return f"""功能计算配置 - 第4步：配置"Ng余转时间"
{channels_text}
【当前默认参数】：
- 监控通道: {rundown_ng.get('channel', 'Ng')}（不可修改）
- 统计方法: {rundown_ng.get('statistic', '平均值')}
- 持续时长: {rundown_ng.get('duration', 1)}秒
- 高阈值: {rundown_ng.get('threshold1', 100)}
- 低阈值: {rundown_ng.get('threshold2', 200)}

说明："Ng余转时间"是在降速阶段计算的，系统会找到第一次低于高阈值（T1）和第一次低于低阈值（T2）的时刻，然后计算T2-T1的时长。

您可以通过自然语言修改参数，例如：
- "高阈值改为1500"
- "低阈值改为100"

注意：监控通道固定为Ng，不可修改。

"确认"或"下一步"继续"""
            elif state == ConfigState.RUNDOWN_NP_CONFIG:
                rundown_np = params.get('rundown_np', {})
                return f"""功能计算配置 - 第5步：配置"Np余转时间"
{channels_text}
【当前默认参数】：
- 监控通道: {rundown_np.get('channel', 'Np')}（不可修改）
- 统计方法: {rundown_np.get('statistic', '平均值')}
- 持续时长: {rundown_np.get('duration', 1)}秒
- 高阈值: {rundown_np.get('threshold1', 6000)}
- 低阈值: {rundown_np.get('threshold2', 500)}

说明："Np余转时间"是在降速阶段计算的，系统会找到第一次低于高阈值（T1）和第一次低于低阈值（T2）的时刻，然后计算T2-T1的时长。

您可以通过自然语言修改参数，例如：
- "高阈值改为5000"
- "低阈值改为400"

注意：监控通道固定为Np，不可修改。

"确认"或"下一步"继续"""
        elif report_type == ReportType.STATUS_EVAL:
            if state == ConfigState.CHANNEL_SELECTION:
                return "状态评估配置 - 第1步：选择评估项目\n\n请选择需要评估的项目："
            elif state == ConfigState.PARAMETER_CONFIG:
                return "状态评估配置 - 第2步：配置参数\n\n请选择您要修改的参数："
        
        return "请选择下一步操作："
    
    def get_channel_options(self, report_type: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """获取通道选择选项"""
        if report_type == ReportType.STEADY_STATE:
            channels = (params or {}).get('availableChannels')
            if not channels or len(channels) == 0:
                # 如果没有可用通道，不返回任何建议操作
                return []
            actions = [f"选择 {c}" for c in channels]
            return actions
        return []
    
    def get_current_actions(self, state: ConfigState, report_type: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """获取当前状态的操作选项"""
        if state == ConfigState.DISPLAY_CHANNELS:
            return self.get_channel_options(report_type, params)
        elif state == ConfigState.TRIGGER_COMBO:
            return ['仅用条件一', '仅用条件二', 'AND']
        elif state == ConfigState.PARAMETER_CONFIG:
            return []  # 使用自然语言对话，不使用无法直接触发的按钮（如'修改统计方法'等）
        elif state == ConfigState.SELECT_JUDGE_CHANNEL:
            return []  # 通过自然语言选择，不使用按钮
        elif state == ConfigState.CONFIRMATION:
            return []
        elif state == ConfigState.GENERATING:
            return []  # 用户通过上方的完成配置按钮生成报表，不需要建议操作
        else:
            return []
    
    def get_confirmation_message(self, report_type: str, params: Dict[str, Any]) -> str:
        """获取确认消息（仅用于功能计算报表）"""
        if report_type != ReportType.FUNCTION_CALC:
            return f"配置确认：\n\n{params}\n\n请确认是否使用以上配置生成报表？"
        
        time_base = params.get('time_base', {})
        startup_time = params.get('startup_time', {})
        ignition_time = params.get('ignition_time', {})
        rundown_ng = params.get('rundown_ng', {})
        rundown_np = params.get('rundown_np', {})
        
        def format_config_item(item: Dict[str, Any], name: str) -> str:
            """格式化单个配置项"""
            if not item:
                return f"{name}：未设置"
            
            lines = [f"{name}："]
            if 'channel' in item:
                lines.append(f"  通道: {item['channel']}")
            if 'statistic' in item:
                lines.append(f"  统计方法: {item['statistic']}")
            if 'duration' in item:
                lines.append(f"  持续时长: {item['duration']}秒")
            if 'logic' in item:
                lines.append(f"  判断依据: {item['logic']}")
            if 'threshold' in item:
                lines.append(f"  阈值: {item['threshold']}")
            if 'threshold1' in item:
                lines.append(f"  阈值1: {item['threshold1']}")
            if 'threshold2' in item:
                lines.append(f"  阈值2: {item['threshold2']}")
            if 'type' in item:
                lines.append(f"  计算类型: {item['type']}")
            
            return '\n'.join(lines) if len(lines) > 1 else f"{name}：未设置"
        
        config_lines = ["配置确认：", ""]
        if time_base:
            config_lines.append(format_config_item(time_base, '时间（基准时刻）'))
            config_lines.append("")
        if startup_time:
            config_lines.append(format_config_item(startup_time, '启动时间'))
            config_lines.append("")
        if ignition_time:
            config_lines.append(format_config_item(ignition_time, '点火时间'))
            config_lines.append("")
        if rundown_ng:
            config_lines.append(format_config_item(rundown_ng, 'Ng余转时间'))
            config_lines.append("")
        if rundown_np:
            config_lines.append(format_config_item(rundown_np, 'Np余转时间'))
        config_lines.append("")
        
        # 移除最后一个空行
        if config_lines and config_lines[-1] == "":
            config_lines.pop()
        
        config_lines.append("\n\n请点击上方完成配置按钮进行报表生成。")
        
        return '\n'.join(config_lines)

    def _get_config_file_path(self, session: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
        """获取配置文件的路径和现有配置"""
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend 目录
        config_dir = backend_dir / "config_sessions"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # 通过file_id查找对应的JSON文件
        file_id = session.get('file_id')
        config_path = None
        existing_config = {}
        
        if file_id:
            # 查找所有JSON文件，找到fileId匹配的
            for json_file in config_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                        if cfg.get("fileId") == file_id:
                            config_path = json_file
                            existing_config = cfg
                            break
                except Exception:
                    continue
        
        # 如果没找到，尝试使用默认的 config_session.json
        if config_path is None:
            # 首先尝试查找是否有固定名称的 config_session.json
            default_path = config_dir / "config_session.json"
            if default_path.exists():
                try:
                    with open(default_path, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)
                        # 如果file_id匹配，使用它；否则仍使用这个文件
                        if not file_id or existing_config.get("fileId") == file_id:
                            config_path = default_path
                except Exception:
                    pass
        
        # 如果还是没找到，创建一个新的（使用时间戳格式，包含毫秒）
        if config_path is None:
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # 包含毫秒
            config_path = config_dir / f"{timestamp_str}.json"
            existing_config = {}
        
        # 读取现有配置（如果找到了文件但还没读取）
        if config_path.exists() and not existing_config:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            except Exception as read_err:
                logger.warning(f"读取已有配置文件失败: {read_err}")
                existing_config = {}
        
        return config_path, existing_config

    def _save_display_channels_to_json(self, session: Dict[str, Any], params: Dict[str, Any]) -> None:
        """保存displayChannels到JSON文件，按照上传文件中通道的顺序排序"""
        display_channels = params.get('displayChannels', [])
        try:
            config_path, existing_config = self._get_config_file_path(session)
            
            # 按照上传文件中的通道顺序对displayChannels进行排序
            file_channel_order = []
            if 'channels' in existing_config and isinstance(existing_config['channels'], list):
                # 从配置文件中获取通道顺序（按照文件中的顺序）
                file_channel_order = [ch.get('channel_name') for ch in existing_config['channels'] if ch.get('channel_name')]
            
            if file_channel_order:
                # 创建通道名称到索引的映射，用于排序
                channel_index_map = {name: idx for idx, name in enumerate(file_channel_order)}
                
                # 按照文件中的通道顺序排序displayChannels
                # 如果通道在文件中，按照文件顺序排序；如果不在，放在最后
                sorted_channels = sorted(
                    display_channels,
                    key=lambda ch: channel_index_map.get(ch, len(file_channel_order))
                )
                display_channels = sorted_channels
                # 更新params中的displayChannels为排序后的顺序
                params['displayChannels'] = sorted_channels
                logger.info(f"已按照文件通道顺序排序displayChannels: {display_channels}")
            
            # 更新displayChannels到reportConfig.stableState.displayChannels
            if 'reportConfig' not in existing_config:
                existing_config['reportConfig'] = {}
            if 'stableState' not in existing_config['reportConfig']:
                existing_config['reportConfig']['stableState'] = {}
            existing_config['reportConfig']['stableState']['displayChannels'] = display_channels
            
            # 如果还没有fileId，从session中获取并保存
            file_id = session.get('file_id')
            if file_id and 'fileId' not in existing_config:
                existing_config['fileId'] = file_id
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存displayChannels到: {config_path}")
        except Exception as e:
            logger.error(f"保存displayChannels到JSON文件失败: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
    
    def _save_conditions_to_json(self, session: Dict[str, Any], params: Dict[str, Any]) -> None:
        """保存conditions到JSON文件"""
        try:
            config_path, existing_config = self._get_config_file_path(session)
            
            # 逻辑值转换映射（中文转符号）
            logic_map = {
                '大于': '>',
                '小于': '<',
                '大于等于': '>=',
                '小于等于': '<=',
                '等于': '==',
                # 如果已经是符号，保持不变
                '>': '>',
                '<': '<',
                '>=': '>=',
                '<=': '<=',
                '==': '=='
            }
            
            # 构建conditions
            trigger = params.get('triggerLogic', {})
            combination = trigger.get('combination', 'AND')
            conditions: List[Dict[str, Any]] = []
            
            # 根据combination决定保存哪些条件
            if combination == 'Cond1_Only':
                # 仅用条件一
                cond1 = trigger.get('condition1', {})
                if cond1.get('enabled', True) and cond1.get('channel'):
                    logic_value = cond1.get('logic', '>')
                    # 转换逻辑值
                    logic_value = logic_map.get(logic_value, logic_value)
                    conditions.append({
                        "type": "statistic",
                        "channel": cond1.get('channel'),
                        "statistic": cond1.get('statistic', '平均值'),
                        "duration": cond1.get('duration_sec', 1),
                        "logic": logic_value,
                        "threshold": cond1.get('threshold', 0)
                    })
            elif combination == 'Cond2_Only':
                # 仅用条件二
                cond2 = trigger.get('condition2', {})
                if cond2.get('enabled', True) and cond2.get('channel'):
                    logic_value = cond2.get('logic', '<')
                    # 转换逻辑值
                    logic_value = logic_map.get(logic_value, logic_value)
                    conditions.append({
                        "type": "amplitude_change",
                        "channel": cond2.get('channel'),
                        "duration": cond2.get('duration_sec', 10),
                        "logic": logic_value,
                        "threshold": cond2.get('threshold', 0)
                    })
            elif combination == 'AND':
                # 同时使用条件一和条件二
                cond1 = trigger.get('condition1', {})
                if cond1.get('enabled', True) and cond1.get('channel'):
                    logic_value = cond1.get('logic', '>')
                    # 转换逻辑值
                    logic_value = logic_map.get(logic_value, logic_value)
                    conditions.append({
                        "type": "statistic",
                        "channel": cond1.get('channel'),
                        "statistic": cond1.get('statistic', '平均值'),
                        "duration": cond1.get('duration_sec', 1),
                        "logic": logic_value,
                        "threshold": cond1.get('threshold', 0)
                    })
                cond2 = trigger.get('condition2', {})
                if cond2.get('enabled', True) and cond2.get('channel'):
                    logic_value = cond2.get('logic', '<')
                    # 转换逻辑值
                    logic_value = logic_map.get(logic_value, logic_value)
                    conditions.append({
                        "type": "amplitude_change",
                        "channel": cond2.get('channel'),
                        "duration": cond2.get('duration_sec', 10),
                        "logic": logic_value,
                        "threshold": cond2.get('threshold', 0)
                    })
            
            # 更新conditions到reportConfig.stableState.conditions
            if 'reportConfig' not in existing_config:
                existing_config['reportConfig'] = {}
            if 'stableState' not in existing_config['reportConfig']:
                existing_config['reportConfig']['stableState'] = {}
            existing_config['reportConfig']['stableState']['conditions'] = conditions
            # 转换combination格式（Cond1_Only -> Cond1_Only, AND -> AND等，保持原样）
            existing_config['reportConfig']['stableState']['conditionLogic'] = combination
            
            # 如果还没有fileId，从session中获取并保存
            file_id = session.get('file_id')
            if file_id and 'fileId' not in existing_config:
                existing_config['fileId'] = file_id
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存conditions到: {config_path}")
        except Exception as e:
            logger.error(f"保存conditions到JSON文件失败: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
    
    def _get_time_base_config_message(self, time_base: Dict[str, Any], available_channels: Optional[List[str]] = None) -> str:
        """生成时间（基准时刻）配置消息"""
        channels_text = ""
        if available_channels:
            channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
        return f"""功能计算配置 - 第1步：配置"时间"（基准时刻）
{channels_text}
【当前参数】：
- 监控通道: {time_base.get('channel', 'Ng')}
- 统计方法: {time_base.get('statistic', '平均值')}
- 持续时长: {time_base.get('duration', 1)}秒
- 判断依据: {time_base.get('logic', '>')}
- 阈值: {time_base.get('threshold', 100)}

说明："时间"是一个基准时刻点，用于后续计算的参考。当指定通道的统计值在持续时长内第一次满足判断条件时，记录该时刻。

您可以通过自然语言修改参数，例如：
- "监控通道改为 Np"
- "把阈值改为600"
- "统计方法改为最大值"
- "持续时长改为2秒"

修改完成后输入"确认"或"下一步"继续。"""
    
    def _get_startup_time_config_message(self, startup_time: Dict[str, Any], available_channels: Optional[List[str]] = None) -> str:
        """生成启动时间配置消息"""
        channels_text = ""
        if available_channels:
            channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
        return f"""功能计算配置 - 第2步：配置"启动时间"
{channels_text}
【当前参数】：
- 监控通道: {startup_time.get('channel', 'Ng')}
- 统计方法: {startup_time.get('statistic', '平均值')}
- 持续时长: {startup_time.get('duration', 1)}秒
- 判断依据: {startup_time.get('logic', '>')}
- 阈值: {startup_time.get('threshold', 100)}

说明："启动时间"是计算从启动点到基准点的相对时长。系统会找到满足条件的启动时刻点，然后计算它与"时间"（基准时刻）的差值。

您可以通过自然语言修改参数，例如：
- "监控通道改为 Np"
- "把阈值改为150"
- "统计方法改为最大值"

修改完成后输入"确认"或"下一步"继续。"""
    
    def _get_ignition_time_config_message(self, ignition_time: Dict[str, Any], available_channels: Optional[List[str]] = None) -> str:
        """生成点火时间配置消息"""
        channels_text = ""
        if available_channels:
            channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
        return f"""功能计算配置 - 第3步：配置"点火时间"
{channels_text}
【当前参数】：
- 监控通道: {ignition_time.get('channel', 'Pressure(kPa)')}
- 计算类型: {ignition_time.get('type', 'difference')}（差值计算）（不可修改）
- 持续时长: {ignition_time.get('duration', 1)}秒
- 判断依据: {ignition_time.get('logic', '>')}
- 阈值: {ignition_time.get('threshold', 100)}

说明："点火时间"是计算从点火点到基准点的相对时长。系统会找到满足条件的点火时刻点，然后计算它与"时间"（基准时刻）的差值。

您可以通过自然语言修改参数，例如：
- "监控通道改为 Np"
- "把阈值改为600"
- "持续时长改为5秒"

注意：计算类型（差值计算）不可修改。

修改完成后输入"确认"或"下一步"继续。"""
    
    def _get_rundown_ng_config_message(self, rundown_ng: Dict[str, Any], available_channels: Optional[List[str]] = None) -> str:
        """生成Ng余转时间配置消息"""
        channels_text = ""
        if available_channels:
            channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
        threshold_text = ""
        if 'threshold1' in rundown_ng or 'threshold2' in rundown_ng:
            threshold_text = f"- 高阈值: {rundown_ng.get('threshold1', 100)}\n- 低阈值: {rundown_ng.get('threshold2', 200)}\n"
        else:
            threshold_text = f"- 阈值: {rundown_ng.get('threshold', 100)}\n"
        return f"""功能计算配置 - 第4步：配置"Ng余转时间"
{channels_text}
【当前参数】：
- 监控通道: {rundown_ng.get('channel', 'Ng')}（不可修改）
- 统计方法: {rundown_ng.get('statistic', '平均值')}
- 持续时长: {rundown_ng.get('duration', 1)}秒
- 判断依据: {rundown_ng.get('logic', '>')}
{threshold_text}
说明："Ng余转时间"是在降速阶段计算的，系统会找到第一次低于高阈值（T1）和第一次低于低阈值（T2）的时刻，然后计算T2-T1的时长。

您可以通过自然语言修改参数，例如：
- "高阈值改为1500"
- "低阈值改为100"
- "统计方法改为最小值"

注意：监控通道固定为Ng，不可修改。

修改完成后输入"确认"或"下一步"继续。"""
    
    def _get_rundown_np_config_message(self, rundown_np: Dict[str, Any], available_channels: Optional[List[str]] = None) -> str:
        """生成Np余转时间配置消息"""
        channels_text = ""
        if available_channels:
            channels_text = f"\n【可用通道】：{', '.join(available_channels)}\n"
        threshold_text = ""
        if 'threshold1' in rundown_np or 'threshold2' in rundown_np:
            threshold_text = f"- 高阈值: {rundown_np.get('threshold1', 100)}\n- 低阈值: {rundown_np.get('threshold2', 200)}\n"
        else:
            threshold_text = f"- 阈值: {rundown_np.get('threshold', 100)}\n"
        return f"""功能计算配置 - 第5步：配置"Np余转时间"
{channels_text}
【当前参数】：
- 监控通道: {rundown_np.get('channel', 'Np')}（不可修改）
- 统计方法: {rundown_np.get('statistic', '平均值')}
- 持续时长: {rundown_np.get('duration', 1)}秒
- 判断依据: {rundown_np.get('logic', '>')}
{threshold_text}
说明："Np余转时间"是在降速阶段计算的，系统会找到第一次低于高阈值（T1）和第一次低于低阈值（T2）的时刻，然后计算T2-T1的时长。

您可以通过自然语言修改参数，例如：
- "高阈值改为5000"
- "低阈值改为400"
- "统计方法改为最小值"

注意：监控通道固定为Np，不可修改。

修改完成后输入"确认"继续。"""
    
    def _save_function_calc_config_to_json(self, session: Dict[str, Any], params: Dict[str, Any]) -> None:
        """保存功能计算配置到JSON文件"""
        try:
            config_path, existing_config = self._get_config_file_path(session)
            
            # 逻辑值转换映射（中文转符号）
            logic_map = {
                '大于': '>',
                '小于': '<',
                '大于等于': '>=',
                '小于等于': '<=',
                '等于': '==',
                '>': '>',
                '<': '<',
                '>=': '>=',
                '<=': '<=',
                '==': '=='
            }
            
            # 构建功能计算配置
            if 'reportConfig' not in existing_config:
                existing_config['reportConfig'] = {}
            if 'functionalCalc' not in existing_config['reportConfig']:
                existing_config['reportConfig']['functionalCalc'] = {}
            
            function_calc = existing_config['reportConfig']['functionalCalc']
            
            # 保存时间（基准时刻）配置
            time_base = params.get('time_base', {})
            if time_base:
                function_calc['time_base'] = {
                    "channel": time_base.get('channel', 'Ng'),
                    "statistic": time_base.get('statistic', '平均值'),
                    "duration": time_base.get('duration', 1),
                    "logic": logic_map.get(time_base.get('logic', '>'), '>'),
                    "threshold": time_base.get('threshold', 500)
                }
            
            # 保存启动时间配置
            startup_time = params.get('startup_time', {})
            if startup_time:
                function_calc['startup_time'] = {
                    "channel": startup_time.get('channel', 'Ng'),
                    "statistic": startup_time.get('statistic', '平均值'),
                    "duration": startup_time.get('duration', 1),
                    "logic": logic_map.get(startup_time.get('logic', '>'), '>'),
                    "threshold": startup_time.get('threshold', 100)
                }
            
            # 保存点火时间配置
            ignition_time = params.get('ignition_time', {})
            if ignition_time:
                function_calc['ignition_time'] = {
                    "channel": ignition_time.get('channel', 'Pressure(kPa)'),
                    "type": ignition_time.get('type', 'difference'),
                    "duration": ignition_time.get('duration', 10),
                    "logic": logic_map.get(ignition_time.get('logic', '>'), '>'),
                    "threshold": ignition_time.get('threshold', 500)
                }
            
            # 保存Ng余转时间配置
            rundown_ng = params.get('rundown_ng', {})
            if rundown_ng:
                function_calc['rundown_ng'] = {
                    "channel": rundown_ng.get('channel', 'Ng'),
                    "statistic": rundown_ng.get('statistic', '平均值'),
                    "duration": rundown_ng.get('duration', 1),
                    "threshold1": rundown_ng.get('threshold1', 8000),
                    "threshold2": rundown_ng.get('threshold2', 1000)
                }
            
            # 保存Np余转时间配置
            rundown_np = params.get('rundown_np', {})
            if rundown_np:
                function_calc['rundown_np'] = {
                    "channel": rundown_np.get('channel', 'Np'),
                    "statistic": rundown_np.get('statistic', '平均值'),
                    "duration": rundown_np.get('duration', 1),
                    "threshold1": rundown_np.get('threshold1', 6000),
                    "threshold2": rundown_np.get('threshold2', 500)
                }
            
            # 保存displayChannels
            display_channels = params.get('displayChannels', [])
            if display_channels:
                function_calc['displayChannels'] = display_channels
            
            # 如果还没有fileId，从session中获取并保存
            file_id = session.get('file_id')
            if file_id and 'fileId' not in existing_config:
                existing_config['fileId'] = file_id
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存功能计算配置到: {config_path}")
        except Exception as e:
            logger.error(f"保存功能计算配置到JSON文件失败: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

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
        
        def clamp_duration(value: Any) -> float:
            try:
                v = float(value)
            except Exception:
                v = 1.0
            if v < 0.1:
                return 0.1
            if v > 50:
                return 50.0
            return v
        combination = trigger.get('combination', 'AND')
        conditions: List[Dict[str, Any]] = []
        
        # 根据combination决定保存哪些条件
        if combination == 'Cond1_Only':
            # 仅用条件一
            cond1 = trigger.get('condition1', {})
            if cond1.get('enabled', True) and cond1.get('channel'):
                conditions.append({
                    "type": cond1.get('type', '统计值'),
                    "channel": cond1.get('channel'),
                    "statistic": cond1.get('statistic', '平均值'),
                    "duration": clamp_duration(cond1.get('duration_sec', 1)),
                    "logic": cond1.get('logic', '>'),
                    "threshold": cond1.get('threshold', 100)
                })
        elif combination == 'Cond2_Only':
            # 仅用条件二
            cond2 = trigger.get('condition2', {})
            if cond2.get('enabled', True) and cond2.get('channel'):
                conditions.append({
                    "type": cond2.get('type', '变化幅度'),
                    "channel": cond2.get('channel'),
                    "statistic": cond2.get('statistic', '变化率'),
                    "duration": clamp_duration(cond2.get('duration_sec', 1)),
                    "logic": cond2.get('logic', '>'),
                    "threshold": cond2.get('threshold', 100)
                })
        elif combination == 'AND':
            # 同时使用条件一和条件二
            cond1 = trigger.get('condition1', {})
            if cond1.get('enabled', True) and cond1.get('channel'):
                conditions.append({
                    "type": cond1.get('type', '统计值'),
                    "channel": cond1.get('channel'),
                    "statistic": cond1.get('statistic', '平均值'),
                    "duration": clamp_duration(cond1.get('duration_sec', 1)),
                    "logic": cond1.get('logic', '>'),
                    "threshold": cond1.get('threshold', 100)
                })
            cond2 = trigger.get('condition2', {})
            if cond2.get('enabled', True) and cond2.get('channel'):
                conditions.append({
                    "type": cond2.get('type', '变化幅度'),
                    "channel": cond2.get('channel'),
                    "statistic": cond2.get('statistic', '变化率'),
                    "duration": clamp_duration(cond2.get('duration_sec', 1)),
                    "logic": cond2.get('logic', '>'),
                    "threshold": cond2.get('threshold', 100)
                })
            
            # AND模式下，计算两个条件的displayChannels交集
            # 必须两个条件都有displayChannels，然后取交集
            cond1_display_list = cond1.get('displayChannels', [])
            cond2_display_list = cond2.get('displayChannels', [])
            cond1_display = set(cond1_display_list) if cond1_display_list else set()
            cond2_display = set(cond2_display_list) if cond2_display_list else set()
            
            # 调试日志
            logger.debug(f"AND模式 - 条件一displayChannels: {cond1_display_list}, 条件二displayChannels: {cond2_display_list}")
            logger.debug(f"AND模式 - 条件一集合: {cond1_display}, 条件二集合: {cond2_display}")
            
            if cond1_display and cond2_display:
                # 两个条件都有displayChannels，取交集
                display_channels = list(cond1_display & cond2_display)
                # 保持原始顺序（使用第一个条件的顺序）
                display_channels = [ch for ch in cond1_display_list if ch in display_channels]
                logger.debug(f"AND模式 - 交集结果: {display_channels}")
            elif not cond1_display and not cond2_display:
                # 两个条件都没有单独的displayChannels，使用全局的displayChannels
                display_channels = params.get('displayChannels', [])
                logger.debug(f"AND模式 - 使用全局displayChannels: {display_channels}")
            else:
                # 只有一个条件有displayChannels，AND模式下应该输出空列表（因为缺少另一个条件的结果）
                # 这通常不应该发生，但如果发生了，返回空列表而不是回退到单个条件
                logger.warning(f"AND模式 - 条件一displayChannels: {cond1_display_list}, 条件二displayChannels: {cond2_display_list}, 只有一个有值，返回空列表")
                display_channels = []
        else:
            # 非AND模式，使用全局displayChannels
            display_channels = params.get('displayChannels', [])
        
        return {
            "reportConfig": {
                "stableState": {
                    "displayChannels": display_channels,
                    "conditionLogic": combination,
                    "conditions": conditions
                }
            }
        }
    
    def _build_function_calc_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建功能计算配置JSON，供后续计算模块使用"""
        # 逻辑值转换映射（中文转符号）
        logic_map = {
            '大于': '>',
            '小于': '<',
            '大于等于': '>=',
            '小于等于': '<=',
            '等于': '==',
            '>': '>',
            '<': '<',
            '>=': '>=',
            '<=': '<=',
            '==': '=='
        }
        
        def clamp_duration(value: Any) -> float:
            try:
                v = float(value)
            except Exception:
                v = 1.0
            if v < 0.1:
                return 0.1
            if v > 50:
                return 50.0
            return v

        function_calc = {}
        
        # 构建时间（基准时刻）配置
        time_base = params.get('time_base', {})
        if time_base:
            function_calc['time_base'] = {
                "channel": time_base.get('channel', 'Ng'),
                "statistic": time_base.get('statistic', '平均值'),
                "duration": clamp_duration(time_base.get('duration', 1)),
                "logic": logic_map.get(time_base.get('logic', '>'), '>'),
                "threshold": time_base.get('threshold', 100)
            }
        
        # 构建启动时间配置
        startup_time = params.get('startup_time', {})
        if startup_time:
            function_calc['startup_time'] = {
                "channel": startup_time.get('channel', 'Ng'),
                "statistic": startup_time.get('statistic', '平均值'),
                "duration": clamp_duration(startup_time.get('duration', 1)),
                "logic": logic_map.get(startup_time.get('logic', '>'), '>'),
                "threshold": startup_time.get('threshold', 100)
            }
        
        # 构建点火时间配置
        ignition_time = params.get('ignition_time', {})
        if ignition_time:
            function_calc['ignition_time'] = {
                "channel": ignition_time.get('channel', 'Pressure(kPa)'),
                "type": ignition_time.get('type', 'difference'),
                "duration": clamp_duration(ignition_time.get('duration', 1)),
                "logic": logic_map.get(ignition_time.get('logic', '>'), '>'),
                "threshold": ignition_time.get('threshold', 100)
            }
        
        # 构建Ng余转时间配置
        rundown_ng = params.get('rundown_ng', {})
        if rundown_ng:
            # 强制使用Ng通道（从availableChannels中找到匹配的Ng通道，大小写不敏感）
            available_channels = params.get('availableChannels', [])
            ng_channel = 'Ng'  # 默认值
            if available_channels:
                for channel in available_channels:
                    if channel.lower() == 'ng':
                        ng_channel = channel
                        break
            
            rundown_ng_config = {
                "channel": ng_channel,  # 强制使用Ng通道
                "statistic": rundown_ng.get('statistic', '平均值'),
                "duration": clamp_duration(rundown_ng.get('duration', 1)),
            }
            # 如果有threshold，使用threshold；否则使用threshold1和threshold2
            if 'threshold' in rundown_ng:
                rundown_ng_config['threshold'] = rundown_ng.get('threshold', 100)
            else:
                if 'threshold1' in rundown_ng:
                    rundown_ng_config['threshold1'] = rundown_ng.get('threshold1', 100)
                if 'threshold2' in rundown_ng:
                    rundown_ng_config['threshold2'] = rundown_ng.get('threshold2', 200)
            function_calc['rundown_ng'] = rundown_ng_config
        
        # 构建Np余转时间配置
        rundown_np = params.get('rundown_np', {})
        if rundown_np:
            # 强制使用Np通道（从availableChannels中找到匹配的Np通道，大小写不敏感）
            available_channels = params.get('availableChannels', [])
            np_channel = 'Np'  # 默认值
            if available_channels:
                for channel in available_channels:
                    if channel.lower() == 'np':
                        np_channel = channel
                        break
            
            rundown_np_config = {
                "channel": np_channel,  # 强制使用Np通道
                "statistic": rundown_np.get('statistic', '平均值'),
                "duration": clamp_duration(rundown_np.get('duration', 1)),
            }
            # 如果有threshold，使用threshold；否则使用threshold1和threshold2
            if 'threshold' in rundown_np:
                rundown_np_config['threshold'] = rundown_np.get('threshold', 100)
            else:
                if 'threshold1' in rundown_np:
                    rundown_np_config['threshold1'] = rundown_np.get('threshold1', 100)
                if 'threshold2' in rundown_np:
                    rundown_np_config['threshold2'] = rundown_np.get('threshold2', 200)
            function_calc['rundown_np'] = rundown_np_config
        
        # 添加displayChannels
        display_channels = params.get('displayChannels', [])
        if display_channels:
            function_calc['displayChannels'] = display_channels
        
        return {
            "reportConfig": {
                "functionalCalc": function_calc
            }
        }

def detect_multiple_actions(user_input: str) -> bool:
    """
    检测用户输入是否包含多个参数修改
    
    检测规则：
    1. 包含逗号或顿号分隔符
    2. 包含多个参数关键词（通道、阈值、统计方法、持续时长、判断依据等）
    3. 包含多个数值或字符串值
    
    Args:
        user_input: 用户输入的自然语言
        
    Returns:
        True 如果检测到多个参数，False 否则
    """
    if not user_input or not user_input.strip():
        return False
    
    user_input = user_input.strip()
    
    # 检测方法1: 包含逗号或顿号分隔符
    if '，' in user_input or ',' in user_input:
        return True
    
    # 检测方法2: 统计参数关键词的数量
    param_keywords = [
        '通道', 'channel',
        '阈值', 'threshold',
        '统计方法', '统计', '方法',
        '持续时长', '持续时间', '时长',
        '判断依据', '判据', '逻辑',
        '计算类型', '类型'
    ]
    
    keyword_count = 0
    for keyword in param_keywords:
        if keyword in user_input.lower():
            keyword_count += 1
    
    # 如果包含2个或以上的参数关键词，可能是多个参数
    if keyword_count >= 2:
        # 进一步验证：检查是否有对应的值
        # 提取所有数字（可能是阈值、持续时长等）
        import re
        numbers = re.findall(r'\d+', user_input)
        # 检查是否包含统计方法的值（最大值、最小值、平均值等）
        statistic_values = ['最大', '最小', '平均', '中位']
        has_statistic_value = any(val in user_input for val in statistic_values)
        
        # 检查是否包含通道名称（如np、ng等）
        channel_keywords = ['np', 'ng', '通道']
        has_channel = any(kw in user_input.lower() for kw in channel_keywords)
        
        # 如果有关键词且（有数字 或 有统计方法值 或 有通道），很可能是多个参数
        if numbers or has_statistic_value or has_channel:
            return True
    
    return False

async def parse_config_intent_with_llm(utterance: str, current_params: dict, current_context: dict = None, force_multiple_actions: bool = False) -> dict:
    """
    用大模型解析自然语言配置意图，返回{action,value,...,error_message}
    
    Args:
        utterance: 用户输入的语句
        current_params: 当前参数配置
        current_context: 当前上下文信息，包含current_condition（"条件一"或"条件二"）
        force_multiple_actions: 如果为True，强制要求LLM识别多个参数并返回actions数组
    """
    if not utterance:
        return {}
    
    # 获取当前上下文
    current_condition = None
    current_step = None
    current_step_name = None
    if current_context:
        current_condition = current_context.get('current_condition')
        current_step = current_context.get('current_step')
        current_step_name = current_context.get('current_step_name')
    
    # 构建上下文提示
    context_hint = ""
    if current_condition:
        # 稳态参数的上下文提示
        context_hint = f"\n\n【⚠️⚠️⚠️ 非常重要】当前上下文：您正在编辑{current_condition}的参数。\n- 【⚠️⚠️⚠️ 最高优先级规则】如果用户明确说了\"条件一\"或\"条件二\"，必须无条件按照用户明确说的条件返回，绝对不能受当前上下文（current_condition）影响！例如：如果当前上下文是条件二，但用户明确说\"条件一的阈值改为2000\"，必须返回{{\"action\": \"修改条件一阈值\", \"value\": 2000}}，绝对不能返回\"修改条件二...\"！\n- 如果用户没有明确指定是\"条件一\"还是\"条件二\"，action字段中必须包含当前条件名称（{current_condition}）。\n- 例如，如果当前在编辑条件一，用户说\"把阈值改为2000\"，必须返回{{\"action\": \"修改条件一阈值\", \"value\": 2000}}，而不是{{\"action\": \"修改阈值\", \"value\": 2000}}。\n- 【关键】如果用户同时修改多个参数（使用actions数组），且没有明确指定条件，那么actions数组中的所有action都必须应用到同一个条件（{current_condition}），绝对不能混用！例如，如果current_condition='条件一'，用户说\"通道改为np，统计方法改为最大值\"，必须返回[{{\"action\": \"修改条件一监控通道\", \"value\": \"Np\"}}, {{\"action\": \"修改条件一统计方法\", \"value\": \"最大值\"}}]，绝对不能返回\"修改条件二...\"！"
    elif current_step and current_step_name:
        # 功能计算的上下文提示
        context_hint = f"\n\n【⚠️⚠️⚠️ 非常重要】当前上下文：您正在配置功能计算的\"{current_step_name}\"步骤。\n- action字段应该直接包含要修改的参数名称，不需要包含步骤名称，例如：\"修改阈值\"、\"修改监控通道\"、\"修改统计方法\"等。\n- 如果当前步骤是\"Ng余转时间\"或\"Np余转时间\"，用户说\"修改阈值\"时，需要根据上下文判断是\"高阈值\"还是\"低阈值\"。如果用户明确说\"高阈值\"或\"低阈值\"，必须返回对应的action（\"修改高阈值\"或\"修改低阈值\"）。\n- 例如，当前在配置\"Ng余转时间\"，用户说\"把高阈值改为1500\" -> {{\"action\": \"修改高阈值\", \"value\": 1500}}\n- 例如，当前在配置\"点火时间\"，用户说\"把阈值改为600\" -> {{\"action\": \"修改阈值\", \"value\": 600}}\n- 例如，当前在配置\"时间（基准时刻）\"，用户说\"修改监控通道为Ng\" -> {{\"action\": \"修改监控通道\", \"value\": \"Ng\"}}"
    
    # 如果强制要求识别多个参数，添加特别提示
    multiple_params_hint = ""
    if force_multiple_actions:
        multiple_params_hint = "\n\n【⚠️⚠️⚠️ 紧急提示】用户输入明确包含多个参数（包含逗号、顿号等分隔符），您必须返回actions数组格式，绝对不能只返回单个action！请仔细分析用户输入的每个部分，识别出所有需要修改的参数并全部返回。如果只返回一个参数，说明您的解析不完整。"
    
    # 构建更详细的prompt，帮助LLM理解用户意图
    # 如果强制要求识别多个参数，在prompt开头就强调这一点
    prompt_start = ""
    if force_multiple_actions:
        prompt_start = "【重要】用户输入包含多个参数，必须返回actions数组格式！\n\n"
    
    prompt = f"""{prompt_start}请把用户的需求转成结构化JSON指令。

当前参数配置：
{json.dumps(current_params, ensure_ascii=False, indent=2)}

用户需求：{utterance}{context_hint}{multiple_params_hint}

重要说明：
0. 【⚠️⚠️⚠️ 最高优先级规则 - 必须严格遵守】如果用户明确说了"条件一"或"条件二"（例如："条件一的..."、"条件二的..."、"把条件一..."、"修改条件二..."等），必须无条件按照用户明确说的条件返回，绝对不能受当前上下文（current_condition）影响！例如：如果当前上下文是条件二，但用户明确说"条件一的阈值改为2000"，必须返回{{"action": "修改条件一阈值", "value": 2000}}，绝对不能返回"修改条件二..."！用户明确说的条件优先级永远最高！
1. 如果用户只修改一个参数，返回格式：{{"action": "修改阈值", "value": 2000}}
2. 如果用户同时修改多个参数（用逗号、顿号、和、以及等连接），必须返回格式：{{"actions": [{{"action": "修改阈值", "value": 2000}}, {{"action": "修改统计方法", "value": "最大值"}}]}}
   - 注意：如果用户说了多个参数，必须使用actions数组，不要只返回单个action！
   - 例如："把阈值改为2000，统计方法改为最大值" -> 必须返回{{"actions": [...]}}，而不是单个{{"action": ...}}
3. action字段应该包含要修改的参数名称和操作：
   【稳态参数】（当current_condition存在时）：
   - "修改条件一阈值"（当用户说"把阈值改为2000"且当前上下文是条件一时，或用户明确说"条件一的阈值改为2000"时）
   - "修改条件二阈值"（当用户说"把阈值改为2000"且当前上下文是条件二时，或用户明确说"条件二的阈值改为2000"时）
   - "修改条件一统计方法"（当用户说"修改统计方法为最大值"且当前上下文是条件一时，或用户明确说"条件一的统计方法改为最大值"时）
   - "修改条件一监控通道"（当用户说"通道改为np"且当前上下文是条件一时，或用户明确说"条件一的通道改为np"时，注意：不要写成"修改触发逻辑通道"，应该写"修改条件一监控通道"或"修改条件一通道"）
   - "修改条件二持续时长"（当用户说"设置持续时长为5秒"且当前上下文是条件二时，或用户明确说"条件二的持续时长改为5秒"时）
   - 注意：如果当前上下文存在且用户没有明确指定条件，action中必须包含条件名称（"条件一"或"条件二"）
   - 【⚠️特别重要】如果用户同时修改多个参数（使用actions数组），且没有明确指定条件，那么actions数组中的所有action都必须应用到同一个条件（current_condition），必须保持一致！
   【功能计算】（当current_step存在时）：
   - "修改阈值"（当用户说"把阈值改为600"、"阈值改为500"等时）
   - "修改监控通道"（当用户说"通道改为Ng"、"监控通道改为Np"等时）
   - "修改统计方法"（当用户说"统计方法改为最大值"、"改为最小值"等时）
   - "修改持续时长"（当用户说"持续时长改为5秒"、"时长改为10"等时）
   - "修改判断依据"（当用户说"判断依据改为大于"、"逻辑改为小于"等时）
   - "修改高阈值"（当用户在Ng余转时间或Np余转时间步骤说"高阈值改为1500"、"T1改为1500"等时）
   - "修改低阈值"（当用户在Ng余转时间或Np余转时间步骤说"低阈值改为100"、"T2改为100"等时）
   - 注意：功能计算的action不需要包含步骤名称，直接使用参数名称即可
   - 如果用户在Ng余转时间或Np余转时间步骤只说"阈值"而没有明确说"高阈值"或"低阈值"，优先理解为"高阈值"
4. value字段应该是修改后的具体值，例如：
   - 数字值：2000、5、10等
   - 字符串值："最大值"、"平均值"、"大于"、"小于"等
   - 通道名称：需要转换为正确的格式（如"Ng"、"Np"、"Pressure(kPa)"、"Temperature(°C)"等）
   - 注意：如果用户说"判断依据改为最大值"，这里的"最大值"应该是统计方法，不是判断依据。判断依据的值应该是">"、"<"、">="、"<="等。请智能识别用户的真实意图。
5. 【重要】条件名称的优先级规则（仅适用于稳态参数）：
   - 最高优先级：如果用户明确说了"条件一"或"条件二"，必须无条件按照用户说的条件返回
   - 次优先级：如果用户没有明确指定条件，且当前上下文存在（current_condition不为空），action中必须包含当前条件的名称（"条件一"或"条件二"）
   - 例如：当前上下文是条件二，用户说"把阈值改为2000"（未明确指定条件） -> {{"action": "修改条件二阈值", "value": 2000}}
   - 例如：当前上下文是条件二，用户明确说"条件一的阈值改为2000" -> {{"action": "修改条件一阈值", "value": 2000}}（必须按照用户明确说的条件返回！）
6. 如果无法识别用户意图，返回空对象{{}}

示例（稳态参数 - 单个参数，假设当前上下文是条件一）：
- 用户说"把条件一的阈值改为2000" -> {{"action": "修改条件一阈值", "value": 2000}}（用户明确说了条件一）
- 用户说"把阈值改为2000"（未明确指定条件） -> {{"action": "修改条件一阈值", "value": 2000}}（根据当前上下文）
- 用户说"修改统计方法为最大值"（未明确指定条件） -> {{"action": "修改条件一统计方法", "value": "最大值"}}（根据当前上下文）
- 【重要示例】假设当前上下文是条件二，用户明确说"条件一的判断依据改为最大值" -> {{"action": "修改条件一统计方法", "value": "最大值"}}（注意：1. 用户明确说了"条件一"，必须返回"修改条件一..."，不能受当前上下文影响；2. "最大值"是统计方法，不是判断依据，请智能识别用户真实意图）

示例（稳态参数 - 多个参数，假设当前上下文是条件一）：
- 用户说"把阈值改为2000，统计方法改为最大值"（未明确指定条件） -> {{"actions": [{{"action": "修改条件一阈值", "value": 2000}}, {{"action": "修改条件一统计方法", "value": "最大值"}}]}}（根据当前上下文）
- 用户说"条件一的阈值改成1000，持续时长改为5秒" -> {{"actions": [{{"action": "修改条件一阈值", "value": 1000}}, {{"action": "修改条件一持续时长", "value": 5}}]}}
- 用户说"阈值2000，统计方法最大值"（未明确指定条件） -> {{"actions": [{{"action": "修改条件一阈值", "value": 2000}}, {{"action": "修改条件一统计方法", "value": "最大值"}}]}}（根据当前上下文）
- 用户说"通道改为np，统计方法改为最大值"（未明确指定条件） -> {{"actions": [{{"action": "修改条件一监控通道", "value": "Np"}}, {{"action": "修改条件一统计方法", "value": "最大值"}}]}}（根据当前上下文，两个action必须都是条件一）
- 【⚠️重要】如果用户没有明确指定条件，actions数组中的所有action都必须应用到同一个条件（current_condition），不能混用！例如，如果current_condition='条件一'，用户说"通道改为np，统计方法改为最大值"，必须返回两个都是"修改条件一..."的action，不能返回"修改条件二..."。

示例（功能计算 - 单个参数，假设当前在配置"点火时间"）：
- 用户说"把阈值改为600" -> {{"action": "修改阈值", "value": 600}}
- 用户说"修改监控通道为Ng" -> {{"action": "修改监控通道", "value": "Ng"}}
- 用户说"统计方法改为最大值" -> {{"action": "修改统计方法", "value": "最大值"}}
- 用户说"持续时长改为5秒" -> {{"action": "修改持续时长", "value": 5}}
- 用户说"判断依据改为大于" -> {{"action": "修改判断依据", "value": ">"}}

示例（功能计算 - Ng余转时间/Np余转时间，假设当前在配置"Ng余转时间"）：
- 用户说"把高阈值改为1500" -> {{"action": "修改高阈值", "value": 1500}}
- 用户说"低阈值改为100" -> {{"action": "修改低阈值", "value": 100}}
- 用户说"阈值改为1500"（未明确说高阈值还是低阈值） -> {{"action": "修改高阈值", "value": 1500}}（优先理解为高阈值）
- 用户说"T1改为1500" -> {{"action": "修改高阈值", "value": 1500}}（T1表示高阈值）
- 用户说"T2改为100" -> {{"action": "修改低阈值", "value": 100}}（T2表示低阈值）

示例（功能计算 - 多个参数，假设当前在配置"时间（基准时刻）"）：
- 用户说"把阈值改为600，统计方法改为最大值" -> {{"actions": [{{"action": "修改阈值", "value": 600}}, {{"action": "修改统计方法", "value": "最大值"}}]}}
- 用户说"通道改为Ng，持续时长改为5秒" -> {{"actions": [{{"action": "修改监控通道", "value": "Ng"}}, {{"action": "修改持续时长", "value": 5}}]}}

示例（导航操作 - 这些操作用于进入下一个步骤或确认当前步骤）：
- 用户说"下一步" -> {{"action": "下一步", "value": null}}
- 用户说"继续" -> {{"action": "继续", "value": null}}
- 用户说"确认" -> {{"action": "确认", "value": null}}
- 用户说"确认配置" -> {{"action": "确认配置", "value": null}}
- 用户说"完成" -> {{"action": "完成", "value": null}}

【⚠️重要】如果用户只说"下一步"、"继续"、"确认"、"完成"等导航操作，必须返回对应的action，绝对不能解析为参数修改操作（如"修改监控通道"）！例如，如果用户说"下一步"，必须返回{{"action": "下一步", "value": null}}，绝对不能返回{{"action": "修改监控通道", "value": "Np"}}等参数修改操作！

请返回JSON格式："""
    
    try:
        config = settings.get_llm_config()
        logger.debug(f"使用LLM提供商: {config.provider}, 模型: {config.model_name}, Base URL: {config.base_url}")
        
        # 检查配置是否有效
        if not config.api_key:
            error_msg = f"LLM提供商 {config.provider} 的API密钥未配置"
            logger.error(error_msg)
            return {"error_message": error_msg}
        
        async with LLMClient(config) as client:
            messages = [
                Message(role="system", content="你是报表参数助手，请理解用户自然语言需求，转成可自动调用后端配置指令结构。你返回的JSON必须严格符合格式要求。"),
                Message(role="user", content=prompt),
            ]
            resp = await client.chat_completion(messages)
            content = resp.get_content().strip().replace('，', ',')
            
            # 尝试提取JSON（可能被markdown代码块包裹）
            import re
            # 先尝试移除markdown代码块标记
            if '```json' in content or '```' in content:
                # 移除代码块标记
                content = re.sub(r'```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```', '', content)
                content = content.strip()
            
            # 使用计数括号的方法提取完整的JSON对象
            json_start = content.find('{')
            if json_start != -1:
                bracket_count = 0
                json_end = json_start
                for i in range(json_start, len(content)):
                    if content[i] == '{':
                        bracket_count += 1
                    elif content[i] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_end = i + 1
                            break
                if bracket_count == 0:
                    content = content[json_start:json_end]
                else:
                    # 如果括号未闭合，保留从开始到结尾的内容（后续会尝试修复）
                    content = content[json_start:]
            else:
                # 如果没有找到{，尝试查找[开头的数组
                json_start = content.find('[')
                if json_start != -1:
                    bracket_count = 0
                    json_end = json_start
                    for i in range(json_start, len(content)):
                        if content[i] == '[':
                            bracket_count += 1
                        elif content[i] == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                json_end = i + 1
                                break
                    if bracket_count == 0:
                        content = content[json_start:json_end]
            
            # 尝试修复不完整的JSON（添加缺失的闭合括号）
            try:
                res = json.loads(content)
            except json.JSONDecodeError as e:
                # 尝试修复常见的JSON不完整问题
                content_original = content
                # 检查是否缺少闭合括号
                open_braces = content.count('{')
                close_braces = content.count('}')
                open_brackets = content.count('[')
                close_brackets = content.count(']')
                
                # 尝试修复缺失的闭合括号
                if open_braces > close_braces:
                    content += '}' * (open_braces - close_braces)
                if open_brackets > close_brackets:
                    content += ']' * (open_brackets - close_brackets)
                
                try:
                    res = json.loads(content)
                    logger.debug(f"JSON修复成功，原始长度: {len(content_original)}, 修复后长度: {len(content)}")
                except json.JSONDecodeError:
                    # 如果修复后仍然失败，记录详细错误信息
                    error_msg = f"LLM返回内容JSON解析失败: {type(e).__name__}: {str(e)}, 原始内容: {content_original[:500]}"
                    logger.warning(error_msg)
                    logger.debug(f"完整内容: {content_original}")
                    return {"error_message": error_msg}
            
            if isinstance(res, dict):
                return res
            return {}
    except Exception as e:
        # 捕获所有LLM调用异常（网络错误、502、超时、认证失败等）
        import traceback
        error_details = traceback.format_exc()
        
        # 检查是否是重试失败的错误（从错误信息中判断）
        error_str = str(e)
        if "已重试" in error_str or "retries" in error_str.lower():
            error_msg = f"LLM服务暂时不可用（已自动重试失败），将使用fallback规则解析"
            logger.warning(f"{error_msg}, utterance: {utterance}, error: {error_str}")
        else:
            error_msg = f"LLM调用失败: {error_str}"
            logger.warning(f"{error_msg}, utterance: {utterance}")
        logger.debug(f"完整错误堆栈:\n{error_details}")
        return {"error_message": error_msg}

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

@router.post("/report_config/update", response_model=ConfigResponse, summary="更新报表配置（支持自然语言")
async def update_report_config(request: ConfigUpdateRequest):
    """
    更新报表配置（支持自然语言配置）\n\n- session_id: 会话ID\n- action: 操作类型\n- value: 操作值（可选）\n- utterance: (可选) 自然语言配置语句
    """
    try:
        parsed_by_llm = False  # 标记是否由大模型解析
        
        # 如果带自然语言指令，优先生成为action/value
        llm_error_message = None
        if request.utterance:
            session = config_manager.sessions.get(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            params = session.get("params", {})
            
            # 构建当前上下文信息
            current_context = {}
            trigger_logic = params.get('triggerLogic', {})
            combination = trigger_logic.get('combination', 'AND')
            
            # 优先级：1. last_modified_condition（上一次修改的条件）
            #        2. 默认条件（根据combination判断）
            last_modified_condition = session.get('last_modified_condition')
            
            if last_modified_condition:
                # 如果记录的最后一次操作的条件存在，优先使用它
                current_context['current_condition'] = last_modified_condition
            else:
                # 否则，根据combination判断默认条件
                if combination == 'AND':
                    # AND模式下，默认条件一
                    current_context['current_condition'] = '条件一'
                elif combination == 'Cond1_Only':
                    current_context['current_condition'] = '条件一'
                elif combination == 'Cond2_Only':
                    current_context['current_condition'] = '条件二'
            
            intent = await parse_config_intent_with_llm(request.utterance, params, current_context)
            
            # 检查是否有错误信息
            if "error_message" in intent:
                llm_error_message = intent["error_message"]
                logger.warning(f"[LLM调用异常] {llm_error_message}")
            
            # 判断LLM解析是否成功：支持单个操作和多个操作
            if "actions" in intent and isinstance(intent["actions"], list) and len(intent["actions"]) > 0:
                # 多个参数更新：循环处理每个操作
                parsed_by_llm = True
                logger.info(f"[LLM解析成功-多参数] utterance: {request.utterance}, actions数量: {len(intent['actions'])}")
                response = None
                success_count = 0
                failed_actions = []
                success_details = []  # 收集成功修改的详细信息
                for i, action_item in enumerate(intent["actions"]):
                    action = action_item.get("action")
                    value = action_item.get("value")
                    if action and action.strip():
                        logger.info(f"[处理多参数更新 {i+1}/{len(intent['actions'])}] action: {action}, value: {value}")
                        try:
                            single_response = config_manager.update_config(request.session_id, action, value, parsed_by_llm=parsed_by_llm)
                            # 保留最后一个response用于返回（包含最新的状态和参数）
                            response = single_response
                            success_count += 1
                            # 提取成功修改的参数信息（从response.message中提取，格式如："已更改阈值为2000"）
                            if single_response.message:
                                # 尝试从消息中提取关键信息（如"已更改阈值为2000"）
                                msg = single_response.message
                                logger.info(f"[提取修改信息-原始消息 {i+1}] 长度: {len(msg)}, 内容: {msg[:300]}...")
                                
                                # 移除可能的step前缀（如"[step1]"或"[step2]"）
                                msg_clean = msg.split(']', 1)[-1].strip() if ']' in msg else msg.strip()
                                logger.info(f"[提取修改信息-清理后消息 {i+1}] {msg_clean[:300]}...")
                                
                                # 使用更健壮的正则表达式提取所有"已更改XXX为YYY"的消息
                                # 这个模式可以匹配："已更改XXX为YYY"（XXX和YYY之间可能有空格）
                                pattern = r'已更改[^。\n]*?为[^。\n]*?(?=[。\n]|$)'
                                matches = re.findall(pattern, msg_clean)
                                logger.info(f"[提取修改信息-正则匹配结果 {i+1}] 找到{len(matches)}个匹配: {matches}")
                                
                                found_detail = False
                                if matches:
                                    # 提取第一个匹配的消息（每个响应应该只有一个"已更改"消息）
                                    detail = matches[0].strip()
                                    # 移除句尾的句号、换行符和空格
                                    detail = detail.rstrip('。\n ').strip()
                                    # 规范化空格：将"为 "改为"为"（监控通道消息格式问题）
                                    detail = re.sub(r'为\s+', '为', detail)
                                    logger.info(f"[提取修改信息-处理后的detail {i+1}] {detail}")
                                    # 确保detail是有效的修改消息
                                    if detail and '已更改' in detail and '为' in detail:
                                        if detail not in success_details:
                                            success_details.append(detail)
                                            logger.info(f"[提取修改信息-正则提取成功 {i+1}] 已添加到列表: {detail}, 当前列表: {success_details}")
                                            found_detail = True
                                        else:
                                            logger.info(f"[提取修改信息-跳过重复 {i+1}] {detail} 已在列表中")
                                
                                # 如果正则表达式没找到，尝试按句号分割查找
                                if not found_detail:
                                    logger.info(f"[提取修改信息-尝试句子分割 {i+1}]")
                                    sentences = msg_clean.split('。')
                                    for idx, sentence in enumerate(sentences):
                                        sentence_clean = sentence.strip()
                                        # 检查是否包含"已更改"和"为"
                                        if '已更改' in sentence_clean and '为' in sentence_clean:
                                            # 检查是否以"已更改"开头（允许前面有空格）
                                            sentence_no_space = sentence_clean.lstrip()
                                            if sentence_no_space.startswith('已更改'):
                                                # 进一步清理，移除可能的换行符和其他前缀
                                                detail = sentence_clean.split('\n')[0].strip()
                                                # 移除句尾可能存在的句号
                                                if detail.endswith('。'):
                                                    detail = detail[:-1]
                                                # 规范化空格
                                                detail = re.sub(r'为\s+', '为', detail)
                                                logger.info(f"[提取修改信息-句子处理后 {i+1}] 句子{idx}: {detail}")
                                                # 确保detail包含"已更改"并且是有效的修改消息
                                                if detail and '已更改' in detail and '为' in detail:
                                                    if detail not in success_details:
                                                        success_details.append(detail)
                                                        logger.info(f"[提取修改信息-句子提取成功 {i+1}] 已添加到列表: {detail}, 当前列表: {success_details}")
                                                        found_detail = True
                                                        break  # 找到第一个"已更改"就停止，避免重复提取
                                
                                # 如果还是没找到，记录警告
                                if not found_detail:
                                    logger.warning(f"[提取修改信息-未找到 {i+1}] 消息中未找到'已更改XXX为YYY'格式的信息。原始消息: {msg[:200]}...")
                            else:
                                logger.warning(f"[提取修改信息-消息为空 {i+1}] single_response.message 为空")
                            
                            if single_response.state != ConfigState.PARAMETER_CONFIG:
                                # 如果状态改变（如确认配置），停止处理后续操作
                                break
                        except Exception as e:
                            logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                            failed_actions.append(f"{action}({value})")
                
                if response is None:
                    raise HTTPException(status_code=400, detail="未能处理多个参数更新")
                
                # 优化响应消息，显示成功和失败的操作
                logger.info(f"[汇总消息] success_count: {success_count}, success_details数量: {len(success_details)}, details: {success_details}")
                
                # 构建汇总消息：将多个"已更改"消息合并为一行，用逗号分隔
                success_msg = ""
                if success_details and len(success_details) > 0:
                    # 将所有修改信息合并为一行，格式："已更改监控通道为滑油压力，判断依据为<，阈值为200。"
                    # 提取每个修改的参数名称和值
                    changes = []
                    for detail in success_details:
                        # detail格式："已更改{field_name}为{value}"
                        if '已更改' in detail and '为' in detail:
                            # 提取"已更改"后面的内容
                            change_part = detail.replace('已更改', '').strip()
                            if change_part:
                                changes.append(change_part)
                    
                    logger.info(f"[汇总消息-提取的changes] {changes}")
                    if changes:
                        # 合并所有修改为一条消息
                        success_msg = "已更改" + "，".join(changes) + "。"
                        logger.info(f"[汇总消息-最终success_msg] {success_msg}")
                
                # 添加失败信息
                if failed_actions:
                    if success_msg:
                        success_msg += f"\n\n以下参数更新失败：{', '.join(failed_actions)}"
                    else:
                        success_msg = f"以下参数更新失败：{', '.join(failed_actions)}"
                
                # 更新响应消息：如果有汇总消息，优先显示汇总消息
                logger.info(f"[汇总消息-更新响应] success_msg: {success_msg}, response.message长度: {len(response.message) if response.message else 0}")
                if success_msg:
                    # 保留原有的响应消息中的状态提示（如果有）
                    if response.message:
                        original_msg = response.message
                        logger.info(f"[汇总消息-原始消息] {original_msg[:500]}...")
                        # 提取状态提示（_msg_for_condition生成的部分，格式："【当前为条件一，参数如下】...")
                        # 查找"【"开头的状态信息部分
                        status_text = ""
                        if "【" in original_msg:
                            # 找到"【"之后的所有内容作为状态信息
                            start_idx = original_msg.find("【")
                            if start_idx >= 0:
                                status_text = original_msg[start_idx:].strip()
                                logger.info(f"[汇总消息-提取状态信息] {status_text[:300]}...")
                        
                        # 如果没找到"【"，尝试按行查找包含"条件一"或"条件二"的行
                        if not status_text:
                            lines = original_msg.split('\n')
                            status_lines = []
                            in_status = False
                            for line in lines:
                                # 如果遇到包含"条件一"或"条件二"的行，开始收集状态信息
                                if '条件一' in line or '条件二' in line:
                                    in_status = True
                                if in_status and '已更改' not in line:
                                    status_lines.append(line)
                            if status_lines:
                                status_text = '\n'.join(status_lines).strip()
                                logger.info(f"[汇总消息-按行提取状态信息] {status_text[:300]}...")
                        
                        if status_text:
                            response.message = f"{success_msg}\n\n{status_text}"
                            logger.info(f"[汇总消息-最终消息] {response.message[:500]}...")
                        else:
                            # 如果没有状态提示，直接使用汇总消息
                            response.message = success_msg
                            logger.info(f"[汇总消息-无状态信息] 直接使用汇总消息: {success_msg}")
                    else:
                        # 如果原始消息为空，直接使用汇总消息
                        response.message = success_msg
                        logger.info(f"[汇总消息-原始消息为空] 直接使用汇总消息: {success_msg}")
                elif response.message:
                    # 如果没有汇总消息，保留原始消息
                    logger.info(f"[汇总消息-无汇总消息] 保留原始消息")
                    pass  # response.message 已经是原始消息，不需要修改
                
                return response
            elif intent.get("action") and intent.get("action").strip():
                # 单个参数更新：保持原有逻辑
                request.action = intent["action"]
                parsed_by_llm = True
                logger.info(f"[LLM解析成功-单参数] utterance: {request.utterance}, action: {request.action}, value: {intent.get('value')}")
                if "value" in intent:
                    request.value = intent["value"]
            else:
                logger.info(f"[LLM解析失败] utterance: {request.utterance}, 使用fallback规则解析")
        
        # 如果utterance存在但解析失败，将utterance作为action传递，让update_config处理
        if not request.action and request.utterance:
            # 将自然语言直接作为action传递，让后端尝试解析
            request.action = request.utterance
            logger.info(f"[Fallback解析] utterance作为action传递: {request.action}")
        
        # action兜底：如果既没有action也没有utterance，报错
        if not request.action:
            raise HTTPException(status_code=400, detail="未能识别有效action参数或自然语言输入")
        
        # 兼容原有处理，传递parsed_by_llm标志
        response = config_manager.update_config(request.session_id, request.action, request.value, parsed_by_llm=parsed_by_llm)
        
        # 如果有LLM错误信息，将其添加到响应中
        if llm_error_message:
            # 使用model_copy更新error_message字段（Pydantic v2兼容方式）
            try:
                response = response.model_copy(update={"error_message": llm_error_message})
            except (AttributeError, ValueError):
                # 如果model_copy不可用，尝试直接设置属性或添加到message中
                try:
                    response.error_message = llm_error_message
                except Exception:
                    # 最后兜底：将错误信息添加到message中
                    original_message = response.message
                    response.message = f"{original_message}\n\n[LLM调用警告] {llm_error_message}"
        
        return response
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
