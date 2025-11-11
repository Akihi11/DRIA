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
    # 不给默认值，若未指定则由服务端按 settings.DEFAULT_LLM_PROVIDER 决定
    provider: Optional[str] = Field(None, description="大模型提供商 (deepseek/openai/anthropic/google/azure/qwen/kimi/local)")


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


class ChannelStatistics(BaseModel):
    """通道统计信息模型"""
    channel_name: str = Field(..., description="通道名称")
    mean: float = Field(..., description="均值")
    max_value: float = Field(..., description="最大值")
    min_value: float = Field(..., description="最小值")
    std_dev: float = Field(..., description="标准差")
    count: int = Field(..., description="数据点数量")


class ChannelAnalysisRequest(BaseModel):
    """通道分析请求模型"""
    file_id: str = Field(..., description="文件ID")


class ChannelAnalysisResponse(BaseModel):
    """通道分析响应模型"""
    file_id: str = Field(..., description="文件ID")
    total_channels: int = Field(..., description="总通道数")
    channels: List[ChannelStatistics] = Field(..., description="通道统计信息列表")
    analysis_time: str = Field(..., description="分析时间")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    timestamp: str = Field(..., description="错误时间")
