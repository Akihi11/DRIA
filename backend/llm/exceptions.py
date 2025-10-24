"""
LLM异常定义
"""

from typing import Optional, Dict, Any


class LLMException(Exception):
    """LLM基础异常"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class LLMConfigError(LLMException):
    """LLM配置错误"""
    pass


class LLMAPIError(LLMException):
    """LLM API错误"""
    pass


class LLMRateLimitError(LLMAPIError):
    """LLM速率限制错误"""
    pass


class LLMAuthenticationError(LLMAPIError):
    """LLM认证错误"""
    pass


class LLMQuotaExceededError(LLMAPIError):
    """LLM配额超限错误"""
    pass


class LLMTimeoutError(LLMAPIError):
    """LLM超时错误"""
    pass


class LLMNetworkError(LLMAPIError):
    """LLM网络错误"""
    pass


class LLMValidationError(LLMException):
    """LLM验证错误"""
    pass


class LLMStreamError(LLMException):
    """LLM流式处理错误"""
    pass

