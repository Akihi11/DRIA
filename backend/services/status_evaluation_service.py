"""
状态评估服务 - 统一的服务接口
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging

from backend.services.data_reader import DataReader
from backend.services.status_evaluation_calculator import (
    StatusEvaluationCalculator,
    StatusEvalConfig,
    EvaluationItem,
    EvaluationCondition
)
from backend.services.report_writer import ReportWriter

logger = logging.getLogger(__name__)


class StatusEvaluationService:
    """状态评估服务"""
    
    def __init__(self):
        self.data_reader = DataReader()
        self.report_writer = ReportWriter()
    
    def generate_report(self, config_path: str, input_file_path: str, output_file_path: str) -> str:
        """
        生成状态评估报表
        
        Args:
            config_path: 配置文件路径
            input_file_path: 输入数据文件路径
            output_file_path: 输出文件完整路径（包含文件名）
        
        Returns:
            输出文件路径
        """
        try:
            # 1. 读取配置
            config, assessment_content_map = self._load_config(config_path)
            
            # 2. 提取需要读取的通道列表
            channels = self._extract_channels(config)
            
            # 3. 读取数据流
            logger.info(f"读取数据文件: {input_file_path}")
            data_stream = self.data_reader.read_data_stream(
                input_file_path,
                channels
            )
            
            # 4. 执行计算
            logger.info("开始状态评估计算...")
            calculator = StatusEvaluationCalculator(config)
            results = calculator.calculate(data_stream)
            
            # 5. 生成报表
            logger.info("生成状态评估报表...")
            output_path = Path(output_file_path)
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_writer.create_status_eval_report(
                results, 
                config.evaluations,
                str(output_path),
                assessment_content_map
            )
            
            logger.info(f"状态评估报表生成完成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"生成状态评估报表失败: {str(e)}")
            raise
    
    def _load_config(self, config_path: str) -> Tuple[StatusEvalConfig, Dict[str, str]]:
        """加载配置
        
        Returns:
            (StatusEvalConfig, assessment_content_map): 配置对象和评估内容描述映射
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        report_config = config_data.get('reportConfig', {})
        
        # 获取状态评估配置
        status_eval = report_config.get('statusEval', {})
        evaluations_config = status_eval.get('evaluations', [])
        
        # 获取评估内容描述映射
        assessment_content_map = status_eval.get('assessment_content_map', {})
        
        # 获取全局默认值（从statusEval层级）
        default_type = status_eval.get('type', 'continuous_check')
        default_condition_logic = status_eval.get('conditionLogic', 'AND')
        
        # 解析评估项
        evaluations = []
        for eval_config in evaluations_config:
            # 获取评估项的类型和条件逻辑，优先使用评估项中的值，如果没有则使用全局默认值
            eval_type = eval_config.get('type', default_type)
            condition_logic = eval_config.get('conditionLogic', default_condition_logic)
            
            # 跳过functional_result类型（这次不实现）
            if eval_type == 'functional_result':
                logger.info(f"跳过functional_result类型评估项: {eval_config.get('item', 'unknown')}")
                continue
            
            # 解析条件
            conditions = []
            conditions_config = eval_config.get('conditions', [])
            
            # 兼容event_check类型（将其转换为continuous_check）
            if eval_type == 'event_check':
                # event_check类型只有一个condition，转换为conditions数组
                condition_config = eval_config.get('condition', {})
                if condition_config:
                    conditions_config = [condition_config]
                eval_type = 'continuous_check'
            
            for cond_config in conditions_config:
                # 兼容event_check格式：使用type字段作为statistic
                statistic = cond_config.get('statistic') or cond_config.get('type', '平均值')
                
                condition = EvaluationCondition(
                    channel=cond_config.get('channel', ''),
                    statistic=self._normalize_statistic(statistic),
                    duration=cond_config.get('duration', 1.0),
                    logic=cond_config.get('logic', '>'),
                    threshold=cond_config.get('threshold', 0.0)
                )
                conditions.append(condition)
            
            # 构建评估项
            evaluation = EvaluationItem(
                item=eval_config.get('item', ''),
                assessment_name=eval_config.get('assessmentName', eval_config.get('item', '')),
                type=eval_type,
                condition_logic=condition_logic,
                conditions=conditions
            )
            evaluations.append(evaluation)
        
        config = StatusEvalConfig(evaluations=evaluations)
        logger.info(f"加载状态评估配置完成，评估项数量: {len(evaluations)}")
        return config, assessment_content_map
    
    def _normalize_statistic(self, statistic: str) -> str:
        """标准化统计方法名称"""
        if not statistic:
            return "平均值"
        
        stat_lower = statistic.lower()
        if stat_lower in ['average', '平均值', 'mean', 'avg']:
            return "平均值"
        elif stat_lower in ['max', '最大值', 'maximum']:
            return "最大值"
        elif stat_lower in ['min', '最小值', 'minimum']:
            return "最小值"
        elif stat_lower in ['rms', '有效值', 'rootmeansquare']:
            return "有效值"
        elif stat_lower in ['instant', '瞬时值', 'instantaneous']:
            return "瞬时值"
        elif stat_lower in ['difference', '差值', 'diff']:
            return "difference"
        else:
            logger.warning(f"未知的统计类型: {statistic}，使用平均值代替")
            return "平均值"
    
    def _extract_channels(self, config: StatusEvalConfig) -> List[str]:
        """从配置中提取所有需要的通道名称"""
        channels = set()
        
        for eval_item in config.evaluations:
            for condition in eval_item.conditions:
                if condition.channel:
                    channels.add(condition.channel)
        
        return list(channels)

