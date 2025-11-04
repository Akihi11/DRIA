"""
通道分析服务 - 自动分析上传文件的通道数据
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ChannelAnalysisService:
    """通道分析服务类"""
    
    def __init__(self):
        self.time_columns = ['time', 'time[s]', 'Time', 'Time[s]', 'timestamp', 'Timestamp', 't', 'T']
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        分析文件中的通道数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含通道分析结果的字典
        """
        try:
            # 读取文件
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 根据文件扩展名选择读取方法
            if file_path_obj.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_path_obj.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {file_path_obj.suffix}")
            
            # 检查数据是否为空
            if df.empty:
                raise ValueError("文件为空")
            
            # 获取通道列
            channel_columns = self._get_channel_columns(df)
            
            if not channel_columns:
                raise ValueError("未找到有效的通道数据列")
            
            # 分析每个通道
            channel_stats = []
            for channel in channel_columns:
                try:
                    stats = self._analyze_channel(df, channel)
                    if stats:
                        channel_stats.append(stats)
                except Exception as e:
                    logger.warning(f"分析通道 {channel} 时出错: {str(e)}")
                    continue
            
            if not channel_stats:
                raise ValueError("没有找到有效的通道数据")
            
            return {
                "success": True,
                "total_channels": len(channel_stats),
                "channels": channel_stats,
                "file_info": {
                    "filename": file_path_obj.name,
                    "total_rows": len(df),
                    "total_columns": len(df.columns)
                }
            }
            
        except Exception as e:
            logger.error(f"文件分析失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "channels": [],
                "total_channels": 0
            }
    
    def _get_channel_columns(self, df: pd.DataFrame) -> List[str]:
        """获取通道列名（排除时间列）"""
        all_columns = df.columns.tolist()
        channel_columns = []
        
        for col in all_columns:
            col_lower = col.lower().strip()
            # 检查是否是时间列
            is_time_column = any(time_col.lower() in col_lower for time_col in self.time_columns)
            
            if not is_time_column:
                channel_columns.append(col)
        
        return channel_columns
    
    def _analyze_channel(self, df: pd.DataFrame, channel_name: str) -> Optional[Dict[str, Any]]:
        """分析单个通道的统计数据"""
        try:
            # 获取数值数据，排除NaN值
            data = pd.to_numeric(df[channel_name], errors='coerce').dropna()
            
            if len(data) == 0:
                logger.warning(f"通道 {channel_name} 没有有效数据")
                return None
            
            # 计算统计值
            stats = {
                "channel_name": channel_name,
                "count": int(len(data)),
                "mean": float(data.mean()),
                "max_value": float(data.max()),
                "min_value": float(data.min()),
                "std_dev": float(data.std()),
                "range": float(data.max() - data.min())
            }
            
            # 添加更多统计信息
            stats.update({
                "median": float(data.median()),
                "q25": float(data.quantile(0.25)),
                "q75": float(data.quantile(0.75)),
                "variance": float(data.var())
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"分析通道 {channel_name} 失败: {str(e)}")
            return None
    
    def format_analysis_result(self, analysis_result: Dict[str, Any]) -> str:
        """格式化分析结果为可读文本"""
        if not analysis_result.get("success", False):
            return f"❌ 文件分析失败: {analysis_result.get('error', '未知错误')}"
        
        channels = analysis_result.get("channels", [])
        total_channels = analysis_result.get("total_channels", 0)
        file_info = analysis_result.get("file_info", {})
        
        # 构建结果文本
        result_text = f"📊 **文件分析完成**\n\n"
        result_text += f"📁 文件: {file_info.get('filename', '未知')}\n"
        result_text += f"📈 总行数: {file_info.get('total_rows', 0)}\n"
        result_text += f"🔢 总列数: {file_info.get('total_columns', 0)}\n"
        result_text += f"📡 **发现 {total_channels} 个数据通道:**\n\n"
        
        # 添加每个通道的统计信息
        for i, channel in enumerate(channels, 1):
            result_text += f"**{i}. {channel['channel_name']}**\n"
            result_text += f"   • 数据点数: {channel['count']}\n"
            result_text += f"   • 均值: {channel['mean']:.4f}\n"
            result_text += f"   • 最大值: {channel['max_value']:.4f}\n"
            result_text += f"   • 最小值: {channel['min_value']:.4f}\n"
            result_text += f"   • 标准差: {channel['std_dev']:.4f}\n"
            result_text += f"   • 范围: {channel['range']:.4f}\n\n"
        
        return result_text
