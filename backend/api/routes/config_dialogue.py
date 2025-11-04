"""
配置对话API接口 - 支持自然语言配置
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import logging
import time
import re
import json

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

def _is_config_state(state: str) -> bool:
    """
    判断是否是配置相关的状态（允许继续处理多个参数的状态）
    
    包括：
    - 稳态配置：parameter_config
    - 功能计算配置：time_base_config, startup_time_config, ignition_time_config, 
                     rundown_ng_config, rundown_np_config
    """
    config_states = {
        "parameter_config",  # 稳态配置
        "time_base_config",  # 功能计算：时间（基准时刻）配置
        "startup_time_config",  # 功能计算：启动时间配置
        "ignition_time_config",  # 功能计算：点火时间配置
        "rundown_ng_config",  # 功能计算：Ng余转时间配置
        "rundown_np_config",  # 功能计算：Np余转时间配置
    }
    return state in config_states

def _build_summary_message(all_responses: list, final_response, failed_actions: list) -> str:
    """
    汇总多个响应的消息
    
    Args:
        all_responses: 所有成功的响应消息列表
        final_response: 最后一个响应对象（用于获取状态信息）
        failed_actions: 失败的操作列表
    
    Returns:
        汇总后的消息
    """
    # 汇总所有成功的修改信息
    success_details = []
    for msg in all_responses:
        if msg:
            # 移除可能的step前缀（如"[step1]"或"[step2]"）
            msg_clean = msg.split(']', 1)[-1].strip() if ']' in msg else msg.strip()
            # 使用正则表达式提取"已更改XXX为YYY"的消息
            pattern = r'已更改[^。\n]*?为[^。\n]*?(?=[。\n]|$)'
            matches = re.findall(pattern, msg_clean)
            if matches:
                detail = matches[0].strip().rstrip('。\n ').strip()
                detail = re.sub(r'为\s+', '为', detail)  # 规范化空格
                if detail and '已更改' in detail and '为' in detail:
                    if detail not in success_details:
                        success_details.append(detail)
            else:
                # 如果正则没找到，尝试按句号分割查找
                sentences = msg_clean.split('。')
                for sentence in sentences:
                    sentence_clean = sentence.strip()
                    if '已更改' in sentence_clean and '为' in sentence_clean:
                        sentence_no_space = sentence_clean.lstrip()
                        if sentence_no_space.startswith('已更改'):
                            detail = sentence_clean.split('\n')[0].strip()
                            if detail.endswith('。'):
                                detail = detail[:-1]
                            detail = re.sub(r'为\s+', '为', detail)
                            if detail and '已更改' in detail and '为' in detail:
                                if detail not in success_details:
                                    success_details.append(detail)
                                    break
    
    logger.info(f"[汇总消息-辅助函数] success_details: {success_details}")
    
    # 构建汇总消息
    success_msg = ""
    if success_details:
        changes = []
        for detail in success_details:
            if '已更改' in detail and '为' in detail:
                change_part = detail.replace('已更改', '').strip()
                if change_part:
                    changes.append(change_part)
        if changes:
            success_msg = "已更改" + "，".join(changes) + "。"
            logger.info(f"[汇总消息-辅助函数] success_msg: {success_msg}")
    
    # 从最后一个响应中提取状态信息（_msg_for_condition生成的部分）
    status_text = ""
    if final_response and final_response.message:
        original_msg = final_response.message
        # 查找"【"开头的状态信息部分
        if "【" in original_msg:
            start_idx = original_msg.find("【")
            if start_idx >= 0:
                status_text = original_msg[start_idx:].strip()
        # 如果没找到"【"，尝试按行查找
        if not status_text:
            lines = original_msg.split('\n')
            status_lines = []
            in_status = False
            for line in lines:
                if '条件一' in line or '条件二' in line:
                    in_status = True
                if in_status and '已更改' not in line:
                    status_lines.append(line)
            if status_lines:
                status_text = '\n'.join(status_lines).strip()
    
    # 构建最终消息
    if success_msg:
        if status_text:
            message = f"{success_msg}\n\n{status_text}"
        else:
            message = success_msg
    else:
        # 如果没有成功汇总，使用原始消息
        message = final_response.message if final_response and final_response.message else ""
    
    # 添加失败信息
    if failed_actions:
        failed_msg = f"以下参数更新失败：{', '.join(failed_actions)}"
        if message:
            message = f"{failed_msg}\n\n{message}"
        else:
            message = failed_msg
    
    return message

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
    对于steady_state和function_calc类型，使用状态驱动的ReportConfigManager
    """
    try:
        # 对于steady_state和function_calc，使用状态驱动的ReportConfigManager
        if request.report_type == "steady_state" or request.report_type == "function_calc":
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

def _is_explicit_button_action(user_input: str) -> bool:
    """
    判断是否是明确的按钮操作（不需要LLM解析）
    
    明确的按钮操作包括：
    - "选择 xxx" (通道选择阶段)
    - "使用 xxx" (通道选择阶段)
    - "完成通道选择" / "完成选择"
    - "仅用条件一" / "仅用条件二" / "AND" (组合逻辑选择)
    - "确认配置" / "确认" / "完成" / "好了"
    - "确认生成" / "修改配置" / "取消配置"
    
    注意：参数修改操作（如"阈值改为2000"）不是明确的按钮操作，
    应该作为自然语言输入通过LLM解析，因为参数配置阶段应该用自然语言对话。
    """
    user_input = user_input.strip()
    
    # 明确的按钮操作模式（只包括结构化的操作，不包括参数修改）
    explicit_patterns = [
        r'^选择\s+',  # "选择 xxx" (通道选择)
        r'^使用\s+',  # "使用 xxx" (通道选择)
        r'^完成通道选择$',
        r'^完成选择$',
        r'^仅用条件一$',
        r'^仅用条件二$',
        r'^AND$',
        r'^确认配置$',
        r'^确认$',
        r'^完成$',
        r'^好了$',
        r'^ok$',
        r'^下一步$',
        r'^下一步骤$',
        r'^继续$',
        r'^确认生成$',
        r'^修改配置$',
        r'^取消配置$',
    ]
    
    for pattern in explicit_patterns:
        if re.match(pattern, user_input, re.IGNORECASE):
            return True
    
    return False

