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
    
    def generate_report(self, config_path: str, input_file_path: str, output_file_path: str, functional_results: List[Dict[str, Any]] = None) -> str:
        """
        生成状态评估报表
        
        Args:
            config_path: 配置文件路径
            input_file_path: 输入数据文件路径
            output_file_path: 输出文件完整路径（包含文件名）
            functional_results: 功能计算汇总表的结果列表，每个元素包含ng_rundown, np_rundown, startup_time, ignition_time等字段
        
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
            
            # 5. 处理functional_result类型的评估项
            if functional_results is not None:
                functional_results_dict = self._process_functional_results(config, functional_results)
                results.update(functional_results_dict)
            
            # 6. 生成报表
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
        # 功能计算类评估项的ID列表
        functional_result_items = {'ngRundown', 'npRundown', 'startupTime', 'ignitionTime'}
        
        for eval_config in evaluations_config:
            item_id = eval_config.get('item', '')
            # 获取评估项的类型和条件逻辑，优先使用评估项中的值，如果没有则使用全局默认值
            eval_type = eval_config.get('type', default_type)
            # 如果item_id是功能计算类评估项，且没有显式设置type，则设置为functional_result
            if item_id in functional_result_items and eval_type == default_type:
                eval_type = 'functional_result'
            condition_logic = eval_config.get('conditionLogic', default_condition_logic)
            
            # functional_result类型需要特殊处理，但不跳过
            # 它们会从功能计算汇总表中读取数据
            
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
                # functional_result类型只需要logic和threshold，其他字段忽略
                if eval_type == 'functional_result':
                    condition = EvaluationCondition(
                        channel='',  # functional_result类型不需要通道
                        statistic='',  # functional_result类型不需要统计方法
                        duration=0.0,  # functional_result类型不需要持续时长
                        logic=cond_config.get('logic', '>'),
                        threshold=cond_config.get('threshold', 0.0)
                    )
                else:
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
        elif stat_lower in ['difference', '差值', 'diff', '差值计算']:
            return "difference"
        else:
            logger.warning(f"未知的统计类型: {statistic}，使用平均值代替")
            return "平均值"
    
    def _extract_channels(self, config: StatusEvalConfig) -> List[str]:
        """从配置中提取所有需要的通道名称"""
        channels = set()
        
        for eval_item in config.evaluations:
            # functional_result类型不需要通道数据
            if eval_item.type == 'functional_result':
                continue
            for condition in eval_item.conditions:
                if condition.channel:
                    channels.add(condition.channel)
        
        return list(channels)
    
    def _process_functional_results(self, config: StatusEvalConfig, functional_results: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        处理functional_result类型的评估项
        
        Args:
            config: 状态评估配置
            functional_results: 功能计算汇总表的结果列表
        
        Returns:
            评估结果字典 {item_id: "是" 或 "否"}
        """
        results = {}
        
        # 映射：评估项ID -> 功能计算字段名
        item_to_field = {
            'ngRundown': 'ng_rundown',
            'npRundown': 'np_rundown',
            'startupTime': 'startup_time',
            'ignitionTime': 'ignition_time'
        }
        
        # 遍历所有functional_result类型的评估项
        for eval_item in config.evaluations:
            if eval_item.type != 'functional_result':
                continue
            
            item_id = eval_item.item
            field_name = item_to_field.get(item_id)
            
            if not field_name:
                logger.warning(f"未找到评估项 {item_id} 对应的功能计算字段，跳过")
                results[item_id] = "是"  # 默认通过
                continue
            
            # 获取阈值（从conditions中获取）
            threshold = None
            logic = '>'
            if eval_item.conditions:
                threshold = eval_item.conditions[0].threshold
                logic = eval_item.conditions[0].logic
            
            if threshold is None:
                logger.warning(f"评估项 {item_id} 没有设置阈值，跳过")
                results[item_id] = "是"  # 默认通过
                continue
            
            # 从功能计算汇总表中提取所有对应的值
            values = []
            for result in functional_results:
                value = result.get(field_name)
                if value is not None:
                    values.append(value)
            
            if not values:
                logger.warning(f"评估项 {item_id} 在功能计算汇总表中没有找到数据，默认填'是'")
                results[item_id] = "是"
                continue
            
            # 判断逻辑：所有值是否均满足条件（大于阈值）
            # 若有不满足的，此单元格填否
            all_meet_condition = True
            for value in values:
                if logic == '>':
                    if not (value > threshold):
                        all_meet_condition = False
                        break
                elif logic == '>=':
                    if not (value >= threshold):
                        all_meet_condition = False
                        break
                elif logic == '<':
                    if not (value < threshold):
                        all_meet_condition = False
                        break
                elif logic == '<=':
                    if not (value <= threshold):
                        all_meet_condition = False
                        break
                elif logic == '==':
                    if not (abs(value - threshold) < 1e-9):
                        all_meet_condition = False
                        break
                else:
                    logger.warning(f"不支持的逻辑操作: {logic}，默认返回False")
                    all_meet_condition = False
                    break
            
            results[item_id] = "是" if all_meet_condition else "否"
            logger.info(f"评估项 {item_id} ({eval_item.assessment_name}): "
                       f"共{len(values)}个值，阈值={threshold}，逻辑={logic}，结果={results[item_id]}")
        
        return results

