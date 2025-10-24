"""
API request and response models
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class DialogueState(str, Enum):
    """对话状态枚举 - 简化为纯对话"""
    INITIAL = "initial"
    ERROR = "error"


class MessageStatus(str, Enum):
    """消息状态枚举"""
    SENT = "sent"
    PENDING = "pending"
    ERROR = "error"


class DialogueRequest(BaseModel):
    """对话请求模型 - 简化为纯对话"""
    session_id: str = Field(..., description="会话ID")
    user_input: str = Field(..., description="用户输入")
    dialogue_state: DialogueState = Field(..., description="当前对话状态")
    provider: Optional[str] = Field("deepseek", description="大模型提供商 (deepseek/openai/anthropic/google/azure/local)")


class DialogueResponse(BaseModel):
    """对话响应模型 - 简化为纯对话"""
    session_id: str = Field(..., description="会话ID")
    ai_response: str = Field(..., description="AI回复内容")
    suggested_actions: Optional[List[str]] = Field(None, description="建议操作列表")
    dialogue_state: DialogueState = Field(..., description="更新后的对话状态")
    is_complete: bool = Field(False, description="对话是否完成")
    error_message: Optional[str] = Field(None, description="错误信息")




class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field("healthy", description="服务状态")
    timestamp: str = Field(..., description="检查时间")
    version: str = Field("1.0.0", description="API版本")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    timestamp: str = Field(..., description="错误时间")
