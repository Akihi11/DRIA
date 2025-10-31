"""
简化的对话API - 直接调用大模型
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import sys
from pathlib import Path
import os
import logging
import asyncio

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.models.api_models import DialogueRequest, DialogueResponse, DialogueState, ErrorResponse
from backend.llm.client import LLMClient
from backend.llm.config import LLMConfig, ModelProvider
from backend.llm.models import Message

# 确保环境变量被加载
from backend.config import settings

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/ai_report/dialogue", response_model=DialogueResponse, summary="AI对话接口")
async def process_dialogue(request: DialogueRequest):
    """
    处理AI对话请求 - 支持配置模式智能解析
    
    用户与大模型对话的接口，支持在配置模式下理解用户意图并执行配置操作
    
    - **session_id**: 会话ID
    - **user_input**: 用户输入内容
    - **dialogue_state**: 当前对话状态
    """
    
    try:
        # 检查是否有活跃的配置会话
        config_session = check_active_config_session(request.session_id)
        
        if config_session:
            # 配置模式：使用大模型理解并执行配置操作
            return await handle_config_dialogue_with_llm(request, config_session)
        else:
            # 普通对话模式
            return await handle_normal_dialogue(request)
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Dialogue API Error: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        return DialogueResponse(
            session_id=request.session_id,
            ai_response="抱歉，处理您的请求时出现了错误。请稍后重试。",
            dialogue_state=DialogueState.INITIAL,
            suggested_actions=[],
            is_complete=False,
            error_message=str(e)
        )


def check_active_config_session(session_id: str) -> Optional[Dict]:
    """检查是否有活跃的配置会话"""
    from backend.api.routes.report_config import config_manager, ConfigState
    session = config_manager.sessions.get(session_id)
    
    # 更严格的检查：必须有配置会话且状态不是初始或已完成
    # 且必须有关联的报表类型
    if session and session['state'] not in [ConfigState.INITIAL, ConfigState.COMPLETED]:
        # 确保会话有必要的字段
        if 'report_type' in session and 'params' in session:
            return session
    return None

async def handle_config_dialogue_with_llm(request: DialogueRequest, config_session: Dict) -> DialogueResponse:
    """使用混合方式处理配置模式下的对话：规则解析 + 大模型帮助"""
    
    # 首先尝试规则解析
    parsed_action = parse_user_input_to_action(
        request.user_input, 
        config_session['state'], 
        config_session['params']
    )
    
    if parsed_action:
        # 规则解析成功，直接执行配置更新
        from backend.api.routes.report_config import config_manager
        config_response = config_manager.update_config(
            request.session_id,
            parsed_action['action'],
            parsed_action.get('value')
        )
        
        return DialogueResponse(
            session_id=request.session_id,
            ai_response=config_response.message,
            dialogue_state=DialogueState.INITIAL,
            suggested_actions=config_response.suggested_actions,
            is_complete=config_response.is_complete
        )
    else:
        # 规则解析失败，使用大模型提供配置帮助
        return await handle_config_help_dialogue(request, config_session)

def parse_user_input_to_action(user_input: str, current_state: str, current_params: Dict) -> Optional[Dict]:
    """解析用户输入为配置操作"""
    user_input_lower = user_input.lower()
    
    # 根据当前状态解析
    if current_state in ["display_channels", "channel_selection"]:
        if any(keyword in user_input_lower for keyword in ['ng', '转速', 'rpm']):
            return {'action': '选择 Ng(rpm)'}
        elif any(keyword in user_input_lower for keyword in ['温度', 'temperature', '°c']):
            return {'action': '选择 Temperature(°C)'}
        elif any(keyword in user_input_lower for keyword in ['压力', 'pressure', 'kpa']):
            return {'action': '选择 Pressure(kPa)'}
        elif any(keyword in user_input_lower for keyword in ['完成', '确定', '选好了']):
            return {'action': '完成通道选择'}
    
    elif current_state in ["trigger_combo"]:
        if '仅用条件一' in user_input or 'cond1' in user_input_lower:
            return {'action': '仅用条件一'}
        if '仅用条件二' in user_input or 'cond2' in user_input_lower:
            return {'action': '仅用条件二'}
        if 'and' in user_input_lower or '同时' in user_input:
            return {'action': 'AND'}

    elif current_state == "parameter_config":
        # 解析阈值修改
        if '阈值' in user_input or 'threshold' in user_input_lower:
            import re
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                return {'action': '修改阈值', 'value': int(numbers[0])}
        
        # 解析统计方法修改
        if any(keyword in user_input for keyword in ['统计', '方法', '计算']):
            if '平均' in user_input:
                return {'action': '修改统计方法', 'value': '平均值'}
            elif '最大' in user_input:
                return {'action': '修改统计方法', 'value': '最大值'}
            elif '最小' in user_input:
                return {'action': '修改统计方法', 'value': '最小值'}
        
        # 解析时间窗口修改
        if '时间窗口' in user_input or '时间' in user_input:
            import re
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                return {'action': '修改时间窗口', 'value': int(numbers[0])}
        
        # 解析确认操作
        if any(keyword in user_input for keyword in ['确认', '完成', '好了', '可以']):
            return {'action': '确认配置'}
        
        # 解析退出操作
        if any(keyword in user_input for keyword in ['退出', '取消', '不要', '算了']):
            return {'action': '取消配置'}
    
    elif current_state == "confirmation":
        if any(keyword in user_input for keyword in ['确认', '生成', '开始']):
            return {'action': '确认生成'}
        elif any(keyword in user_input for keyword in ['修改', '更改', '调整']):
            return {'action': '修改配置'}
        elif any(keyword in user_input for keyword in ['取消', '退出', '不要']):
            return {'action': '取消配置'}
    
    return None

async def handle_config_help_dialogue(request: DialogueRequest, config_session: Dict) -> DialogueResponse:
    """在配置模式下提供智能帮助"""
    provider = getattr(request, 'provider', None) or settings.DEFAULT_LLM_PROVIDER
    config = settings.get_llm_config(provider)
    
    # 构建包含配置上下文的系统提示
    system_prompt = f"""你是一个AI助手，当前用户正在配置{config_session['report_type']}报表。

