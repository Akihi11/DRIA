"""
Dialogue management interfaces - abstract base classes for AI conversation handling
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.api_models import DialogueRequest, DialogueResponse
from models.report_config import ReportConfig


class NluProcessor(ABC):
    """
    自然语言理解处理器抽象基类
    定义自然语言理解单元接口，处理用户输入的自然语言
    """
    
    @abstractmethod
    def process_text(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理用户输入的自然语言文本
        
        Args:
            text: 用户输入的文本
            context: 对话上下文信息
            
        Returns:
            Dict[str, Any]: 处理结果，包含意图识别和参数提取
        """
        pass
    
    @abstractmethod
    def extract_parameters(self, text: str, parameter_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        从文本中提取特定参数
        
        Args:
            text: 输入文本
            parameter_schema: 参数模式定义
            
        Returns:
            Dict[str, Any]: 提取的参数
        """
        pass
    
    @abstractmethod
    def classify_intent(self, text: str) -> str:
        """
        分类用户意图
        
        Args:
            text: 输入文本
            
        Returns:
            str: 意图类别
        """
        pass


class RuleProvider(ABC):
    """
    规则提供者抽象基类
    定义规则提供者接口，管理报表生成规则和模板
    """
    
    @abstractmethod
    def get_report_template(self, report_type: str) -> Dict[str, Any]:
        """
        获取报表模板
        
        Args:
            report_type: 报表类型
            
        Returns:
            Dict[str, Any]: 报表模板配置
        """
        pass
    
    @abstractmethod
    def get_configuration_rules(self, section: str) -> Dict[str, Any]:
        """
        获取配置规则
        
        Args:
            section: 配置部分标识
            
        Returns:
            Dict[str, Any]: 配置规则
        """
        pass
    
    @abstractmethod
    def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """
        验证配置是否符合规则
        
        Args:
            config: 配置数据
            
        Returns:
            bool: 配置是否有效
        """
        pass
    
    @abstractmethod
    def get_default_parameters(self, report_section: str) -> Dict[str, Any]:
        """
        获取默认参数
        
        Args:
            report_section: 报表部分
            
        Returns:
            Dict[str, Any]: 默认参数配置
        """
        pass


class DialogueManager(ABC):
    """
    对话管理器抽象基类
    管理对话流程，协调各个组件完成报表配置
    """
    
    @abstractmethod
    def process(self, user_request: DialogueRequest) -> DialogueResponse:
        """
        处理用户对话请求
        
        Args:
            user_request: 用户对话请求
            
        Returns:
            DialogueResponse: AI对话响应
            
        Raises:
            ValueError: 请求格式错误
            RuntimeError: 处理过程中发生错误
        """
        pass
    
    @abstractmethod
    def initialize_session(self, session_id: str, file_id: Optional[str] = None) -> Dict[str, Any]:
        """
        初始化对话会话
        
        Args:
            session_id: 会话ID
            file_id: 可选的文件ID
            
        Returns:
            Dict[str, Any]: 会话初始化信息
        """
        pass
    
    @abstractmethod
    def update_configuration(self, session_id: str, config_updates: Dict[str, Any]) -> bool:
        """
        更新配置信息
        
        Args:
            session_id: 会话ID
            config_updates: 配置更新数据
            
        Returns:
            bool: 更新是否成功
        """
        pass
    
    @abstractmethod
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict[str, Any]: 会话状态信息
        """
        pass
    
    @abstractmethod
    def generate_ai_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """
        生成AI回复
        
        Args:
            user_input: 用户输入
            context: 对话上下文
            
        Returns:
            str: AI回复文本
        """
        pass
    
    @abstractmethod
    def finalize_configuration(self, session_id: str) -> ReportConfig:
        """
        完成配置并返回最终配置对象
        
        Args:
            session_id: 会话ID
            
        Returns:
            ReportConfig: 最终的报表配置
        """
        pass
