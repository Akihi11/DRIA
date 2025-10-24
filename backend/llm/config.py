"""
LLM配置管理
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ModelProvider(str, Enum):
    """模型提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    KIMI = "kimi"
    LOCAL = "local"


class LLMConfig(BaseModel):
    """LLM配置类"""
    
    # 基础配置
    provider: ModelProvider = Field(..., description="模型提供商")
    model_name: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    
    # 模型参数
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(2048, gt=0, description="最大token数")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Top-p参数")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="频率惩罚")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="存在惩罚")
    
    # 重试配置
    max_retries: int = Field(5, ge=0, description="最大重试次数")
    retry_delay: float = Field(2.0, ge=0.0, description="重试延迟(秒)")
    request_delay: float = Field(1.0, ge=0.0, description="请求间隔延迟(秒)")
    
    # 超时配置
    timeout: float = Field(30.0, gt=0, description="请求超时时间(秒)")
    
    # 其他配置
    stream: bool = Field(False, description="是否流式输出")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="自定义请求头")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            ModelProvider: lambda v: v.value
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return self.dict(exclude={'api_key'})  # 排除敏感信息
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        config = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": self.stream,
        }
        
        if self.base_url:
            config["base_url"] = self.base_url
            
        return config
