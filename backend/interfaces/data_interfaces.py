"""
Data service interfaces - abstract base classes for data reading and report writing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.models.data_models import ChannelData, ReportData


class DataReader(ABC):
    """
    数据读取器抽象基类
    定义数据读取器规范，支持从不同格式的文件中读取通道数据
    """
    
    @abstractmethod
    def read(self, file_path: str, channel_names: List[str]) -> List[ChannelData]:
        """
        读取指定通道的数据
        
        Args:
            file_path: 数据文件路径
            channel_names: 需要读取的通道名称列表
            
        Returns:
            List[ChannelData]: 通道数据列表
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持或数据格式错误
        """
        pass
    
    @abstractmethod
    def get_available_channels(self, file_path: str) -> List[str]:
        """
        获取文件中所有可用的通道名称
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            List[str]: 可用通道名称列表
        """
        pass
    
    @abstractmethod
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件元数据信息
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            Dict[str, Any]: 文件元数据
        """
        pass


class ReportWriter(ABC):
    """
    报表写入器抽象基类
    定义报表写入器规范，支持将分析结果写入不同格式的报表文件
    """
    
    @abstractmethod
    def write(self, output_path: str, report_data: ReportData) -> bool:
        """
        将报表数据写入文件
        
        Args:
            output_path: 输出文件路径
            report_data: 报表数据
            
        Returns:
            bool: 写入是否成功
            
        Raises:
            PermissionError: 文件写入权限不足
            ValueError: 报表数据格式错误
        """
        pass
    
    @abstractmethod
    def create_excel_report(self, output_path: str, report_data: ReportData) -> bool:
        """
        创建Excel格式的报表文件
        
        Args:
            output_path: 输出文件路径
            report_data: 报表数据
            
        Returns:
            bool: 创建是否成功
        """
        pass
    
    @abstractmethod
    def add_charts_to_report(self, report_path: str, chart_configs: List[Dict[str, Any]]) -> bool:
        """
        向报表中添加图表
        
        Args:
            report_path: 报表文件路径
            chart_configs: 图表配置列表
            
        Returns:
            bool: 添加是否成功
        """
        pass
