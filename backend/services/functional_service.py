"""
功能计算服务 - 统一的服务接口
"""
import json
from pathlib import Path
from typing import Dict, Any
import logging

from backend.services.data_reader import DataReader
from backend.services.functional_calculator import FunctionalCalculator, FunctionalCalcConfig

logger = logging.getLogger(__name__)


class FunctionalService:
    """功能计算服务"""
    
    def __init__(self):
        self.data_reader = DataReader()
    
    def generate_report(self, config_path: str, input_file_path: str, output_file_path: str) -> str:
        """
        生成功能计算汇总表
        
        Args:
            config_path: 配置文件路径
            input_file_path: 输入数据文件路径
            output_file_path: 输出文件完整路径（包含文件名）
        
        Returns:
            输出文件路径
        """
        try:
            # 1. 读取配置
            config = self._load_config(config_path)
            
            # 2. 获取需要读取的通道列表
            channels = self._extract_channels(config)
            
            # 3. 读取数据流
            logger.info(f"读取数据文件: {input_file_path}")
            data_stream = self.data_reader.read_data_stream(
                input_file_path,
                channels
            )
            
            # 4. 执行计算
            logger.info("开始功能计算...")
            calculator = FunctionalCalculator(config)
            calculator.process_data_stream(data_stream)
            
            # 5. 导出到Excel
            logger.info("导出Excel文件...")
            output_path = Path(output_file_path)
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            calculator.export_to_excel(str(output_path))
            
            logger.info(f"功能计算汇总表生成完成: {output_path}")
            # 返回结果路径和计算器结果
            return {
                'output_path': str(output_path),
                'calculator': calculator
            }
            
        except Exception as e:
            logger.error(f"生成功能计算汇总表失败: {str(e)}")
            raise
    
    def generate_report_simple(self, config_path: str, input_file_path: str, output_file_path: str) -> str:
        """
        生成功能计算汇总表（简化版本，只返回路径）
        
        Args:
            config_path: 配置文件路径
            input_file_path: 输入数据文件路径
            output_file_path: 输出文件完整路径（包含文件名）
        
        Returns:
            输出文件路径
        """
        result = self.generate_report(config_path, input_file_path, output_file_path)
        if isinstance(result, dict):
            return result['output_path']
        return result
    
    def _load_config(self, config_path: str) -> FunctionalCalcConfig:
        """加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        report_config = config_data.get('reportConfig', {})
        
        # 获取功能计算配置
        functional_calc = report_config.get('functionalCalc', {})
        
        # 解析各个配置项
        config = FunctionalCalcConfig(
            time_base=functional_calc.get('time_base'),
            startup_time=functional_calc.get('startup_time'),
            ignition_time=functional_calc.get('ignition_time'),
            rundown_ng=functional_calc.get('rundown_ng'),
            rundown_np=functional_calc.get('rundown_np')
        )
        
        return config
    
    def _extract_channels(self, config: FunctionalCalcConfig) -> list:
        """从配置中提取所有需要的通道名称"""
        channels = set()
        
        if config.time_base:
            channels.add(config.time_base.get('channel'))
        
        if config.startup_time:
            channels.add(config.startup_time.get('channel'))
        
        if config.ignition_time:
            channels.add(config.ignition_time.get('channel'))
        
        if config.rundown_ng:
            channels.add(config.rundown_ng.get('channel'))
        
        if config.rundown_np:
            channels.add(config.rundown_np.get('channel'))
        
        return list(channels)