def _normalize_actions_to_current_condition(actions: list, user_input: str, current_context: dict) -> list:
    """
    修正LLM返回的actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
    
    Args:
        actions: LLM返回的actions列表
        user_input: 用户输入的原始文本
        current_context: 当前上下文信息，包含current_condition
        
    Returns:
        修正后的actions列表
    """
    if not actions or not isinstance(actions, list):
        return actions
    
    # 检查用户是否明确指定了条件
    user_explicitly_specified_condition = False
    if '条件一' in user_input or '条件1' in user_input or 'condition1' in user_input.lower():
        user_explicitly_specified_condition = True
    elif '条件二' in user_input or '条件2' in user_input or 'condition2' in user_input.lower():
        user_explicitly_specified_condition = True
    
    # 如果用户明确指定了条件，不需要修正
    if user_explicitly_specified_condition:
        return actions
    
    # 获取当前上下文的条件
    current_condition = current_context.get('current_condition') if current_context else None
    
    # 如果当前上下文没有条件，不需要修正
    if not current_condition:
        return actions
    
    # 检查actions是否都应用到当前条件
    # 严格过滤：如果用户没有明确指定条件，只保留当前上下文条件的actions
    normalized_actions = []
    seen_params = set()  # 用于去重，避免同一个参数被修改多次
    
    for action_item in actions:
        action = action_item.get('action', '')
        value = action_item.get('value')
        
        # 检查action中是否包含条件名称
        has_condition_one = '条件一' in action or '条件1' in action
        has_condition_two = '条件二' in action or '条件2' in action
        
        # 如果action中包含条件名称，必须严格匹配当前上下文条件
        if has_condition_one or has_condition_two:
            # 检查是否是当前上下文条件
            is_current_condition = False
            if current_condition == '条件一' and has_condition_one:
                is_current_condition = True
            elif current_condition == '条件二' and has_condition_two:
                is_current_condition = True
            
            if is_current_condition:
                # 是当前条件，保留（但要去重）
                if '修改' in action:
                    # 提取参数名称用于去重（去除条件名称）
                    param_name = action.replace('修改', '').replace('条件一', '').replace('条件二', '').replace('条件1', '').replace('条件2', '').strip()
                    if param_name not in seen_params:
                        normalized_actions.append(action_item)
                        seen_params.add(param_name)
                        logger.info(f"[保留action] 当前上下文条件匹配: {action}, 参数: {param_name}")
                    else:
                        logger.warning(f"[过滤重复] 跳过重复的参数修改: {action} (参数{param_name}已被处理)")
                else:
                    # 非修改类的action（如"下一步"等），保留
                    normalized_actions.append(action_item)
            else:
                # 不是当前条件，严格过滤掉
                logger.warning(f"[严格过滤] 过滤掉非当前上下文条件的action: {action}, 当前上下文: {current_condition}")
                continue  # 跳过这个action
        else:
            # action中没有指定条件名称，需要添加当前条件
            if '修改' in action and current_condition:
                # 提取参数名称
                param_name = action.replace('修改', '').strip()
                # 检查是否已经处理过相同参数（可能在其他action中已经处理过）
                if param_name not in seen_params:
                    corrected_action = f'修改{current_condition}{param_name}'
                    normalized_actions.append({
                        'action': corrected_action,
                        'value': value
                    })
                    seen_params.add(param_name)
                    logger.info(f"[修正action] 原action: {action}, 修正后: {corrected_action}, 当前上下文: {current_condition}")
                else:
                    logger.warning(f"[过滤重复] 跳过重复的参数修改: {action} (参数{param_name}已被处理)")
            else:
                # 不是参数修改action（如"下一步"、"确认"等），直接保留
                normalized_actions.append(action_item)
    
    # 最终检查：确保没有同时包含两个条件的actions
    if len(normalized_actions) > 0:
        conditions_in_actions = set()
        for action_item in normalized_actions:
            action = action_item.get('action', '')
            if '条件一' in action or '条件1' in action:
                conditions_in_actions.add('条件一')
            if '条件二' in action or '条件2' in action:
                conditions_in_actions.add('条件二')
        
        if len(conditions_in_actions) > 1:
            logger.error(f"[严重错误] 发现actions中同时包含多个条件: {conditions_in_actions}, actions: {normalized_actions}")
            # 如果仍然发现多个条件，只保留当前上下文条件的actions
            filtered_actions = []
            for action_item in normalized_actions:
                action = action_item.get('action', '')
                if current_condition in action:
                    filtered_actions.append(action_item)
            normalized_actions = filtered_actions
            logger.warning(f"[强制过滤] 强制过滤后只保留当前上下文条件的actions: {len(normalized_actions)}个")
    
    return normalized_actions

