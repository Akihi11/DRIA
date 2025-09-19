"""
API request and response models
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class DialogueState(str, Enum):
    """对话状态枚举"""
    INITIAL = "initial"
    FILE_UPLOADED = "file_uploaded" 
    CONFIGURING = "configuring"
    CONFIRMING = "confirming"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


class MessageStatus(str, Enum):
    """消息状态枚举"""
    SENT = "sent"
    PENDING = "pending"
    ERROR = "error"


class DialogueRequest(BaseModel):
    """对话请求模型"""
    session_id: str = Field(..., description="会话ID")
    file_id: Optional[str] = Field(None, description="文件ID")
    user_input: str = Field(..., description="用户输入")
    dialogue_state: DialogueState = Field(..., description="当前对话状态")


class DialogueResponse(BaseModel):
    """对话响应模型"""
    session_id: str = Field(..., description="会话ID")
    ai_response: str = Field(..., description="AI回复内容")
    quick_choices: Optional[List[str]] = Field(None, description="快速选择选项（已弃用，使用suggested_actions）")
    suggested_actions: Optional[List[str]] = Field(None, description="建议操作列表")
    dialogue_state: DialogueState = Field(..., description="更新后的对话状态")
    is_complete: bool = Field(False, description="对话是否完成")
    report_url: Optional[str] = Field(None, description="生成的报表下载链接")
    error_message: Optional[str] = Field(None, description="错误信息")


class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    file_id: str = Field(..., description="文件ID")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    upload_time: str = Field(..., description="上传时间")
    available_channels: List[str] = Field(..., description="可用的通道列表")
    preview_data: Optional[Dict[str, Any]] = Field(None, description="数据预览")


class ReportGenerationRequest(BaseModel):
    """报表生成请求模型"""
    session_id: str = Field(..., description="会话ID")
    file_id: str = Field(..., description="源文件ID")
    config: Dict[str, Any] = Field(..., description="报表配置")
    report_type: Optional[str] = Field("api_generated", description="报表类型 (api_generated, test_reports, manual_reports, etc.)")


class ReportGenerationResponse(BaseModel):
    """报表生成响应模型"""
    session_id: str = Field(..., description="会话ID")
    report_id: str = Field(..., description="报表ID")
    report_url: str = Field(..., description="报表下载链接")
    generation_time: str = Field(..., description="生成时间")
    file_size: int = Field(..., description="报表文件大小")
    success: bool = Field(True, description="生成是否成功")
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
