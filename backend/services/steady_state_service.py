"""
稳定状态服务 - 统一的服务接口
"""
import json
from pathlib import Path
from typing import Dict, Any
import logging

from backend.services.data_reader import DataReader
from backend.services.steady_state_calculator import SteadyStateCalculator, StableStateConfig, TriggerConfig
from backend.services.report_writer import ReportWriter

logger = logging.getLogger(__name__)


class SteadyStateService:
    """稳定状态服务"""
    
    def __init__(self):
        self.data_reader = DataReader()
        self.report_writer = ReportWriter()
    
    def generate_report(self, config_path: str, input_file_path: str, output_file_path: str) -> str:
        """
        生成稳定状态报表
        
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
            
            # 2. 读取数据流
            logger.info(f"读取数据文件: {input_file_path}")
            data_stream = self.data_reader.read_data_stream(
                input_file_path,
                config.display_channels
            )
            
            # 3. 执行计算
            logger.info("开始计算...")
            calculator = SteadyStateCalculator(config)
            snapshots = calculator.calculate(data_stream)
            
            # 4. 生成报表
            logger.info("生成报表...")
            output_path = Path(output_file_path)
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_writer.create_report(snapshots, str(output_path))
            
            logger.info(f"报表生成完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"生成报表失败: {str(e)}")
            raise
    
    def _load_config(self, config_path: str) -> StableStateConfig:
        """加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        report_config = config_data.get('reportConfig', {})
        
        # 获取稳定状态配置
        stable_state = report_config.get('stableState', {})
        
        # 显示通道
        display_channels = stable_state.get('displayChannels', [])
        
        # 触发逻辑
        condition_logic = stable_state.get('conditionLogic', 'AND')
        conditions = stable_state.get('conditions', [])
        
        # 解析条件
        condition1 = None
        condition2 = None
        
        for condition in conditions:
            condition_type = condition.get('type', '')
            # 支持中英文类型标识（处理大小写和中文）
            if condition_type.lower() in ['statistic', '统计值']:
                condition1 = {
                    'enabled': True,
                    'channel': condition.get('channel'),
                    'statistic': self._translate_statistic(condition.get('statistic', 'Average')),
                    'duration_sec': condition.get('duration', 1.0),
                    'logic': self._translate_logic(condition.get('logic', '>')),
                    'threshold': condition.get('threshold', 0.0)
                }
            elif condition_type.lower() in ['amplitude_change', '变化幅度']:
                condition2 = {
                    'enabled': True,
                    'channel': condition.get('channel'),
                    'statistic': self._translate_statistic(condition.get('statistic', 'RateOfChange')),
                    'duration_sec': condition.get('duration', 1.0),
                    'logic': self._translate_logic(condition.get('logic', '<')),
                    'threshold': condition.get('threshold', 0.0)
                }
        
        # 构建触发配置
        trigger_config = TriggerConfig(
            combination=self._translate_combination(condition_logic),
            condition1=condition1,
            condition2=condition2
        )
        
        # 构建稳定状态配置
        stable_state_config = StableStateConfig(
            display_channels=display_channels,
            trigger_logic=trigger_config
        )
        
        return stable_state_config
    
    def _translate_statistic(self, statistic: str) -> str:
        """翻译统计方法"""
        translation = {
            '平均值': 'Average',
            '最大值': 'Max',
            '最小值': 'Min',
            '有效值': 'RMS',
            '变化率': 'RateOfChange',
            '变化幅度': 'RateOfChange',
            'Average': 'Average',
            'Max': 'Max',
            'Min': 'Min',
            'RMS': 'RMS',
            'RateOfChange': 'RateOfChange'
        }
        # 如果未找到，且原值是RateOfChange相关，返回RateOfChange；否则返回Average
        if statistic and ('rate' in statistic.lower() or 'change' in statistic.lower() or '变化' in statistic):
            return translation.get(statistic, 'RateOfChange')
        return translation.get(statistic, 'Average')
    
    def _translate_logic(self, logic: str) -> str:
        """翻译逻辑操作符"""
        translation = {
            '大于': '>',
            '小于': '<',
            '大于等于': '>=',
            '小于等于': '<=',
            '等于': '==',
            # 如果已经是符号，保持不变
            '>': '>',
            '<': '<',
            '>=': '>=',
            '<=': '<=',
            '==': '=='
        }
        return translation.get(logic, logic)
    
    def _translate_combination(self, combination: str) -> str:
        """翻译组合逻辑"""
        if combination.upper() == 'AND':
            return 'AND'
        elif combination.upper() == 'COND1_ONLY':
            return 'Cond1_Only'
        elif combination.upper() == 'COND2_ONLY':
            return 'Cond2_Only'
        else:
            return 'Cond1_Only'

