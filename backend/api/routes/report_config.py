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
        
        # 保存file_id到session中，用于后续查找配置文件
        self.sessions[session_id] = {
            'state': ConfigState.DISPLAY_CHANNELS,
            'report_type': report_type,
            'params': default_params,
            'step': 0,
            'created_at': datetime.now(),
            'file_id': file_id,  # 保存file_id，用于查找对应的配置文件
            'config_file_name': "config_session.json"
        }
        
        return ConfigResponse(
            session_id=session_id,
            state=ConfigState.DISPLAY_CHANNELS,
            message=self.get_step_message(report_type, ConfigState.DISPLAY_CHANNELS),
            suggested_actions=self.get_channel_options(report_type, default_params),
            current_params=default_params
        )
    
    def _extract_value_from_action(self, action: str, field_name: str) -> Any:
        """
        从action字符串中提取value
        例如："把阈值改成2000" -> 2000
             "修改统计方法为最大值" -> "最大值"
        """
        import re
        # 提取数值
        if field_name in ['threshold', 'duration_sec']:
            # 查找数字（支持小数）
            numbers = re.findall(r'\d+(?:\.\d+)?', action)
            if numbers:
                try:
                    return float(numbers[0]) if '.' in numbers[0] else int(numbers[0])
                except:
                    pass
        # 提取字符串值（统计方法、判据）
        elif field_name == 'statistic':
            if '最大' in action:
                return '最大值'
            elif '最小' in action:
                return '最小值'
            elif '平均' in action:
                return '平均值'
        elif field_name == 'logic':
            if '大于' in action:
                return '大于'
            elif '小于' in action:
                return '小于'
            elif '等于' in action or '==' in action:
                return '等于'
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
                return create_response(
                    session_id=session_id,
                    state=ConfigState.DISPLAY_CHANNELS,
                    message=f"已选择展示通道：{params.get('displayChannels', [])}\n\n您可以继续选择其它通道，或点击'完成通道选择'。要求：至少包含一个转速通道（含 rpm）。",
                    suggested_actions=self.get_channel_options(report_type, params),
                    current_params=params
                )
            elif action in ['完成通道选择', '完成选择']:
                display = params.get('displayChannels', []) or []
                # 判断是否包含转速通道：名称包含rpm、Ng或Np（不区分大小写）
                has_rpm = any('rpm' in c.lower() or c.lower() in ['ng', 'np'] or c.lower().startswith('ng') or c.lower().startswith('np') for c in display)
                if not has_rpm:
                    # 未满足强约束，不允许进入下一步
                    return create_response(
                        session_id=session_id,
                        state=ConfigState.DISPLAY_CHANNELS,
                        message="必须至少选择一个转速通道（名称包含 rpm）。请继续选择后再完成。",
                        suggested_actions=self.get_channel_options(report_type, params),
                        current_params=params
                    )
                # 设置默认条件一/二 改为中文
                params.setdefault('triggerLogic', {})
                params['triggerLogic'] = {
                    'combination': 'AND',
                    'condition1': {
                        'enabled': True,
                        'channel': next((c for c in display if 'ng' in c.lower() or 'np' in c.lower() or 'rpm' in c.lower()), 'Ng(rpm)'),
                        'type': '统计值',
                        'statistic': '平均值',
                        'duration_sec': 1,
                        'logic': '大于',
                        'threshold': 10000
                    },
                    'condition2': {
                        'enabled': True,
                        'channel': next((c for c in display if 'ng' in c.lower() or 'np' in c.lower() or 'rpm' in c.lower()), 'Ng(rpm)'),
                        'type': '变化幅度',
                        'statistic': '变化率',
                        'duration_sec': 10,
                        'logic': '小于',
                        'threshold': 100
                    }
                }
                # 新增：生成条件描述params['triggerDesc']
                cond1 = params['triggerLogic']['condition1']
                cond2 = params['triggerLogic']['condition2']
                logic_map = {'大于': '大于', '小于': '小于'}
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
                        'type': '统计值',
                        'statistic': '平均值',
                        'duration_sec': 1,
                        'logic': '大于',
                        'threshold': 10000
                    },
                    'condition2': {
                        'enabled': True,
                        'channel': selected_rpm or rpm_channels[0],
                        'type': '变化幅度',
                        'statistic': '变化率',
                        'duration_sec': 10,
                        'logic': '小于',
                        'threshold': 100
                    }
                }
                session['state'] = ConfigState.TRIGGER_COMBO
                
                # 生成条件的自然语言描述
                cond1_desc = self.format_condition_description(params['triggerLogic']['condition1'])
                cond2_desc = self.format_condition_description(params['triggerLogic']['condition2'])
                
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.TRIGGER_COMBO,
                    message=(
                        f"已选择 {selected_rpm or rpm_channels[0]} 作为判断标准。\n\n"
                        f"已为您填充默认条件一/二：\n"
                        f"条件一：{cond1_desc}\n"
                        f"条件二：{cond2_desc}\n\n"
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
- 判据逻辑: {cond.get('logic', '未设置')}
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
                        f"- 统计方法（statistic）：可改为 平均值/最大值/最小值/中位数 等\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判据逻辑（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"注意：监控通道已在之前选择，不可修改。\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件一的阈值改为9000\"\n"
                        f"- \"将统计方法改为最大值\"\n"
                        f"- \"修改持续时长为5秒\""
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
                        f"- 统计方法（statistic）：可改为 平均值/最大值/最小值/中位数 等\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判据逻辑（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"注意：监控通道已在之前选择，不可修改。\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件二的阈值改为100\"\n"
                        f"- \"将统计方法改为平均值\"\n"
                        f"- \"修改持续时长为15秒\""
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
                        f"【可修改的参数】（每个条件都可修改）：\n"
                        f"- 统计方法（statistic）：可改为 平均值/最大值/最小值/中位数 等\n"
                        f"- 持续时长（duration_sec）：单位秒\n"
                        f"- 判据逻辑（logic）：可改为 大于/小于/大于等于/小于等于\n"
                        f"- 阈值（threshold）：数值\n\n"
                        f"注意：监控通道已在之前选择，不可修改。\n\n"
                        f"您可以通过自然语言进行参数修改，例如：\n"
                        f"- \"把条件一的阈值改为9000\"\n"
                        f"- \"将条件二的统计方法改为平均值\"\n"
                        f"- \"修改条件一的持续时长为5秒\""
                    )
                
                session['state'] = ConfigState.PARAMETER_CONFIG
                return ConfigResponse(
                    session_id=session_id,
                    state=ConfigState.PARAMETER_CONFIG,
                    message=message_text,
                    suggested_actions=[],  # 不使用按钮，让用户用自然语言对话
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
            trigger_logic = params.get('triggerLogic', {})
            combination = trigger_logic.get('combination', 'AND')
            step = session.get('step', 1)
            # 允许编辑参数列表（监控通道不可修改，已在之前选择）
            def _msg_for_condition(cond: dict, cond_name: str):
                return f"\n【当前为{cond_name}，参数如下】\n" \
                       f"- 监控通道: {cond.get('channel', '')} (已在之前选择，不可修改)\n" \
                       f"- 统计方法: {cond.get('statistic', '')} (可修改)\n" \
                       f"- 持续时长(秒): {cond.get('duration_sec', '')} (可修改)\n" \
                       f"- 判据: {cond.get('logic', '')} (可修改)\n" \
                       f"- 阈值: {cond.get('threshold', '')} (可修改)"
            #########################################################################################
            if combination == 'Cond1_Only':
                condition = trigger_logic.get('condition1', {})
                # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                    field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判据': 'logic', '阈值': 'threshold'}
                    if '监控通道' in action or 'channel' in action.lower():
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"监控通道已在之前选择为 {condition.get('channel', '')}，不可修改。{_msg_for_condition(condition, '条件一')}\n如需完成请回复'确认配置'，否则请继续修改其他参数。",
                            suggested_actions=[],
                            current_params=params
                        )
                    # 尝试匹配字段并更新
                    field_updated = False
                    for k, v in field_map.items():
                        if k in action:
                            # 如果value为None，尝试从action字符串中提取
                            extracted_value = value if value is not None else self._extract_value_from_action(action, v)
                            if extracted_value is not None:
                                condition[v] = extracted_value
                                field_updated = True
                                break
                    
                    if field_updated:
                        params['triggerLogic']['condition1'] = condition
                        self._save_display_channels_to_json(session, params)  # 立即保存
                        self._save_conditions_to_json(session, params)  # 保存conditions
                        field_name = next((k for k in field_map.keys() if k in action), '参数')
                        field_key = next((v for k, v in field_map.items() if k in action), None)
                        actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition, '条件一')}\n如需完成请回复'确认配置'，否则请继续修改其他参数。",
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
                elif action in ['确认配置', '确认', '完成', '好了']:
                    session['state'] = ConfigState.CONFIRMATION
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.CONFIRMATION,
                        message=self.get_confirmation_message(report_type, params),
                        suggested_actions=['确认生成', '修改配置', '取消配置'],
                        current_params=params
                    )
                else:
                    # 没有匹配到action，可能是纯自然语言输入，提示用户如何表达
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message=_msg_for_condition(condition, '条件一') + "\n您可以使用自然语言修改参数，例如：'把阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。完成后回复'确认配置'。",
                        suggested_actions=[],
                        current_params=params
                    )
            #########################################################################################
            elif combination == 'Cond2_Only':
                condition = trigger_logic.get('condition2', {})
                # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                    field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判据': 'logic', '阈值': 'threshold'}
                    if '监控通道' in action or 'channel' in action.lower():
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"监控通道已在之前选择为 {condition.get('channel', '')}，不可修改。{_msg_for_condition(condition, '条件二')}\n如需完成请回复'确认配置'，否则请继续修改其他参数。",
                            suggested_actions=[],
                            current_params=params
                        )
                    # 尝试匹配字段并更新
                    field_updated = False
                    for k, v in field_map.items():
                        if k in action:
                            # 如果value为None，尝试从action字符串中提取
                            extracted_value = value if value is not None else self._extract_value_from_action(action, v)
                            if extracted_value is not None:
                                condition[v] = extracted_value
                                field_updated = True
                                break
                    
                    if field_updated:
                        params['triggerLogic']['condition2'] = condition
                        self._save_display_channels_to_json(session, params)
                        self._save_conditions_to_json(session, params)  # 保存conditions
                        field_name = next((k for k in field_map.keys() if k in action), '参数')
                        field_key = next((v for k, v in field_map.items() if k in action), None)
                        actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=f"已更改{field_name}为{actual_value}。{_msg_for_condition(condition, '条件二')}\n如需完成请回复'确认配置'，否则请继续修改其他参数。",
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
                elif action in ['确认配置', '确认', '完成', '好了']:
                    session['state'] = ConfigState.CONFIRMATION
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.CONFIRMATION,
                        message=self.get_confirmation_message(report_type, params),
                        suggested_actions=['确认生成', '修改配置', '取消配置'],
                        current_params=params
                    )
                else:
                    # 没有匹配到action，可能是纯自然语言输入，提示用户如何表达
                    return ConfigResponse(
                        session_id=session_id,
                        state=ConfigState.PARAMETER_CONFIG,
                        message=_msg_for_condition(condition, '条件二') + "\n您可以使用自然语言修改参数，例如：'把阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。完成后回复'确认配置'。",
                        suggested_actions=[],
                        current_params=params
                    )
            #########################################################################################
            elif combination == 'AND':
                # 分步：step 1 配 condition1，确认后 step=2，配 condition2。
                if step == 1:
                    condition = trigger_logic.get('condition1', {})
                    # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                    if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                        field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判据': 'logic', '阈值': 'threshold'}
                        if '监控通道' in action or 'channel' in action.lower():
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"监控通道已在之前选择为 {condition.get('channel', '')}，不可修改。{_msg_for_condition(condition, '条件一')}\n如需完成该条件配置请回复'下一步'，否则请继续修改。",
                                suggested_actions=[],
                                current_params=params
                            )
                        # 尝试匹配字段并更新
                        field_updated = False
                        for k, v in field_map.items():
                            if k in action:
                                # 如果value为None，尝试从action字符串中提取
                                extracted_value = value if value is not None else self._extract_value_from_action(action, v)
                                if extracted_value is not None:
                                    condition[v] = extracted_value
                                    field_updated = True
                                    break
                        
                        if field_updated:
                            params['triggerLogic']['condition1'] = condition
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)  # 保存conditions
                            field_name = next((k for k in field_map.keys() if k in action), '参数')
                            field_key = next((v for k, v in field_map.items() if k in action), None)
                            actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"[step1] 已更改{field_name}为{actual_value}。{_msg_for_condition(condition,'条件一')}\n如需完成该条件配置请回复'下一步'，否则请继续修改。",
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
                        session['step'] = 2
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(trigger_logic.get('condition2', {}), '条件二')+"\n请继续编辑条件二，您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'（监控通道不可修改）。全部完成后回复'确认配置'。",
                            suggested_actions=[],
                            current_params=params
                        )
                    else:
                        # 没有匹配到action，可能是纯自然语言输入
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(condition, '条件一')+ "\n您可以使用自然语言修改参数，例如：'把条件一的阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。完成后回复'下一步'。",
                            suggested_actions=[],
                            current_params=params
                        )
                elif step == 2:
                    condition = trigger_logic.get('condition2', {})
                    # 增强自然语言解析：支持"修改阈值"、"修改统计方法"等格式
                    if action and ('修改' in action or '改为' in action or '改成' in action or '设置为' in action or '设置成' in action):
                        field_map = {'统计方法': 'statistic', '持续时长': 'duration_sec', '判据': 'logic', '阈值': 'threshold'}
                        if '监控通道' in action or 'channel' in action.lower():
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"监控通道已在之前选择为 {condition.get('channel', '')}，不可修改。{_msg_for_condition(condition, '条件二')}\n如需完成请回复'确认配置'，否则请继续修改。",
                                suggested_actions=[],
                                current_params=params
                            )
                        # 尝试匹配字段并更新
                        field_updated = False
                        for k, v in field_map.items():
                            if k in action:
                                # 如果value为None，尝试从action字符串中提取
                                extracted_value = value if value is not None else self._extract_value_from_action(action, v)
                                if extracted_value is not None:
                                    condition[v] = extracted_value
                                    field_updated = True
                                    break
                        
                        if field_updated:
                            params['triggerLogic']['condition2'] = condition
                            self._save_display_channels_to_json(session, params)
                            self._save_conditions_to_json(session, params)  # 保存conditions
                            field_name = next((k for k in field_map.keys() if k in action), '参数')
                            field_key = next((v for k, v in field_map.items() if k in action), None)
                            actual_value = value if value is not None else (condition.get(field_key) if field_key else None)
                            return ConfigResponse(
                                session_id=session_id,
                                state=ConfigState.PARAMETER_CONFIG,
                                message=f"[step2] 已更改{field_name}为{actual_value}。{_msg_for_condition(condition,'条件二')}\n如需完成请回复'确认配置'，否则请继续修改。",
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
                    elif action in ['确认配置', '确认', '完成', '好了']:
                        session['state'] = ConfigState.CONFIRMATION
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.CONFIRMATION,
                            message=self.get_confirmation_message(report_type, params),
                            suggested_actions=['确认生成', '修改配置', '取消配置'],
                            current_params=params
                        )
                    else:
                        # 没有匹配到action，可能是纯自然语言输入
                        return ConfigResponse(
                            session_id=session_id,
                            state=ConfigState.PARAMETER_CONFIG,
                            message=_msg_for_condition(condition, '条件二') + "\n您可以使用自然语言修改参数，例如：'把条件二的阈值改为2000'、'修改统计方法为最大值'、'设置持续时长为5秒'。完成后回复'确认配置'。",
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
            trigger_logic = params.get('triggerLogic', {})
            cond1 = trigger_logic.get('condition1', {})
            cond2 = trigger_logic.get('condition2', {})
            cond1_desc = self.format_condition_description(cond1) if cond1 else "未设置"
            cond2_desc = self.format_condition_description(cond2) if cond2 else "未设置"
            
            return f"""配置确认：

展示通道：{params.get('displayChannels', [])}
组合逻辑：{trigger_logic.get('combination', 'AND')}
条件一：{cond1_desc}
条件二：{cond2_desc}
时间窗口：{params.get('time_window', 10)}秒

请确认是否使用以上配置生成报表？"""
        else:
            return f"配置确认：\n\n{params}\n\n请确认是否使用以上配置生成报表？"

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
        """保存displayChannels到JSON文件"""
        display_channels = params.get('displayChannels', [])
        try:
            config_path, existing_config = self._get_config_file_path(session)
            
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
            print(f"[DEBUG] 已保存displayChannels到: {config_path.absolute()}")
        except Exception as e:
            logger.error(f"保存displayChannels到JSON文件失败: {e}", exc_info=True)
            print(f"[ERROR] 保存displayChannels失败: {e}")
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
            print(f"[DEBUG] 已保存conditions到: {config_path.absolute()}, conditions: {conditions}")
        except Exception as e:
            logger.error(f"保存conditions到JSON文件失败: {e}", exc_info=True)
            print(f"[ERROR] 保存conditions失败: {e}")
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
        conditions: List[Dict[str, Any]] = []
        if trigger.get('condition1', {}).get('enabled', True):
            conditions.append({
                "type": trigger.get('condition1', {}).get('type', '统计值'),
                "channel": trigger.get('condition1', {}).get('channel'),
                "statistic": trigger.get('condition1', {}).get('statistic', '平均值'),
                "duration": trigger.get('condition1', {}).get('duration_sec', 1),
                "logic": trigger.get('condition1', {}).get('logic', '大于'),
                "threshold": trigger.get('condition1', {}).get('threshold', 0)
            })
        if trigger.get('condition2', {}).get('enabled', True):
            conditions.append({
                "type": trigger.get('condition2', {}).get('type', '变化幅度'),
                "channel": trigger.get('condition2', {}).get('channel'),
                "statistic": trigger.get('condition2', {}).get('statistic', '变化率'),
                "duration": trigger.get('condition2', {}).get('duration_sec', 10),
                "logic": trigger.get('condition2', {}).get('logic', '小于'),
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

async def parse_config_intent_with_llm(utterance: str, current_params: dict) -> dict:
    """
    用大模型解析自然语言配置意图，返回{action,value,...,error_message}
    """
    if not utterance:
        return {}
    
    # 构建更详细的prompt，帮助LLM理解用户意图
    prompt = f"""请把用户的需求转成结构化JSON指令，只包括action字段和value字段，不要多余内容！

当前参数配置：
{json.dumps(current_params, ensure_ascii=False, indent=2)}

用户需求：{utterance}

重要说明：
1. action字段应该包含要修改的参数名称和操作，例如：
   - "修改阈值"（当用户说"把阈值改为2000"时）
   - "修改统计方法"（当用户说"修改统计方法为最大值"时）
   - "修改持续时长"（当用户说"设置持续时长为5秒"时）
   - "修改判据"（当用户说"修改判据为大于"时）
2. value字段应该是修改后的具体值，例如：
   - 数字值：2000、5、10等
   - 字符串值："最大值"、"平均值"、"大于"、"小于"等
3. 如果用户提到了"条件一"或"条件二"，action中也需要包含（但后端会忽略，因为当前状态已经确定了条件）
4. 如果无法识别用户意图，返回空对象{{}}

示例：
- 用户说"把条件一的阈值改为2000" -> {{"action": "修改阈值", "value": 2000}}
- 用户说"阈值改为2000" -> {{"action": "修改阈值", "value": 2000}}
- 用户说"把阈值改成2000" -> {{"action": "修改阈值", "value": 2000}}
- 用户说"修改统计方法为最大值" -> {{"action": "修改统计方法", "value": "最大值"}}
- 用户说"设置持续时长为5秒" -> {{"action": "修改持续时长", "value": 5}}
- 用户说"确认配置" -> {{"action": "确认配置", "value": null}}

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
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            try:
                # 强制兼容json
                res = json.loads(content)
                if isinstance(res, dict):
                    return res
                return {}
            except Exception as e:
                error_msg = f"LLM返回内容JSON解析失败: {type(e).__name__}: {str(e)}, 原始内容: {content[:200]}"
                logger.warning(error_msg)
                return {"error_message": error_msg}
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
            intent = await parse_config_intent_with_llm(request.utterance, params)
            
            # 检查是否有错误信息
            if "error_message" in intent:
                llm_error_message = intent["error_message"]
                logger.warning(f"[LLM调用异常] {llm_error_message}")
            
            # 判断LLM解析是否成功：如果有action字段且不为空，说明解析成功
            if intent.get("action") and intent.get("action").strip():
                request.action = intent["action"]
                parsed_by_llm = True
                logger.info(f"[LLM解析成功] utterance: {request.utterance}, action: {request.action}, value: {intent.get('value')}")
            else:
                logger.info(f"[LLM解析失败] utterance: {request.utterance}, 使用fallback规则解析")
            
            if "value" in intent:
                request.value = intent["value"]
        
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