def _parse_natural_language_fallback(user_input: str) -> Dict[str, Any]:
    """
    当LLM解析失败时，使用规则匹配作为fallback解析自然语言输入
    
    支持解析的参数修改：
    - "阈值改为100" / "阈值改成100" / "把阈值改为100" -> action="修改阈值", value=100
    - "把条件一的阈值改为100" -> action="修改条件一阈值", value=100
    - "统计方法改为最大值" / "修改统计方法为最大值" -> action="修改统计方法", value="最大值"
    - "持续时长改为5秒" / "设置持续时长为5" -> action="修改持续时长", value=5
    - "判据改为大于" / "修改判据为大于" / "判断依据改为大于" / "修改判断依据为大于" -> action="修改判断依据", value="大于"
    - "通道改成np" / "监控通道改为np" -> action="修改监控通道", value="Np"
    
    支持多个参数（有逗号分隔）：
    - "统计方法改为最大值，阈值改为1667" -> {"actions": [{"action": "修改统计方法", "value": "最大值"}, {"action": "修改阈值", "value": 1667}]}
    
    支持多个参数（无逗号分隔）：
    - "通道改成np 阈值2600 统计方法改为最大值" -> {"actions": [{"action": "修改监控通道", "value": "Np"}, {"action": "修改阈值", "value": 2600}, {"action": "修改统计方法", "value": "最大值"}]}
    """
    user_input = user_input.strip()
    
    # 检查是否包含多个参数（通过逗号分隔）
    has_comma = '，' in user_input or ',' in user_input
    
    # 检测是否包含多个参数（即使没有逗号）
    # 使用detect_multiple_actions函数进行检测
    try:
        from backend.api.routes.report_config import detect_multiple_actions
        has_multiple_params = detect_multiple_actions(user_input)
    except Exception:
        # 如果导入失败，使用简单检测
        has_multiple_params = False
        param_keywords = ['通道', '阈值', '统计', '方法', '持续时长', '判断依据', '判据']
        keyword_count = sum(1 for kw in param_keywords if kw in user_input)
        has_multiple_params = keyword_count >= 2
    
    # 如果有多个参数（无论是否有逗号），尝试解析所有参数
    if has_comma or has_multiple_params:
        # 分割成多个部分（如果有逗号按逗号分割，否则按关键词分割）
        if has_comma:
            parts = re.split(r'[，,]\s*', user_input)
        else:
            # 没有逗号时，尝试按关键词分割
            # 使用正则表达式匹配参数模式
            # 例如："通道改成np 阈值2600 统计方法改为最大值"
            # 匹配模式：参数名 + 改成/改为/改为等动词 + 值
            pattern_parts = []
            
            # 先尝试按常见参数关键词分割
            # 通道相关（支持"通道改成np"或"通道np"）
            channel_match = re.search(r'(?:通道|监控通道)(?:[改成改为为]+)?([a-zA-Z0-9\u4e00-\u9fa5]+)', user_input, re.IGNORECASE)
            if channel_match:
                channel_part = channel_match.group(0)
                pattern_parts.append(('channel', channel_part))
            
            # 阈值相关（支持"阈值2600"或"阈值改为2600"）
            threshold_match = re.search(r'阈值(?:[改成改为为]+)?(\d+)', user_input)
            if threshold_match:
                threshold_part = threshold_match.group(0)
                pattern_parts.append(('threshold', threshold_part))
            
            # 统计方法相关（支持"统计方法改为最大值"或"统计方法最大值"）
            statistic_match = re.search(r'(统计方法|统计|方法)(?:[改成改为为]+)?(最大值|最小值|平均值|中位数)', user_input)
            if statistic_match:
                statistic_part = statistic_match.group(0)
                pattern_parts.append(('statistic', statistic_part))
            
            # 持续时长相关
            duration_match = re.search(r'(持续时长|持续时间|时长)[改成改为为]*(\d+)', user_input)
            if duration_match:
                duration_part = duration_match.group(0)
                pattern_parts.append(('duration', duration_part))
            
            # 判断依据相关
            logic_match = re.search(r'(判断依据|判据|逻辑)[改成改为为]+(大于|小于|大于等于|小于等于)', user_input)
            if logic_match:
                logic_part = logic_match.group(0)
                pattern_parts.append(('logic', logic_part))
            
            # 如果通过模式匹配找到了多个部分，使用这些部分
            if len(pattern_parts) >= 2:
                parts = [part[1] for part in pattern_parts]
            else:
                # 如果模式匹配失败，尝试按关键词简单分割
                # 查找所有参数关键词的位置，按位置分割
                keywords = ['通道', '阈值', '统计方法', '统计', '方法', '持续时长', '判断依据', '判据']
                split_points = []
                for keyword in keywords:
                    for match in re.finditer(keyword, user_input):
                        split_points.append(match.start())
                
                if len(split_points) >= 2:
                    # 有多个关键词，按关键词位置分割
                    split_points = sorted(split_points)
                    parts = []
                    for i, start in enumerate(split_points):
                        end = split_points[i + 1] if i + 1 < len(split_points) else len(user_input)
                        part = user_input[start:end].strip()
                        if part:
                            parts.append(part)
                else:
                    # 没有找到足够的分割点，按空格分割
                    parts = [p.strip() for p in user_input.split() if p.strip()]
        actions = []
        condition_prefix = ""
        
        # 检查是否有条件前缀
        if '条件一' in user_input or '条件1' in user_input or 'condition1' in user_input.lower():
            condition_prefix = "条件一"
        elif '条件二' in user_input or '条件2' in user_input or 'condition2' in user_input.lower():
            condition_prefix = "条件二"
        
        # 解析每个部分
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 解析通道修改（监控通道）
            if '通道' in part or 'channel' in part.lower():
                # 尝试提取通道名称（np、ng等），支持"通道改成np"或"通道np"
                channel_match = re.search(r'(?:通道|监控通道)(?:[改成改为为]+)?([a-zA-Z0-9\u4e00-\u9fa5]+)', part, re.IGNORECASE)
                if channel_match:
                    channel_value = channel_match.group(1).strip()
                    # 将小写转换为首字母大写（如np -> Np）
                    if channel_value.lower() in ['np', 'ng']:
                        channel_value = channel_value.upper()
                    actions.append({
                        'action': f'修改{condition_prefix}监控通道' if condition_prefix else '修改监控通道',
                        'value': channel_value
                    })
                    continue
            
            # 解析阈值修改
            if '阈值' in part or 'threshold' in part.lower():
                numbers = re.findall(r'\d+', part)
                if numbers:
                    actions.append({
                        'action': f'修改{condition_prefix}阈值' if condition_prefix else '修改阈值',
                        'value': int(numbers[0])
                    })
                    continue
            
            # 解析统计方法修改（支持"统计方法改为最大值"或"统计方法最大值"）
            if any(keyword in part for keyword in ['统计', '方法', '计算']):
                if '平均' in part:
                    actions.append({
                        'action': f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法',
                        'value': '平均值'
                    })
                    continue
                elif '最大' in part:
                    actions.append({
                        'action': f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法',
                        'value': '最大值'
                    })
                    continue
                elif '最小' in part:
                    actions.append({
                        'action': f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法',
                        'value': '最小值'
                    })
                    continue
                elif '中位' in part:
                    actions.append({
                        'action': f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法',
                        'value': '中位数'
                    })
                    continue
            
            # 解析持续时长修改
            if any(keyword in part for keyword in ['持续时长', '持续时间', '时长']):
                numbers = re.findall(r'\d+', part)
                if numbers:
                    actions.append({
                        'action': f'修改{condition_prefix}持续时长' if condition_prefix else '修改持续时长',
                        'value': int(numbers[0])
                    })
                    continue
            
            # 解析判断依据逻辑修改（支持"判据"、"判断依据"、"逻辑"三种说法）
            if '判据' in part or '判断依据' in part or '逻辑' in part:
                if '大于' in part:
                    if '等于' in part:
                        actions.append({
                            'action': f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据',
                            'value': '大于等于'
                        })
                    else:
                        actions.append({
                            'action': f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据',
                            'value': '大于'
                        })
                    continue
                elif '小于' in part:
                    if '等于' in part:
                        actions.append({
                            'action': f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据',
                            'value': '小于等于'
                        })
                    else:
                        actions.append({
                            'action': f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据',
                            'value': '小于'
                        })
                    continue
        
        # 如果成功解析了多个操作，返回actions格式
        if len(actions) > 0:
            return {"actions": actions}
    
    # 单个参数解析（原有逻辑）
    result = {}
    
    # 检查是否包含"条件一"或"条件二"
    condition_prefix = ""
    if '条件一' in user_input or '条件1' in user_input or 'condition1' in user_input.lower():
        condition_prefix = "条件一"
    elif '条件二' in user_input or '条件2' in user_input or 'condition2' in user_input.lower():
        condition_prefix = "条件二"
    
    # 解析通道修改（监控通道）（支持"通道改成np"或"通道np"）
    if '通道' in user_input or 'channel' in user_input.lower():
        # 尝试提取通道名称（np、ng等），支持多种格式
        channel_match = re.search(r'(?:通道|监控通道)(?:[改成改为为]+)?([a-zA-Z0-9\u4e00-\u9fa5]+)', user_input, re.IGNORECASE)
        if channel_match:
            channel_value = channel_match.group(1).strip()
            # 将小写转换为首字母大写（如np -> Np）
            if channel_value.lower() in ['np', 'ng']:
                channel_value = channel_value.upper()
            result['action'] = f'修改{condition_prefix}监控通道' if condition_prefix else '修改监控通道'
            result['value'] = channel_value
            return result
    
    # 解析阈值修改
    if '阈值' in user_input or 'threshold' in user_input.lower():
        numbers = re.findall(r'\d+', user_input)
        if numbers:
            result['action'] = f'修改{condition_prefix}阈值' if condition_prefix else '修改阈值'
            result['value'] = int(numbers[0])
            return result
    
    # 解析统计方法修改
    if any(keyword in user_input for keyword in ['统计', '方法', '计算']):
        if '平均' in user_input:
            result['action'] = f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法'
            result['value'] = '平均值'
            return result
        elif '最大' in user_input:
            result['action'] = f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法'
            result['value'] = '最大值'
            return result
        elif '最小' in user_input:
            result['action'] = f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法'
            result['value'] = '最小值'
            return result
        elif '中位' in user_input:
            result['action'] = f'修改{condition_prefix}统计方法' if condition_prefix else '修改统计方法'
            result['value'] = '中位数'
            return result
    
    # 解析持续时长修改
    if any(keyword in user_input for keyword in ['持续时长', '持续时间', '时长']):
        numbers = re.findall(r'\d+', user_input)
        if numbers:
            result['action'] = f'修改{condition_prefix}持续时长' if condition_prefix else '修改持续时长'
            result['value'] = int(numbers[0])
            return result
    
    # 解析判断依据逻辑修改（支持"判据"、"判断依据"、"逻辑"三种说法）
    if '判据' in user_input or '判断依据' in user_input or '逻辑' in user_input:
        if '大于' in user_input:
            if '等于' in user_input:
                result['action'] = f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据'
                result['value'] = '大于等于'
            else:
                result['action'] = f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据'
                result['value'] = '大于'
            return result
        elif '小于' in user_input:
            if '等于' in user_input:
                result['action'] = f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据'
                result['value'] = '小于等于'
            else:
                result['action'] = f'修改{condition_prefix}判断依据' if condition_prefix else '修改判断依据'
                result['value'] = '小于'
            return result
    
    # 解析确认操作
    if any(keyword in user_input for keyword in ['确认', '完成', '好了', '可以']):
        if '生成' in user_input:
            result['action'] = '确认生成'
        elif '配置' in user_input:
            result['action'] = '确认配置'
        else:
            result['action'] = '确认配置'
        return result
    
    # 解析取消操作
    if any(keyword in user_input for keyword in ['取消', '退出', '不要', '算了']):
        result['action'] = '取消配置'
        return result
    
    return result