当前配置状态：{config_session['state']}
当前参数：{config_session['params']}

用户可能想要：
1. 修改配置参数（可以说"阈值改成15000"、"使用平均值"等）
2. 询问配置相关问题
3. 确认或取消配置

请根据用户的输入提供帮助。如果用户想要修改参数，请引导他们使用自然语言描述。
如果用户想要退出配置，请明确告知可以输入"退出配置"或"取消配置"。
如果用户的输入与配置无关，请友好地引导他们回到配置主题。

示例：
- "阈值改成15000" → 修改阈值为15000
- "使用平均值" → 修改统计方法为平均值
- "时间窗口改成20" → 修改时间窗口为20
- "确认配置" → 进入确认状态
- "退出配置" → 取消配置

重要：只有在用户明确表示要修改配置时，才提供配置建议气泡。"""

    async with LLMClient(config) as client:
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=request.user_input)
        ]
        
        response = await client.chat_completion(messages)
        ai_response = response.get_content()
    
    # 检查用户输入是否与配置相关，如果不相关则不返回配置建议
    user_input_lower = request.user_input.lower()
    config_keywords = ['通道', '阈值', '时间窗口', '统计', '配置', '确认', '取消', '平均值', '最大', '最小']
    is_config_related = any(keyword in user_input_lower for keyword in config_keywords)
    
    # 只在明确与配置相关时才返回配置建议
    suggested_actions = get_config_suggestions(config_session['state']) if is_config_related else []
    
    return DialogueResponse(
        session_id=request.session_id,
        ai_response=ai_response,
        dialogue_state=DialogueState.INITIAL,
        suggested_actions=suggested_actions,
        is_complete=False
    )

async def handle_normal_dialogue(request: DialogueRequest) -> DialogueResponse:
    """处理普通对话请求"""
    provider = getattr(request, 'provider', None) or settings.DEFAULT_LLM_PROVIDER
    config = settings.get_llm_config(provider)
    
    # 准备消息 - 使用更温和的系统提示
    messages = [
        Message(role="system", content="你是一个专业、友好的AI助手，请用中文礼貌地回答用户的问题。请确保回答内容积极正面，避免任何可能引起争议的内容。"),
        Message(role="user", content=request.user_input)
    ]
    
    # 调用大模型
    async with LLMClient(config) as client:
        response = await client.chat_completion(messages)
        ai_response = response.get_content()
    
    return DialogueResponse(
        session_id=request.session_id,
        ai_response=ai_response,
        dialogue_state=DialogueState.INITIAL,
        suggested_actions=[],
        is_complete=False
    )

def get_config_suggestions(current_state: str) -> List[str]:
    """根据当前状态获取建议操作"""
    from backend.api.routes.report_config import ConfigState
    
    if current_state == ConfigState.DISPLAY_CHANNELS:
        return ['选择 Ng(rpm)', '选择 Np(rpm)', '选择 Temperature(°C)', '选择 Pressure(kPa)', '完成通道选择', '取消配置']
    elif current_state == ConfigState.TRIGGER_COMBO:
        return ['仅用条件一', '仅用条件二', 'AND', '返回修改通道']
    elif current_state == ConfigState.PARAMETER_CONFIG:
        return ['修改统计方法', '修改阈值', '修改时间窗口', '确认配置', '取消配置']
    elif current_state == ConfigState.CONFIRMATION:
        return ['确认生成', '修改配置', '取消配置']
    else:
        return ['取消配置']


@router.post("/ai_report/sessions", summary="创建新会话")
async def create_session():
    """
    创建新的对话会话
    """
    
    session_id = str(uuid.uuid4())
    
    return {
        "session_id": session_id,
        "message": "新会话创建成功"
    }