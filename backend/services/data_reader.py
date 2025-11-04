"""
数据读取服务 - 读取CSV/Excel文件并转换为时序数据流
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    """单个数据点"""
    timestamp: float
    values: Dict[str, float]


@dataclass
class ChannelData:
    """通道数据"""
    channel_name: str
    data_points: List[DataPoint]


class DataReader:
    """数据读取器"""
    
    def __init__(self):
        self.time_columns = ['time', 'time[s]', 'Time', 'Time[s]', 'timestamp', 'Timestamp', 't', 'T', 'TIME', 'TIME[s]']
    
    def read_csv(self, file_path: str) -> pd.DataFrame:
        """读取CSV文件"""
        try:
            # 尝试多种编码
            for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"成功使用 {encoding} 编码读取文件")
                    return df
                except UnicodeDecodeError:
                    continue
            
            # 如果都失败了，使用默认编码并忽略错误
            df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
            logger.warning("使用错误容忍模式读取文件")
            return df
        except Exception as e:
            logger.error(f"读取CSV文件失败: {str(e)}")
            raise
    
    def read_excel(self, file_path: str) -> pd.DataFrame:
        """读取Excel文件"""
        try:
            df = pd.read_excel(file_path)
            return df
        except Exception as e:
            logger.error(f"读取Excel文件失败: {str(e)}")
            raise
    
    def read_file(self, file_path: str) -> pd.DataFrame:
        """读取文件（自动检测格式）"""
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        suffix = file_path_obj.suffix.lower()
        
        if suffix == '.csv':
            return self.read_csv(file_path)
        elif suffix in ['.xlsx', '.xls']:
            return self.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")
    
    def find_time_column(self, df: pd.DataFrame) -> Optional[str]:
        """查找时间列"""
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in [tc.lower() for tc in self.time_columns]:
                return col
        
        # 如果没找到标准名称，尝试识别第一列是否为时间
        if len(df.columns) > 0:
            first_col = df.columns[0]
            # 检查第一列是否为数值类型的递增序列
            try:
                data = pd.to_numeric(df[first_col], errors='coerce').dropna()
                if len(data) > 10 and all(data.iloc[i] <= data.iloc[i+1] for i in range(len(data)-1)):
                    logger.info(f"推断时间列: {first_col}")
                    return first_col
            except:
                pass
        
        return None
    
    def get_channel_columns(self, df: pd.DataFrame) -> List[str]:
        """获取通道列（排除时间列）"""
        time_col = self.find_time_column(df)
        channel_columns = []
        
        for col in df.columns:
            if col != time_col:
                channel_columns.append(col)
        
        return channel_columns
    
    def read_data_stream(self, file_path: str, channel_names: List[str]) -> List[Tuple[float, Dict[str, float]]]:
        """
        读取数据流，返回时序数据
        
        Returns:
            List of (timestamp, {channel_name: value}) tuples
        """
        df = self.read_file(file_path)
        
        # 查找时间列
        time_col = self.find_time_column(df)
        if not time_col:
            raise ValueError("未找到时间列")
        
        # 将时间列转换为数值
        time_data = pd.to_numeric(df[time_col], errors='coerce').fillna(0)
        
        data_stream = []
        for idx, timestamp in enumerate(time_data):
            values = {}
            for channel in channel_names:
                if channel in df.columns:
                    value = pd.to_numeric(df[channel].iloc[idx], errors='coerce')
                    values[channel] = value if not pd.isna(value) else 0.0
                else:
                    logger.warning(f"通道 {channel} 不存在于数据中")
                    values[channel] = 0.0
            
            data_stream.append((float(timestamp), values))
        
        logger.info(f"成功读取 {len(data_stream)} 个数据点")
        return data_stream

