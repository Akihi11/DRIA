"""
LLM模型定义
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """消息模型"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    name: Optional[str] = Field(None, description="消息发送者名称")
    
    class Config:
        use_enum_values = True


class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[Message] = Field(..., description="消息列表")
    model: str = Field(..., description="模型名称")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, gt=0, description="最大token数")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p参数")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="存在惩罚")
    stream: bool = Field(False, description="是否流式输出")
    stop: Optional[Union[str, List[str]]] = Field(None, description="停止词")
    user: Optional[str] = Field(None, description="用户标识")


class ChatResponse(BaseModel):
    """聊天响应模型"""
    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[Dict[str, Any]] = Field(..., description="选择列表")
    usage: Optional[Dict[str, Any]] = Field(None, description="使用统计")
    
    def get_content(self) -> str:
        """获取响应内容"""
        if self.choices and len(self.choices) > 0:
            return self.choices[0].get("message", {}).get("content", "")
        return ""
    
    def get_finish_reason(self) -> Optional[str]:
        """获取完成原因"""
        if self.choices and len(self.choices) > 0:
            return self.choices[0].get("finish_reason")
        return None


class StreamChunk(BaseModel):
    """流式响应块"""
    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion.chunk", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: List[Dict[str, Any]] = Field(..., description="选择列表")
    
    def get_delta_content(self) -> str:
        """获取增量内容"""
        if self.choices and len(self.choices) > 0:
            return self.choices[0].get("delta", {}).get("content", "")
        return ""
    
    def is_finished(self) -> bool:
        """是否完成"""
        if self.choices and len(self.choices) > 0:
            return self.choices[0].get("finish_reason") is not None
        return False


class LLMError(Exception):
    """LLM错误异常"""
    
    def __init__(
        self, 
        error: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.error = error
        self.code = code
        self.details = details or {}
        self.timestamp = timestamp or datetime.now()
        super().__init__(self.error)
    
    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.error}"
        return self.error


class ModelInfo(BaseModel):
    """模型信息"""
    name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="提供商")
    description: Optional[str] = Field(None, description="模型描述")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    context_length: Optional[int] = Field(None, description="上下文长度")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")
    pricing: Optional[Dict[str, Any]] = Field(None, description="定价信息")
