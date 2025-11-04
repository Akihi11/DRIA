"""
稳定状态计算引擎 - 根据触发条件抓取满足条件的时刻快照
"""
import numpy as np
from collections import deque
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """触发配置"""
    combination: str  # "Cond1_Only", "Cond2_Only", "AND"
    condition1: Optional[Dict[str, Any]]
    condition2: Optional[Dict[str, Any]]


@dataclass
class StableStateConfig:
    """稳定状态配置"""
    display_channels: List[str]
    trigger_logic: TriggerConfig


class SteadyStateCalculator:
    """稳定状态计算器"""
    
    def __init__(self, config: StableStateConfig):
        self.config = config
        self.window_cond1 = None
        self.window_cond2 = None
        
        # 初始化窗口
        if config.trigger_logic.condition1 and config.trigger_logic.condition1.get('enabled', False):
            self.window_cond1 = deque()
        
        if config.trigger_logic.condition2 and config.trigger_logic.condition2.get('enabled', False):
            self.window_cond2 = deque()
        
        # 状态变量
        self.cond1_last_state = False
        self.cond1_first_trigger = True  # 标记是否第一次触发
        self.cond2_last_state = False
        self.final_trigger_last_state = False  # 保存final_trigger的上一次状态，用于上升沿检测
        self.cond2_last_recorded_value = None
        self.cond2_last_recorded_time = 0.0
        
        # 日志控制标志
        self._window_size_100_logged = False  # 标记是否已记录窗口大小100的日志
        self._cond1_not_enabled_warned = False  # 标记是否已警告条件一未启用
        self._cond2_not_enabled_warned = False  # 标记是否已警告条件二未启用
        
        # 记录结果
        self.snapshots = []
    
    def calculate_statistic(self, values: List[float], statistic_type: str) -> float:
        """计算统计值"""
        if not values:
            return 0.0
        
        array = np.array(values)
        
        # 支持中英文统计类型
        stat_lower = statistic_type.lower() if statistic_type else 'average'
        
        # 调试：首次调用时记录统计类型识别
        if not hasattr(self, '_stat_debug_logged'):
            logger.info(f"[统计识别] 原始statistic_type={statistic_type}, lower后={stat_lower}")
            self._stat_debug_logged = True
        
        if stat_lower in ['average', '平均值', 'mean', 'avg']:
            result = float(np.mean(array))
            if len(values) == 100 and not hasattr(self, '_first_avg_calc'):
                logger.info(f"[使用平均值] 窗口大小={len(values)}, 平均值={result:.2f}")
                self._first_avg_calc = True
            return result
        elif stat_lower in ['max', '最大值', 'maximum']:
            result = float(np.max(array))
            if len(values) == 100 and not hasattr(self, '_first_max_calc'):
                logger.warning(f"[使用最大值] 窗口大小={len(values)}, 最大值={result:.2f}")
                self._first_max_calc = True
            return result
        elif stat_lower in ['min', '最小值', 'minimum']:
            return float(np.min(array))
        elif stat_lower in ['rms', '有效值', 'rootmeansquare']:
            return float(np.sqrt(np.mean(array ** 2)))
        else:
            logger.warning(f"未知的统计类型: {statistic_type} (lower={stat_lower})，使用平均值代替")
            return float(np.mean(array))
    
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
        else:
            raise ValueError(f"不支持的逻辑操作: {logic}")
    
    def update_window(self, window: deque, current_time: float, duration_sec: float, value: float):
        """更新滑动窗口，移除过期数据，添加新数据"""
        # 移除过期数据
        # 窗口大小是 duration_sec 秒，窗口范围：(current_time - duration_sec, current_time]（左开右闭区间）
        # 保留时间戳 > (current_time - duration_sec) 且 <= current_time 的数据
        # 所以移除时间戳 <= (current_time - duration_sec) 的数据
        # 例如：current_time=1.00s, duration=1.0s，窗口是 (0.00s, 1.00s] = [0.01s, 1.00s]，包含100个点
        #      current_time=1.01s, duration=1.0s，窗口是 (0.01s, 1.01s] = [0.02s, 1.01s]，包含100个点
        cutoff_time = current_time - duration_sec
        while window and window[0][0] <= cutoff_time:
            window.popleft()
        
        # 添加新数据
        window.append((current_time, value))
    
    def check_condition1(self, current_time: float, data_point: Dict[str, float]) -> Tuple[bool, float]:
        """检查条件1（统计型）"""
        # 检查配置是否存在
        if not self.config.trigger_logic.condition1:
            return False, 0.0
        
        cond1 = self.config.trigger_logic.condition1
        if not cond1.get('enabled', False):
            return False, 0.0
        
        # 如果窗口未初始化，初始化它
        if self.window_cond1 is None:
            self.window_cond1 = deque()
        
        channel = cond1.get('channel')
        if channel not in data_point:
            logger.warning(f"通道 {channel} 不在数据点中")
            return False, 0.0
        
        # 更新窗口
        duration = cond1.get('duration_sec', 1.0)
        self.update_window(self.window_cond1, current_time, duration, data_point[channel])
        
        # 如果窗口数据不足，返回False（至少需要1个点）
        if len(self.window_cond1) < 1:
            return False, 0.0
        
        # 提取窗口内的值
        window_values = [item[1] for item in self.window_cond1]
        
        # 计算统计值
        statistic_type = cond1.get('statistic', 'Average')
        # 调试：记录统计方法（仅在关键点记录一次）
        window_size = len(self.window_cond1)
        if window_size == 1:
            logger.info(f"[统计方法] 窗口初始化: statistic参数={statistic_type} (类型: {type(statistic_type)}), 窗口大小={window_size}")
        elif window_size == 100 and not self._window_size_100_logged:
            logger.info(f"[统计方法] 窗口已满: statistic参数={statistic_type} (类型: {type(statistic_type)}), 窗口大小={window_size}")
            self._window_size_100_logged = True
        current_stat = self.calculate_statistic(window_values, statistic_type)
        
        # 调试：在关键点显示计算细节
        if len(self.window_cond1) == 100 and current_time < 1.5:
            window_sample = window_values[:5] if len(window_values) >= 5 else window_values
            logger.info(f"[计算详情] time={current_time:.3f}s, statistic={statistic_type}, "
                       f"窗口值样本={window_sample}, 计算结果={current_stat:.2f}")
        
        # 评估条件：直接使用阈值进行比较
        logic = cond1.get('logic', '>')
        threshold = cond1.get('threshold', 0.0)
        cond1_met = self.evaluate_logic(current_stat, logic, threshold)
        
        return cond1_met, current_stat
    
    def check_condition2(self, current_time: float, data_point: Dict[str, float]) -> Tuple[bool, float]:
        """检查条件2（变化率型）"""
        # 检查配置是否存在
        if not self.config.trigger_logic.condition2:
            return False, 0.0
        
        cond2 = self.config.trigger_logic.condition2
        if not cond2.get('enabled', False):
            return False, 0.0
        
        # 如果窗口未初始化，初始化它
        if self.window_cond2 is None:
            self.window_cond2 = deque()
        
        channel = cond2.get('channel')
        if channel not in data_point:
            logger.warning(f"通道 {channel} 不在数据点中")
            return False, 0.0
        
        # 更新窗口
        duration = cond2.get('duration_sec', 1.0)
        self.update_window(self.window_cond2, current_time, duration, data_point[channel])
        
        # 如果窗口数据不足，返回False（至少需要2个点才能计算变化率）
        if len(self.window_cond2) < 2:
            return False, 0.0
        
        # 提取窗口内的值
        window_values = [item[1] for item in self.window_cond2]
        
        # 计算变化率（最大值 - 最小值）
        current_max = float(np.max(window_values))
        current_min = float(np.min(window_values))
        current_change = current_max - current_min
        
        # 评估条件
        logic = cond2.get('logic', '>')
        threshold = cond2.get('threshold', 0.0)
        cond2_met = self.evaluate_logic(current_change, logic, threshold)
        
        return cond2_met, current_change
    
    def calculate(self, data_stream: List[Tuple[float, Dict[str, float]]]) -> List[Dict[str, Any]]:
        """
        执行计算，返回快照列表
        
        Args:
            data_stream: 时序数据流，每个元素为 (timestamp, {channel: value})
        
        Returns:
            快照列表，每个快照包含时间和所有显示通道的值
        """
        snapshots = []
        
        # 调试：记录配置信息
        combination = self.config.trigger_logic.combination
        logger.info(f"[计算开始] 组合逻辑={combination}")
        if self.config.trigger_logic.condition1:
            cond1 = self.config.trigger_logic.condition1
            logger.info(f"[条件一配置] enabled={cond1.get('enabled', False)}, channel={cond1.get('channel')}, "
                       f"statistic={cond1.get('statistic')}, duration={cond1.get('duration_sec')}, "
                       f"logic={cond1.get('logic')}, threshold={cond1.get('threshold')}")
        else:
            logger.warning("[条件一配置] 未配置")
        
        if self.config.trigger_logic.condition2:
            cond2 = self.config.trigger_logic.condition2
            logger.info(f"[条件二配置] enabled={cond2.get('enabled', False)}, channel={cond2.get('channel')}, "
                       f"duration={cond2.get('duration_sec')}, logic={cond2.get('logic')}, "
                       f"threshold={cond2.get('threshold')}")
        else:
            logger.warning("[条件二配置] 未配置")
        
        # 调试：统计信息
        debug_count = 0
        cond1_met_count = 0
        record_count = 0
        
        for current_time, data_point in data_stream:
            cond1_met = False
            cond2_met = False
            
            # 先获取组合逻辑，用于后续判断
            combination = self.config.trigger_logic.combination
            
            # 检查条件1
            current_stat1 = 0.0
            cond1_checked = False
            if self.config.trigger_logic.condition1 and self.config.trigger_logic.condition1.get('enabled', False):
                cond1_met, current_stat1 = self.check_condition1(current_time, data_point)
                cond1_checked = True
            else:
                # 条件一未启用或未配置，在AND模式下应该阻止触发
                if combination == "AND":
                    if not self._cond1_not_enabled_warned:
                        logger.warning(f"[AND模式] 条件一未启用或未配置，时间={current_time:.3f}s（此警告仅显示一次）")
                        self._cond1_not_enabled_warned = True
                    cond1_met = False
            
            # 检查条件2
            current_change = 0.0
            cond2_checked = False
            if self.config.trigger_logic.condition2 and self.config.trigger_logic.condition2.get('enabled', False):
                cond2_met, current_change = self.check_condition2(current_time, data_point)
                cond2_checked = True
            else:
                # 条件二未启用或未配置，在AND模式下应该阻止触发
                if combination == "AND":
                    if not self._cond2_not_enabled_warned:
                        logger.warning(f"[AND模式] 条件二未启用或未配置，时间={current_time:.3f}s（此警告仅显示一次）")
                        self._cond2_not_enabled_warned = True
                    cond2_met = False
            
            # 组合最终触发条件
            final_trigger = False
            
            if combination == "Cond1_Only":
                final_trigger = cond1_met
            elif combination == "Cond2_Only":
                final_trigger = cond2_met
            elif combination == "AND":
                # AND模式：必须两个条件都满足
                final_trigger = cond1_met and cond2_met
                # 如果只有一个条件满足，记录警告
                if cond1_met and not cond2_met:
                    if debug_count <= 20 or (current_time < 5.0):
                        logger.warning(f"[AND模式] 仅条件一满足: time={current_time:.3f}s, "
                                     f"cond1_met={cond1_met}, cond2_met={cond2_met}, "
                                     f"stat1={current_stat1:.2f}, change={current_change:.2f}")
                elif cond2_met and not cond1_met:
                    if debug_count <= 20 or (current_time < 5.0):
                        logger.warning(f"[AND模式] 仅条件二满足: time={current_time:.3f}s, "
                                     f"cond1_met={cond1_met}, cond2_met={cond2_met}, "
                                     f"stat1={current_stat1:.2f}, change={current_change:.2f}")
            else:
                logger.warning(f"未知的组合逻辑: {combination}")
            
            # 判断是否执行记录
            do_record = False
            
            # 统一使用final_trigger的状态变化来判断是否需要记录（上升沿触发）
            # 只有当final_trigger从不满足变为满足时，才记录一次
            if final_trigger and not self.final_trigger_last_state:
                # 上升沿触发：从不满足变为满足
                do_record = True
                
                # 如果使用了条件二，需要更新条件二相关的记录信息
                uses_condition_2 = combination in ["Cond2_Only", "AND"]
                if uses_condition_2 and self.config.trigger_logic.condition2 and self.config.trigger_logic.condition2.get('enabled', False):
                    self.cond2_last_recorded_value = current_change
                    self.cond2_last_recorded_time = current_time
                    if len(snapshots) < 10:
                        logger.info(f"[记录触发] 上升沿触发: time={current_time:.3f}s, "
                                  f"final_trigger_last_state={self.final_trigger_last_state}, "
                                  f"cond2_change={current_change:.2f}")
                else:
                    # 仅使用条件一时，更新条件一的状态
                    self.cond1_first_trigger = False
                    if len(snapshots) < 10:
                        logger.info(f"[记录触发] 上升沿触发: time={current_time:.3f}s, "
                                  f"final_trigger_last_state={self.final_trigger_last_state}")
            elif final_trigger and self.final_trigger_last_state:
                # 条件一直满足，通常不记录（避免重复记录）
                # 但如果使用了条件二，且超过10分钟，则记录一次（文档要求的特殊规则）
                uses_condition_2 = combination in ["Cond2_Only", "AND"]
                if uses_condition_2 and self.config.trigger_logic.condition2 and self.config.trigger_logic.condition2.get('enabled', False):
                    is_time_up = (current_time - self.cond2_last_recorded_time) > (10 * 60)
                    if is_time_up:
                        # 超过10分钟，即使一直满足，也记录一次
                        do_record = True
                        self.cond2_last_recorded_value = current_change
                        self.cond2_last_recorded_time = current_time
                        if len(snapshots) < 10:
                            logger.info(f"[记录触发] 10分钟超时: time={current_time:.3f}s, "
                                      f"change={current_change:.2f}")
            
            # 执行记录
            if do_record:
                snapshot = {
                    'timestamp': current_time,
                    'data': {channel: data_point.get(channel, 0.0) for channel in self.config.display_channels}
                }
                snapshots.append(snapshot)
                record_count += 1
                if record_count <= 10:
                    logger.info(f"记录快照 @ {current_time}s: {snapshot['data']}")
            
            # 更新状态
            self.cond1_last_state = cond1_met
            self.cond2_last_state = cond2_met
            self.final_trigger_last_state = final_trigger  # 保存final_trigger的状态，用于下次上升沿检测
            
            # 调试：统计信息
            if cond1_met:
                cond1_met_count += 1
            
            debug_count += 1
            # 在AND模式下，记录两个条件的状态（限制输出频率）
            if combination == "AND":
                # 只在以下情况输出：前20个点，或记录时，或前5秒内且满足条件
                should_log = (debug_count <= 20 or do_record or 
                            (current_time < 5.0 and (cond1_met or cond2_met or final_trigger)))
                if should_log:
                    logger.info(f"[AND模式调试] idx={debug_count}, time={current_time:.3f}s, "
                               f"cond1_met={cond1_met}, stat1={current_stat1:.2f}, "
                               f"cond2_met={cond2_met}, change={current_change:.2f}, "
                               f"final_trigger={final_trigger}, do_record={do_record}")
            elif debug_count <= 20 or do_record or (current_time < 5.0 and cond1_met):
                # 打印前20个点，或者记录时，或前5秒内且条件满足时
                logger.info(f"[调试] idx={debug_count}, time={current_time:.3f}s, cond1_met={cond1_met}, "
                           f"stat1={current_stat1:.2f}, last_state={self.cond1_last_state}, "
                           f"first_trigger={self.cond1_first_trigger}, do_record={do_record}")
        
        logger.info(f"计算完成: 总点数={debug_count}, 条件1满足={cond1_met_count}, 记录快照={len(snapshots)}")
        return snapshots