@router.post("/update-config", response_model=UpdateConfigResponse, summary="更新配置参数")
async def update_config_dialogue(request: UpdateConfigRequest):
    """
    通过自然语言更新配置参数
    
    支持自然语言表达，如：
    - "使用转速通道" → 转速通道 = true
    - "阈值改成15000" → 阈值 = 15000
    - "使用平均值" → 统计方法 = 平均值
    - "完成通道选择" → 状态驱动操作
    
    对于明确的按钮操作，直接使用规则匹配，不调用LLM
    只有在规则匹配失败时，才尝试使用LLM解析（但捕获异常避免影响明确操作）
    """
    try:
        # 延迟导入避免循环导入
        from backend.api.routes.report_config import config_manager as report_config_manager
        
        # 先检查是否在ReportConfigManager中（状态驱动配置）
        if request.session_id in report_config_manager.sessions:
            # 使用状态驱动的ReportConfigManager
            try:
                session = report_config_manager.sessions.get(request.session_id)
                params = session.get("params", {}) if session else {}
                
                parsed_by_llm = False
                action = None
                value = None
                
                # 判断是否是明确的按钮操作
                is_explicit_action = _is_explicit_button_action(request.user_input)
                
                if is_explicit_action:
                    # 明确的按钮操作：直接使用规则匹配，不调用LLM
                    logger.info(f"[明确按钮操作] utterance: {request.user_input}, 使用规则匹配")
                    action = request.user_input
                    # 尝试从action中提取数值（如"阈值改为2000"）
                    match = re.search(r'(\d+)', request.user_input)
                    if match:
                        value = int(match.group(1))
                    # 明确的按钮操作直接处理并返回，不调用LLM
                    parsed_by_llm = False
                    config_response = report_config_manager.update_config(
                        request.session_id,
                        action,
                        value,
                        parsed_by_llm=parsed_by_llm
                    )
                    return UpdateConfigResponse(
                        success=True,
                        message=config_response.message,
                        config=config_response.current_params,
                        status=config_response.state,
                        suggested_actions=config_response.suggested_actions or []
                    )
                else:
                    # 不是明确的按钮操作：先尝试LLM解析，失败后使用规则匹配fallback
                    action = request.user_input
                    parsed_by_llm = False
                    
                    # 尝试使用LLM解析自然语言输入（但捕获异常避免影响明确操作）
                    try:
                        from backend.api.routes.report_config import parse_config_intent_with_llm, detect_multiple_actions
                        
                        # 构建当前上下文信息
                        current_context = {}
                        current_state = session.get('state', '') if session else ''
                        
                        # 判断是稳态参数还是功能计算
                        if current_state in ['time_base_config', 'startup_time_config', 'ignition_time_config', 'rundown_ng_config', 'rundown_np_config']:
                            # 功能计算：设置当前步骤信息
                            step_names = {
                                'time_base_config': '时间（基准时刻）',
                                'startup_time_config': '启动时间',
                                'ignition_time_config': '点火时间',
                                'rundown_ng_config': 'Ng余转时间',
                                'rundown_np_config': 'Np余转时间'
                            }
                            current_context['current_step'] = current_state
                            current_context['current_step_name'] = step_names.get(current_state, '')
                        else:
                            # 稳态参数：优先级：1. last_modified_condition（上一次修改的条件） 2. 默认条件（根据combination判断）
                            trigger_logic = params.get('triggerLogic', {})
                            combination = trigger_logic.get('combination', 'AND')
                            
                            # 优先使用last_modified_condition（如果存在）
                            last_modified_condition = session.get('last_modified_condition') if session else None
                            if last_modified_condition:
                                current_context['current_condition'] = last_modified_condition
                            else:
                                # 如果没有last_modified_condition，根据combination判断默认条件
                                if combination == 'AND':
                                    # AND模式下，默认条件一
                                    current_context['current_condition'] = '条件一'
                                elif combination == 'Cond1_Only':
                                    current_context['current_condition'] = '条件一'
                                elif combination == 'Cond2_Only':
                                    current_context['current_condition'] = '条件二'
                        
                        # 在调用LLM之前检测多参数，使用共用检测函数
                        force_multiple_actions = detect_multiple_actions(request.user_input)
                        
                        intent = await parse_config_intent_with_llm(request.user_input, params, current_context, force_multiple_actions=force_multiple_actions)
                        
                        # 支持单个操作和多个操作
                        if "actions" in intent and isinstance(intent["actions"], list) and len(intent["actions"]) > 0:
                            # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                            intent["actions"] = _normalize_actions_to_current_condition(
                                intent["actions"], 
                                request.user_input, 
                                current_context
                            )
                            
                            # 多个参数更新：循环处理每个操作
                            parsed_by_llm = True
                            logger.info(f"[LLM解析成功-多参数] utterance: {request.user_input}, actions数量: {len(intent['actions'])}")
                            response = None
                            success_count = 0
                            failed_actions = []
                            all_responses = []  # 收集所有成功的响应消息
                            for i, action_item in enumerate(intent["actions"]):
                                action = action_item.get("action")
                                value = action_item.get("value")
                                if action and action.strip():
                                    logger.info(f"[处理多参数更新 {i+1}/{len(intent['actions'])}] action: {action}, value: {value}")
                                    try:
                                        single_response = report_config_manager.update_config(
                                            request.session_id,
                                            action,
                                            value,
                                            parsed_by_llm=parsed_by_llm
                                        )
                                        response = single_response  # 保留最后一个响应用于状态和参数
                                        success_count += 1
                                        # 收集所有成功的响应消息，用于后续汇总
                                        if single_response.message:
                                            all_responses.append(single_response.message)
                                        if not _is_config_state(response.state):
                                            # 如果状态改变（如确认配置），停止处理后续操作
                                            break
                                    except Exception as e:
                                        logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                        failed_actions.append(f"{action}({value})")
                            
                            if response is None:
                                return UpdateConfigResponse(
                                    success=False,
                                    message="未能处理多个参数更新",
                                    config=params,
                                    status=session.get("state", "unknown")
                                )
                            
                            # 使用辅助函数汇总消息
                            message = _build_summary_message(all_responses, response, failed_actions)
                            
                            return UpdateConfigResponse(
                                success=True,
                                message=message,
                                config=response.current_params,
                                status=response.state,
                                suggested_actions=response.suggested_actions
                            )
                        elif intent.get("action") and intent.get("action").strip():
                            # 检查用户输入是否包含多个参数（使用共用检测函数）
                            # 如果包含多个参数，但LLM只返回了单个action，使用更明确的提示重新调用LLM
                            has_multiple_params = detect_multiple_actions(request.user_input)
                            
                            if has_multiple_params:
                                # LLM可能没有正确识别多个参数，使用更明确的提示重新调用LLM
                                logger.warning(f"[LLM解析可能不完整] utterance: {request.user_input}包含多个参数，但LLM只返回了单个action，尝试使用更明确的提示重新解析")
                                try:
                                    # 重新调用LLM，强制要求识别多个参数
                                    retry_intent = await parse_config_intent_with_llm(
                                        request.user_input, 
                                        params, 
                                        current_context,
                                        force_multiple_actions=True
                                    )
                                    
                                    # 检查重新解析的结果
                                    if "actions" in retry_intent and isinstance(retry_intent["actions"], list) and len(retry_intent["actions"]) > 0:
                                        # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                                        retry_intent["actions"] = _normalize_actions_to_current_condition(
                                            retry_intent["actions"], 
                                            request.user_input, 
                                            current_context
                                        )
                                        # LLM重新解析成功，识别到多个参数
                                        logger.info(f"[LLM重新解析成功-多参数] utterance: {request.user_input}, actions数量: {len(retry_intent['actions'])}")
                                        intent = retry_intent  # 使用重新解析的结果
                                        # 继续到下面的多参数处理逻辑
                                    elif retry_intent.get("action") and retry_intent.get("action").strip():
                                        # LLM重新解析后仍然只返回单个action，但至少返回了结果
                                        logger.warning(f"[LLM重新解析仍不完整] utterance: {request.user_input}，重新解析后仍然只返回单个action，继续使用单参数处理")
                                        # 使用重新解析的结果作为fallback
                                        intent = retry_intent
                                    else:
                                        # LLM重新解析失败或返回空结果，回退到规则匹配
                                        logger.warning(f"[LLM重新解析失败] utterance: {request.user_input}，回退到规则匹配")
                                        fallback_result = _parse_natural_language_fallback(request.user_input)
                                        
                                        # 检查fallback是否识别到多个参数
                                        if "actions" in fallback_result and isinstance(fallback_result["actions"], list) and len(fallback_result["actions"]) > 0:
                                            # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                                            fallback_result["actions"] = _normalize_actions_to_current_condition(
                                                fallback_result["actions"], 
                                                request.user_input, 
                                                current_context
                                            )
                                            # 多个参数更新：循环处理每个操作
                                            logger.info(f"[规则匹配成功-多参数] utterance: {request.user_input}, actions数量: {len(fallback_result['actions'])}")
                                            response = None
                                            success_count = 0
                                            failed_actions = []
                                            all_responses = []  # 收集所有成功的响应消息
                                            for i, action_item in enumerate(fallback_result["actions"]):
                                                action = action_item.get("action")
                                                value = action_item.get("value")
                                                if action and action.strip():
                                                    logger.info(f"[处理多参数更新 {i+1}/{len(fallback_result['actions'])}] action: {action}, value: {value}")
                                                    try:
                                                        single_response = report_config_manager.update_config(
                                                            request.session_id,
                                                            action,
                                                            value,
                                                            parsed_by_llm=False  # 使用规则匹配，不是LLM解析
                                                        )
                                                        response = single_response  # 保留最后一个响应用于状态和参数
                                                        success_count += 1
                                                        # 收集所有成功的响应消息，用于后续汇总
                                                        if single_response.message:
                                                            all_responses.append(single_response.message)
                                                        if not _is_config_state(response.state):
                                                            # 如果状态改变（如确认配置），停止处理后续操作
                                                            break
                                                    except Exception as e:
                                                        logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                                        failed_actions.append(f"{action}({value})")
                                            
                                            if response is None:
                                                return UpdateConfigResponse(
                                                    success=False,
                                                    message="未能处理多个参数更新",
                                                    config=params,
                                                    status=session.get("state", "unknown") if session else "unknown"
                                                )
                                            
                                            # 使用辅助函数汇总消息
                                            message = _build_summary_message(all_responses, response, failed_actions)
                                            
                                            return UpdateConfigResponse(
                                                success=True,
                                                message=message,
                                                config=response.current_params,
                                                status=response.state,
                                                suggested_actions=response.suggested_actions or []
                                            )
                                        # 如果fallback也只识别到单个参数，继续使用原始LLM返回的结果
                                except Exception as e:
                                    # LLM重新调用失败，回退到规则匹配
                                    logger.warning(f"[LLM重新调用失败] utterance: {request.user_input}，错误: {e}，回退到规则匹配")
                                    fallback_result = _parse_natural_language_fallback(request.user_input)
                                    
                                    # 检查fallback是否识别到多个参数
                                    if "actions" in fallback_result and isinstance(fallback_result["actions"], list) and len(fallback_result["actions"]) > 0:
                                        # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                                        fallback_result["actions"] = _normalize_actions_to_current_condition(
                                            fallback_result["actions"], 
                                            request.user_input, 
                                            current_context
                                        )
                                        # 多个参数更新：循环处理每个操作
                                        logger.info(f"[规则匹配成功-多参数] utterance: {request.user_input}, actions数量: {len(fallback_result['actions'])}")
                                        response = None
                                        success_count = 0
                                        failed_actions = []
                                        all_responses = []  # 收集所有成功的响应消息
                                        for i, action_item in enumerate(fallback_result["actions"]):
                                            action = action_item.get("action")
                                            value = action_item.get("value")
                                            if action and action.strip():
                                                logger.info(f"[处理多参数更新 {i+1}/{len(fallback_result['actions'])}] action: {action}, value: {value}")
                                                try:
                                                    single_response = report_config_manager.update_config(
                                                        request.session_id,
                                                        action,
                                                        value,
                                                        parsed_by_llm=False  # 使用规则匹配，不是LLM解析
                                                    )
                                                    response = single_response  # 保留最后一个响应用于状态和参数
                                                    success_count += 1
                                                    # 收集所有成功的响应消息，用于后续汇总
                                                    if single_response.message:
                                                        all_responses.append(single_response.message)
                                                    if not _is_config_state(response.state):
                                                        # 如果状态改变（如确认配置），停止处理后续操作
                                                        break
                                                except Exception as e:
                                                    logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                                    failed_actions.append(f"{action}({value})")
                                        
                                        if response is None:
                                            return UpdateConfigResponse(
                                                success=False,
                                                message="未能处理多个参数更新",
                                                config=params,
                                                status=session.get("state", "unknown") if session else "unknown"
                                            )
                                        
                                        # 使用辅助函数汇总消息
                                        message = _build_summary_message(all_responses, response, failed_actions)
                                        
                                        return UpdateConfigResponse(
                                            success=True,
                                            message=message,
                                            config=response.current_params,
                                            status=response.state,
                                            suggested_actions=response.suggested_actions or []
                                        )
                                    # 如果fallback也只识别到单个参数，继续使用原始LLM返回的结果
                            
                            # 处理单个action的情况（可能是单参数，或者是多参数但LLM只识别到一个）
                            # 检查当前intent是否有actions数组（可能是重新解析后的结果）
                            if "actions" in intent and isinstance(intent["actions"], list) and len(intent["actions"]) > 0:
                                # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                                intent["actions"] = _normalize_actions_to_current_condition(
                                    intent["actions"], 
                                    request.user_input, 
                                    current_context
                                )
                                # 多个参数更新：循环处理每个操作
                                parsed_by_llm = True
                                logger.info(f"[LLM解析成功-多参数] utterance: {request.user_input}, actions数量: {len(intent['actions'])}")
                                response = None
                                success_count = 0
                                failed_actions = []
                                all_responses = []  # 收集所有成功的响应消息
                                for i, action_item in enumerate(intent["actions"]):
                                    action = action_item.get("action")
                                    value = action_item.get("value")
                                    if action and action.strip():
                                        logger.info(f"[处理多参数更新 {i+1}/{len(intent['actions'])}] action: {action}, value: {value}")
                                        try:
                                            single_response = report_config_manager.update_config(
                                                request.session_id,
                                                action,
                                                value,
                                                parsed_by_llm=parsed_by_llm
                                            )
                                            response = single_response  # 保留最后一个响应用于状态和参数
                                            success_count += 1
                                            # 收集所有成功的响应消息，用于后续汇总
                                            if single_response.message:
                                                all_responses.append(single_response.message)
                                            if not _is_config_state(response.state):
                                                # 如果状态改变（如确认配置），停止处理后续操作
                                                break
                                        except Exception as e:
                                            logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                            failed_actions.append(f"{action}({value})")
                                
                                if response is None:
                                    return UpdateConfigResponse(
                                        success=False,
                                        message="未能处理多个参数更新",
                                        config=params,
                                        status=session.get("state", "unknown") if session else "unknown"
                                    )
                                
                                # 使用辅助函数汇总消息
                                message = _build_summary_message(all_responses, response, failed_actions)
                                
                                return UpdateConfigResponse(
                                    success=True,
                                    message=message,
                                    config=response.current_params,
                                    status=response.state,
                                    suggested_actions=response.suggested_actions or []
                                )
                            
                            # 使用LLM返回的单个action
                            action = intent["action"]
                            parsed_by_llm = True
                            logger.info(f"[LLM解析成功-单参数] utterance: {request.user_input}, action: {action}, value: {intent.get('value')}")
                            if "value" in intent:
                                value = intent["value"]
                        else:
                            # LLM返回空结果，尝试规则匹配fallback
                            logger.info(f"[LLM解析返回空] utterance: {request.user_input}, 使用fallback规则解析")
                            fallback_result = _parse_natural_language_fallback(request.user_input)
                            
                            # 检查是否是多个参数
                            if "actions" in fallback_result and isinstance(fallback_result["actions"], list) and len(fallback_result["actions"]) > 0:
                                # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                                fallback_result["actions"] = _normalize_actions_to_current_condition(
                                    fallback_result["actions"], 
                                    request.user_input, 
                                    current_context
                                )
                                # 多个参数更新：循环处理每个操作
                                logger.info(f"[规则匹配成功-多参数] utterance: {request.user_input}, actions数量: {len(fallback_result['actions'])}")
                                response = None
                                success_count = 0
                                failed_actions = []
                                all_responses = []  # 收集所有成功的响应消息
                                for i, action_item in enumerate(fallback_result["actions"]):
                                    action = action_item.get("action")
                                    value = action_item.get("value")
                                    if action and action.strip():
                                        logger.info(f"[处理多参数更新 {i+1}/{len(fallback_result['actions'])}] action: {action}, value: {value}")
                                        try:
                                            single_response = report_config_manager.update_config(
                                                request.session_id,
                                                action,
                                                value,
                                                parsed_by_llm=parsed_by_llm
                                            )
                                            response = single_response  # 保留最后一个响应用于状态和参数
                                            success_count += 1
                                            # 收集所有成功的响应消息，用于后续汇总
                                            if single_response.message:
                                                all_responses.append(single_response.message)
                                            if not _is_config_state(response.state):
                                                # 如果状态改变（如确认配置），停止处理后续操作
                                                break
                                        except Exception as e:
                                            logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                            failed_actions.append(f"{action}({value})")
                                
                                if response is None:
                                    return UpdateConfigResponse(
                                        success=False,
                                        message="未能处理多个参数更新",
                                        config=params,
                                        status=session.get("state", "unknown") if session else "unknown"
                                    )
                                
                                # 使用辅助函数汇总消息
                                message = _build_summary_message(all_responses, response, failed_actions)
                                
                                return UpdateConfigResponse(
                                    success=True,
                                    message=message,
                                    config=response.current_params,
                                    status=response.state,
                                    suggested_actions=response.suggested_actions or []
                                )
                            elif fallback_result.get("action"):
                                action = fallback_result["action"]
                                if "value" in fallback_result:
                                    value = fallback_result["value"]
                                logger.info(f"[规则匹配成功] utterance: {request.user_input}, action: {action}, value: {value}")
                            else:
                                logger.warning(f"[规则匹配失败] utterance: {request.user_input}, 无法解析")
                    except Exception as llm_error:
                        # LLM解析失败（如502错误），使用规则匹配作为fallback
                        logger.warning(f"[LLM解析异常] utterance: {request.user_input}, 错误: {llm_error}, 使用规则匹配fallback")
                        fallback_result = _parse_natural_language_fallback(request.user_input)
                        
                        # 检查是否是多个参数
                        if "actions" in fallback_result and isinstance(fallback_result["actions"], list) and len(fallback_result["actions"]) > 0:
                            # 修正actions，确保它们应用到当前上下文的条件（如果用户没有明确指定条件）
                            fallback_result["actions"] = _normalize_actions_to_current_condition(
                                fallback_result["actions"], 
                                request.user_input, 
                                current_context
                            )
                            # 多个参数更新：循环处理每个操作
                            logger.info(f"[规则匹配成功-多参数] utterance: {request.user_input}, actions数量: {len(fallback_result['actions'])}")
                            response = None
                            success_count = 0
                            failed_actions = []
                            all_responses = []  # 收集所有成功的响应消息
                            for i, action_item in enumerate(fallback_result["actions"]):
                                action = action_item.get("action")
                                value = action_item.get("value")
                                if action and action.strip():
                                    logger.info(f"[处理多参数更新 {i+1}/{len(fallback_result['actions'])}] action: {action}, value: {value}")
                                    try:
                                        single_response = report_config_manager.update_config(
                                            request.session_id,
                                            action,
                                            value,
                                            parsed_by_llm=parsed_by_llm
                                        )
                                        response = single_response  # 保留最后一个响应用于状态和参数
                                        success_count += 1
                                        # 收集所有成功的响应消息，用于后续汇总
                                        if single_response.message:
                                            all_responses.append(single_response.message)
                                        if not _is_config_state(response.state):
                                            # 如果状态改变（如确认配置），停止处理后续操作
                                            break
                                    except Exception as e:
                                        logger.warning(f"[多参数更新失败] action: {action}, value: {value}, 错误: {e}")
                                        failed_actions.append(f"{action}({value})")
                            
                            if response is None:
                                return UpdateConfigResponse(
                                    success=False,
                                    message="未能处理多个参数更新",
                                    config=params,
                                    status=session.get("state", "unknown") if session else "unknown"
                                )
                            
                            # 使用辅助函数汇总消息
                            message = _build_summary_message(all_responses, response, failed_actions)
                            
                            return UpdateConfigResponse(
                                success=True,
                                message=message,
                                config=response.current_params,
                                status=response.state,
                                suggested_actions=response.suggested_actions or []
                            )
                        elif fallback_result.get("action"):
                            action = fallback_result["action"]
                            if "value" in fallback_result:
                                value = fallback_result["value"]
                            logger.info(f"[规则匹配成功] utterance: {request.user_input}, action: {action}, value: {value}")
                        else:
                            logger.warning(f"[规则匹配失败] utterance: {request.user_input}, 无法解析")
                
                # 调用update_config，传入解析后的action和value（单个参数的情况）
                if action is None:
                    return UpdateConfigResponse(
                        success=False,
                        message="未能识别您的操作。请使用自然语言修改参数,例如:'把阈值改为2000'、'修改统计方法为最大值'。",
                        config=params,
                        status=session.get("state", "unknown") if session else "unknown"
                    )
                
                config_response = report_config_manager.update_config(
                    request.session_id,
                    action,
                    value,
                    parsed_by_llm=parsed_by_llm
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
    完成配置对话 - 直接生成报表并退出配置模式
    
    用户点击"完成配置"按钮时：
    1. 读取已保存的配置文件（JSON 文件）
    2. 调用计算模块生成报表
    3. 删除配置会话，退出配置模式
    """
    try:
        # 首先检查是否在 ReportConfigManager 中（用于 steady_state 报表）
        from backend.api.routes.report_config import config_manager as report_config_manager
        
        if request.session_id in report_config_manager.sessions:
            # 使用 ReportConfigManager
            session = report_config_manager.sessions.get(request.session_id)
            
            if not session:
                raise ValueError("配置会话不存在")
            
            # 直接调用计算模块生成报表（不需要状态检查）
            try:
                # 1. 获取配置文件路径
                backend_dir = Path(__file__).parent.parent.parent
                config_dir = backend_dir / "config_sessions"
                config_file_path = None
                
                # 查找对应的配置文件（通过 file_id 或使用 config_session.json）
                file_id = session.get('file_id')
                if file_id:
                    # 查找匹配的配置文件（按修改时间排序，取最新的）
                    matching_files = []
                    for json_file in config_dir.glob("*.json"):
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                cfg = json.load(f)
                                if cfg.get("fileId") == file_id:
                                    matching_files.append((json_file.stat().st_mtime, json_file))
                        except Exception:
                            continue
                    
                    if matching_files:
                        # 按修改时间排序，取最新的
                        matching_files.sort(key=lambda x: x[0], reverse=True)
                        config_file_path = matching_files[0][1]
                
                # 如果没找到，使用默认的 config_session.json
                if config_file_path is None:
                    default_path = config_dir / "config_session.json"
                    if default_path.exists():
                        config_file_path = default_path
                    else:
                        raise ValueError("找不到配置文件，请确保已保存配置")
                
                # 2. 获取输入数据文件路径
                uploads_dir = backend_dir / "uploads"
                input_file_path = None
                
                # 从配置文件中读取 fileId（UUID）或 sourceFileId
                # 优先使用 fileId，因为上传后文件被重命名为 UUID 格式
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    # 优先使用 fileId（UUID格式），如果没有则使用 sourceFileId
                    file_id = config_data.get("fileId") or config_data.get("sourceFileId")
                
                if file_id:
                    # 查找上传的文件（支持多种扩展名）
                    # 如果 file_id 已经是 UUID（不含扩展名），直接拼接扩展名
                    # 如果 file_id 是原始文件名（含扩展名），需要处理
                    for ext in [".csv", ".xlsx", ".xls"]:
                        # 如果 file_id 已经包含扩展名，尝试直接匹配
                        if file_id.endswith(ext):
                            candidate = uploads_dir / file_id
                            if candidate.exists():
                                input_file_path = candidate
                                break
                        # 否则尝试添加扩展名（UUID 格式的情况）
                        candidate = uploads_dir / f"{file_id}{ext}"
                        if candidate.exists():
                            input_file_path = candidate
                            break
                
                if not input_file_path or not input_file_path.exists():
                    raise ValueError(f"找不到输入数据文件: {file_id}。请确认文件已上传到 uploads 目录。")
                
                # 3. 创建输出目录
                import uuid
                report_id = str(uuid.uuid4())
                reports_dir = backend_dir / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                
                # 4. 调用计算模块生成报表
                # 新格式：reports/steady_state_report-{uuid}.xlsx
                report_file_path = reports_dir / f"steady_state_report-{report_id}.xlsx"
                from backend.services.steady_state_service import SteadyStateService
                service = SteadyStateService()
                report_path = service.generate_report(
                    str(config_file_path),
                    str(input_file_path),
                    str(report_file_path)
                )
                
                # 5. 删除配置会话，退出配置模式
                del report_config_manager.sessions[request.session_id]
                
                logger.info(f"报表生成成功: {report_path}")
                
                return CompleteConfigResponse(
                    success=True,
                    message=f"报表生成成功！文件路径: {report_path}",
                    config={"report_id": report_id, "report_path": report_path},
                    status="completed"
                )
                
            except Exception as calc_error:
                logger.error(f"生成报表失败: {calc_error}", exc_info=True)
                # 保持会话，允许用户重试
                return CompleteConfigResponse(
                    success=False,
                    message=f"生成报表失败: {str(calc_error)}",
                    config=session.get('params', {}),
                    status="error"
                )
        else:
            # 使用 ConfigManager（旧的配置管理器）
            config_response = await config_manager.complete_config(request.session_id)
        
        return CompleteConfigResponse(
            success=True,
            message=config_response["message"],
            config=config_response["config"],
            status=config_response["status"]
        )
        
    except Exception as e:
        logger.error(f"完成配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"完成配置失败: {str(e)}")

@router.post("/cancel-config", response_model=CancelConfigResponse, summary="取消配置")
async def cancel_config_dialogue(request: CancelConfigRequest):
    """
    取消配置对话 - 退出配置模式，不生成报表
    """
    try:
        # 首先检查是否在 ReportConfigManager 中（用于 steady_state 报表）
        from backend.api.routes.report_config import config_manager as report_config_manager
        
        if request.session_id in report_config_manager.sessions:
            # 使用 ReportConfigManager - 直接删除会话
            del report_config_manager.sessions[request.session_id]
            
            logger.info(f"取消配置，会话已删除: {request.session_id}")
            
            return CancelConfigResponse(
                success=True,
                message="已取消配置，已退出配置模式"
            )
        else:
            # 使用 ConfigManager（旧的配置管理器）
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
