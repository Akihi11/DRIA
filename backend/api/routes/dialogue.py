"""
简化的对话API - 直接调用大模型
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
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

# 创建LLM配置
def get_llm_config(provider: str = "deepseek"):
    """获取LLM配置"""
    provider = provider.lower()
    
    if provider == "openai":
        return LLMConfig(
            provider=ModelProvider.OPENAI,
            model_name=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "anthropic":
        return LLMConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            base_url=settings.ANTHROPIC_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "google":
        return LLMConfig(
            provider=ModelProvider.GOOGLE,
            model_name=settings.GOOGLE_MODEL,
            api_key=settings.GOOGLE_API_KEY,
            base_url=settings.GOOGLE_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "azure":
        return LLMConfig(
            provider=ModelProvider.AZURE,
            model_name=settings.AZURE_MODEL,
            api_key=settings.AZURE_API_KEY,
            base_url=settings.AZURE_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "local":
        return LLMConfig(
            provider=ModelProvider.LOCAL,
            model_name=settings.LOCAL_MODEL,
            api_key=settings.LOCAL_API_KEY,
            base_url=settings.LOCAL_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "qwen":
        return LLMConfig(
            provider=ModelProvider.QWEN,
            model_name=settings.QWEN_MODEL,
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    elif provider == "kimi":
        return LLMConfig(
            provider=ModelProvider.KIMI,
            model_name=settings.KIMI_MODEL,
            api_key=settings.KIMI_API_KEY,
            base_url=settings.KIMI_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )
    else:  # 默认使用DeepSeek
        return LLMConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=30.0
        )

@router.post("/ai_report/dialogue", response_model=DialogueResponse, summary="AI对话接口")
async def process_dialogue(request: DialogueRequest):
    """
    处理AI对话请求 - 直接调用大模型
    
    用户与大模型直接对话的接口
    
    - **session_id**: 会话ID
    - **user_input**: 用户输入内容
    - **dialogue_state**: 当前对话状态
    """
    
    try:
        # 获取LLM配置 - 优先使用请求中的provider，否则使用配置文件中的默认值
        provider = getattr(request, 'provider', None) or settings.DEFAULT_LLM_PROVIDER
        
        # 检查提供商是否可用
        if not settings.is_provider_available(provider):
            available_providers = settings.get_available_providers()
            if not available_providers:
                raise HTTPException(
                    status_code=400, 
                    detail="没有可用的LLM提供商，请检查配置文件中的API密钥设置"
                )
            
            # 如果指定的提供商不可用，使用第一个可用的提供商
            provider = available_providers[0]
            logger.warning(f"指定的提供商不可用，自动切换到: {provider}")
        
        config = get_llm_config(provider)
        
        # 创建LLM客户端并调用大模型
        async with LLMClient(config) as client:
            # 准备消息 - 使用更温和的系统提示
            messages = [
                Message(role="system", content="你是一个专业、友好的AI助手，请用中文礼貌地回答用户的问题。请确保回答内容积极正面，避免任何可能引起争议的内容。"),
                Message(role="user", content=request.user_input)
            ]
            
            # 调用大模型
            response = await client.chat_completion(messages)
            ai_response = response.get_content()
        
        return DialogueResponse(
            session_id=request.session_id,
            ai_response=ai_response,
            dialogue_state=DialogueState.INITIAL,
            suggested_actions=[],
            is_complete=False
        )
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Dialogue API Error: {e}")
        print(traceback.format_exc())
        return DialogueResponse(
            session_id=request.session_id,
            ai_response="抱歉，处理您的请求时出现了错误。请稍后重试。",
            dialogue_state=DialogueState.ERROR,
            suggested_actions=[],
            is_complete=False,
            error_message=str(e)
        )


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