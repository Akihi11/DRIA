"""
Analysis engine interfaces - abstract base classes for data analysis and report calculation
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..models.data_models import ChannelData, AnalysisResult, ReportData
from ..models.report_config import ReportConfig


class Analyzer(ABC):
    """
    分析器抽象基类
    定义所有分析器策略的接口，实现具体的数据分析算法
    """
    
    @abstractmethod
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """
        执行数据分析
        
        Args:
            data: 通道数据列表
            config: 分析配置参数
            
        Returns:
            AnalysisResult: 分析结果
            
        Raises:
            ValueError: 配置参数错误或数据格式不正确
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置参数是否有效
        
        Args:
            config: 分析配置参数
            
        Returns:
            bool: 配置是否有效
        """
        pass
    
    @abstractmethod
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """
        获取分析所需的通道列表
        
        Args:
            config: 分析配置参数
            
        Returns:
            List[str]: 所需通道名称列表
        """
        pass


class StableStateAnalyzer(Analyzer):
    """稳定状态分析器接口"""
    
    @abstractmethod
    def find_stable_periods(self, data: List[ChannelData], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        查找稳定时段
        
        Args:
            data: 通道数据列表
            config: 稳定状态配置
            
        Returns:
            List[Dict[str, Any]]: 稳定时段列表
        """
        pass


class FunctionalAnalyzer(Analyzer):
    """功能计算分析器接口"""
    
    @abstractmethod
    def calculate_timing_metrics(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, float]:
        """
        计算时间相关指标
        
        Args:
            data: 通道数据列表
            config: 功能计算配置
            
        Returns:
            Dict[str, float]: 时间指标结果
        """
        pass


class StatusEvaluator(Analyzer):
    """状态评估器接口"""
    
    @abstractmethod
    def evaluate_status(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行状态评估
        
        Args:
            data: 通道数据列表
            config: 状态评估配置
            
        Returns:
            Dict[str, Any]: 评估结果
        """
        pass


class ReportCalculationEngine(ABC):
    """
    报表计算引擎抽象基类
    核心计算引擎，负责调度各种分析器策略
    """
    
    @abstractmethod
    def generate(self, data: List[ChannelData], full_config: ReportConfig) -> ReportData:
        """
        生成完整的报表数据
        
        Args:
            data: 通道数据列表
            full_config: 完整的报表配置
            
        Returns:
            ReportData: 完整的报表数据
            
        Raises:
            ValueError: 配置错误或数据不完整
            RuntimeError: 计算过程中发生错误
        """
        pass
    
    @abstractmethod
    def register_analyzer(self, analyzer_type: str, analyzer: Analyzer) -> None:
        """
        注册分析器
        
        Args:
            analyzer_type: 分析器类型标识
            analyzer: 分析器实例
        """
        pass
    
    @abstractmethod
    def validate_data_completeness(self, data: List[ChannelData], config: ReportConfig) -> bool:
        """
        验证数据完整性
        
        Args:
            data: 通道数据列表
            config: 报表配置
            
        Returns:
            bool: 数据是否完整
        """
        pass
    
    @abstractmethod
    def preprocess_data(self, data: List[ChannelData]) -> List[ChannelData]:
        """
        数据预处理
        
        Args:
            data: 原始通道数据列表
            
        Returns:
            List[ChannelData]: 预处理后的数据
        """
        pass
