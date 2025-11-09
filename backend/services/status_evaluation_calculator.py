"""
状态评估计算器 - V3.3.1 (NameError 修复版)
根据配置文件扫描整个数据流

V3.3.1 - 修复了 evaluate_normal_condition 中的 "NameError: 'idx' is not defined"
"""
import numpy as np
from collections import deque
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
import logging

# 假设 SlidingWindow (V3.2) 已经从 functional_calculator 导入
# （这行是根据你的 turn_211 代码来的）
from backend.services.functional_calculator import SlidingWindow

logger = logging.getLogger(__name__)


@dataclass
class EvaluationCondition:
    """评估条件配置"""
    channel: str
    statistic: str
    duration: float
    logic: str
    threshold: float


@dataclass
class EvaluationItem:
    """评估项配置"""
    item: str
    assessment_name: str
    type: str
    condition_logic: str
    conditions: List[EvaluationCondition]


@dataclass
class StatusEvalConfig:
    """状态评估配置"""
    evaluations: List[EvaluationItem]


class StatusEvaluationCalculator:
    """状态评估计算器 - "不满足则否决"机制"""
    
    def __init__(self, config: StatusEvalConfig):
        self.config = config
        self.results = {}  # {item_id: "是" 或 "否"}
        
        # 滑动窗口字典
        self.windows = {}  # {key: SlidingWindow}
        self.difference_windows = {}  # {key: SlidingWindow} 用于difference统计
        
        # 窗口键到通道的映射
        self._window_keys_to_channels = []
        self._diff_window_keys_to_channels = []
        
        # 初始化结果字典和滑动窗口
        self._initialize()
    
    def _initialize(self):
        """初始化结果字典和滑动窗口"""
        # 1. 初始化所有评估项的结论为"是"（通过）
        for eval_item in self.config.evaluations:
            # 跳过functional_result类型（这次不实现）
            if eval_item.type == "functional_result":
                continue
            
            self.results[eval_item.item] = "是"
            
            # 2. 为每个条件初始化滑动窗口
            for idx, condition in enumerate(eval_item.conditions):
                channel = condition.channel
                statistic = condition.statistic
                duration = condition.duration
                
                # 对于"瞬时值"类型，如果duration为None，不需要创建窗口（直接使用当前值）
                if statistic == "瞬时值" and duration is None:
                    continue
                
                # 对于其他类型，如果duration为None，使用默认值1
                if duration is None:
                    duration = 1
                    logger.warning(f"条件 {eval_item.item} 的 duration 为 None，使用默认值 1")
                
                # 生成唯一的窗口键
                key = f"{eval_item.item}_cond{idx}_{channel}_{statistic}_{duration}s"
                
                if statistic == "difference" or statistic == "差值计算":
                    # 差值窗口：用于存储历史值，计算当前值减去duration秒前的值
                    if key not in self.difference_windows:
                        self.difference_windows[key] = SlidingWindow(duration, "瞬时值")
                        self._diff_window_keys_to_channels.append((key, channel))
                else:
                    # 普通统计窗口
                    if key not in self.windows:
                        self.windows[key] = SlidingWindow(duration, statistic)
                        self._window_keys_to_channels.append((key, channel))
        
        logger.info(f"状态评估计算器初始化完成，评估项数量: {len(self.results)}")
        logger.info(f"滑动窗口数量: {len(self.windows)}, 差值窗口数量: {len(self.difference_windows)}")
    
    def _update_all_windows(self, timestamp: float, data_point: Dict[str, float]):
        """统一更新所有滑动窗口"""
        # 更新普通统计窗口
        for key, channel in self._window_keys_to_channels:
            if channel in data_point:
                self.windows[key].update(timestamp, data_point[channel])
        
        # 更新差值窗口
        for key, channel in self._diff_window_keys_to_channels:
            if channel in data_point:
                self.difference_windows[key].update(timestamp, data_point[channel])
    
    def evaluate_logic(self, value: float, logic: str, threshold: float) -> bool:
        """评估逻辑条件"""
        if logic == ">":
            return value > threshold
        elif logic == "<":
            return value < threshold
        elif logic == ">=":
            return value >= threshold
        elif logic == "<=":
            return value <= threshold
        elif logic == "==":
            return abs(value - threshold) < 1e-9  # 浮点数相等比较
        else:
            logger.warning(f"不支持的逻辑操作: {logic}，默认返回False")
            return False
    
    def evaluate_normal_condition(
        self, 
        condition: EvaluationCondition, 
        eval_item: EvaluationItem,
        condition_idx: int, # <--- (turn_223) 函数定义
        timestamp: float,
        data_point: Dict[str, float]
    ) -> bool:
        """
        计算单个"正常条件"是否为True
        
        Returns:
            True表示"正常条件"满足（通过），False表示"正常条件"不满足（失败）
        """
        channel = condition.channel
        statistic = condition.statistic
        duration = condition.duration
        logic = condition.logic
        threshold = condition.threshold
        
        # 检查通道是否存在
        if channel not in data_point:
            logger.warning(f"通道 {channel} 不在数据点中，跳过此条件")
            return False
        
        value_to_check = None
        
        # --- (!!!) V3.3.1 修复：
        #    我把 'idx' 改成了 'condition_idx'
        log_key = f"{eval_item.item}_cond{condition_idx}" # (日志)
        # --- (修复结束) ---
        
        # 生成窗口键
        key = f"{eval_item.item}_cond{condition_idx}_{channel}_{statistic}_{duration}s"
        
        if statistic == "difference" or statistic == "差值计算":
            # 喘振逻辑：当前瞬时值减去duration秒前的瞬时值
            if key not in self.difference_windows:
                logger.warning(f"差值窗口 {key} 不存在")
                return False
            
            window = self.difference_windows[key]
            current_val = data_point[channel]
            oldest_val = window.get_oldest_value()
            
            if oldest_val is None:
                logger.debug(f"evaluate_normal_condition [{log_key}]: (差值计算) 窗口未满. -> True (Normal)")
                return True # 窗口未满，我们假设它是“正常”的
            
            value_to_check = current_val - oldest_val
        
        elif statistic == "瞬时值":
            # 直接使用当前瞬时值
            value_to_check = data_point[channel]
        
        else:
            # 平均值、最大值、最小值、有效值
            if key not in self.windows:
                logger.warning(f"统计窗口 {key} 不存在")
                return False
            
            window = self.windows[key]
            value_to_check = window.calculate_statistic()
            
            if value_to_check is None:
                logger.debug(f"evaluate_normal_condition [{log_key}]: ({statistic}) 窗口未满. -> True (Normal)")
                return True # 窗口未满，同上，我们假设它是“正常”的
        
        # 评估逻辑条件 (e.g., 检查 "0 < 18000" 是否为 True)
        result = self.evaluate_logic(value_to_check, logic, threshold)
        
        # (V3.3.1 日志)
        logger.debug(
            f"evaluate_normal_condition [{log_key}]: "
            f"({statistic} Val: {value_to_check:.2f}) {logic} {threshold}? -> {result}"
        )
        
        return result
    
    def calculate(self, data_stream: List[Tuple[float, Dict[str, float]]]) -> Dict[str, str]:
        """
        执行计算，返回评估结果字典
        """
        logger.info(f"开始状态评估计算，数据点数量: {len(data_stream)}")
        
        # 逐点扫描数据流
        for timestamp, data_point in data_stream:
            # 1. 统一更新所有滑动窗口
            self._update_all_windows(timestamp, data_point)
            
            # 2. 遍历配置中的所有评估项（保持顺序）
            for eval_item in self.config.evaluations:
                # 跳过functional_result类型
                if eval_item.type == "functional_result":
                    continue
                
                item_id = eval_item.item
                
                # 优化：如果已经失败了，就没必要在这个数据点上再算了
                if self.results[item_id] == "否":
                    continue
                
                # 3. 检查所有 "正常" 条件
                condition_results = []
                
                for idx, condition in enumerate(eval_item.conditions):
                    # 检查这个单独的"正常"条件是否为True
                    is_met = self.evaluate_normal_condition(
                        condition, 
                        eval_item, 
                        idx, # <--- (turn_223) 这里传 'idx'
                        timestamp, 
                        data_point
                    )
                    condition_results.append(is_met)
                
                # (V3.3 核心修复)
                
                all_normal_conditions_met = all(condition_results)
                
                # 4. 逻辑翻转（遵循S1文档）
                #    "若有不满足的 (if not all_normal_conditions_met), 
                #     此单元格填否"
                
                if not all_normal_conditions_met:
                    # 核心逻辑：一票否决
                    self.results[item_id] = "否"
                    logger.info(
                        f"评估项 [{eval_item.assessment_name}] 在 T={timestamp:.3f}s 触发失败 (不满足'正常'条件)，"
                        f"条件结果: {condition_results}"
                    )
        
        logger.info(f"状态评估计算完成，结果: {self.results}")
        return self.results