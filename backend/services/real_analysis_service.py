"""
Real implementations of analysis service interfaces for Phase 2
Implements actual data analysis algorithms according to task specifications
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
import logging

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from interfaces.analysis_interfaces import (
    ReportCalculationEngine, StableStateAnalyzer, 
    FunctionalAnalyzer, StatusEvaluator
)
from models.data_models import (
    ChannelData, AnalysisResult, ReportData,
    StableStateResult, FunctionalCalcResult, StatusEvalResult
)
from models.report_config import ReportConfig

logger = logging.getLogger(__name__)


class RealStableStateAnalyzer(StableStateAnalyzer):
    """
    Real implementation of stable state analyzer
    Implements algorithms according to task specifications
    """
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Analyze stable state periods based on configuration"""
        try:
            stable_periods = self.find_stable_periods(data, config)
            
            # Calculate channel statistics for stable periods
            channel_statistics = self._calculate_channel_statistics(data, stable_periods, config)
            
            # Calculate total stable time
            total_stable_time = sum(period['duration'] for period in stable_periods)
            
            result_data = {
                "stable_periods": stable_periods,
                "channel_statistics": channel_statistics,
                "total_stable_time": total_stable_time
            }
            
            return AnalysisResult(
                analysis_type="stable_state",
                result_data=result_data,
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error in stable state analysis: {e}")
            raise
    
    def find_stable_periods(self, data: List[ChannelData], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find stable periods based on multiple conditions
        Implements AND/OR logic for multiple conditions
        """
        try:
            conditions = config.get('conditions', [])
            condition_logic = config.get('conditionLogic', 'AND')
            
            if not conditions:
                logger.warning("No conditions specified for stable state analysis")
                return []
            
            # Get data for analysis
            data_dict = {channel.channel_name: channel for channel in data}
            
            # Evaluate each condition
            condition_results = []
            for condition in conditions:
                result = self._evaluate_condition(data_dict, condition)
                condition_results.append(result)
            
            # Combine conditions using specified logic
            if condition_logic.upper() == 'AND':
                combined_mask = np.all(condition_results, axis=0)
            else:  # OR
                combined_mask = np.any(condition_results, axis=0)
            
            # Find continuous stable periods
            stable_periods = self._find_continuous_periods(combined_mask, data[0])
            
            logger.info(f"Found {len(stable_periods)} stable periods with total time {sum(p['duration'] for p in stable_periods):.2f}s")
            
            return stable_periods
            
        except Exception as e:
            logger.error(f"Error finding stable periods: {e}")
            raise
    
    def _evaluate_condition(self, data_dict: Dict[str, ChannelData], condition: Dict[str, Any]) -> np.ndarray:
        """Evaluate a single stability condition"""
        condition_type = condition.get('type', 'statistic')
        channel_name = condition['channel']
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found in data")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        if condition_type == 'statistic':
            return self._evaluate_statistic_condition(values, timestamps, condition)
        elif condition_type == 'amplitude_change':
            return self._evaluate_amplitude_change_condition(values, timestamps, condition)
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")
    
    def _evaluate_statistic_condition(self, values: np.ndarray, timestamps: np.ndarray, condition: Dict[str, Any]) -> np.ndarray:
        """Evaluate statistical condition (mean, max, min, rms over duration)"""
        statistic = condition['statistic']
        duration = condition['duration']
        logic = condition['logic']
        threshold = condition['threshold']
        
        # Calculate sample rate
        sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
        window_size = int(duration * sample_rate)
        
        if window_size <= 0:
            window_size = 1
        
        # Calculate rolling statistic
        if statistic == '平均值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=True).mean().fillna(0)
        elif statistic == '最大值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=True).max().fillna(0)
        elif statistic == '最小值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=True).min().fillna(0)
        elif statistic == '有效值':  # RMS
            rolling_values = pd.Series(values).rolling(window=window_size, center=True).apply(
                lambda x: np.sqrt(np.mean(x**2)), raw=True
            ).fillna(0)
        else:
            raise ValueError(f"Unknown statistic: {statistic}")
        
        # Apply threshold logic
        if logic == '>':
            return rolling_values.values > threshold
        elif logic == '<':
            return rolling_values.values < threshold
        elif logic == '>=':
            return rolling_values.values >= threshold
        elif logic == '<=':
            return rolling_values.values <= threshold
        else:
            raise ValueError(f"Unknown logic operator: {logic}")
    
    def _evaluate_amplitude_change_condition(self, values: np.ndarray, timestamps: np.ndarray, condition: Dict[str, Any]) -> np.ndarray:
        """Evaluate amplitude change condition (variation within duration)"""
        duration = condition['duration']
        logic = condition['logic']
        threshold = condition['threshold']
        
        # Calculate sample rate
        sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
        window_size = int(duration * sample_rate)
        
        if window_size <= 0:
            window_size = 1
        
        # Calculate rolling amplitude (max - min in window)
        rolling_max = pd.Series(values).rolling(window=window_size, center=True).max().fillna(0)
        rolling_min = pd.Series(values).rolling(window=window_size, center=True).min().fillna(0)
        rolling_amplitude = rolling_max - rolling_min
        
        # Apply threshold logic
        if logic == '<':
            return rolling_amplitude.values < threshold
        elif logic == '>':
            return rolling_amplitude.values > threshold
        elif logic == '<=':
            return rolling_amplitude.values <= threshold
        elif logic == '>=':
            return rolling_amplitude.values >= threshold
        else:
            raise ValueError(f"Unknown logic operator: {logic}")
    
    def _find_continuous_periods(self, mask: np.ndarray, reference_channel: ChannelData) -> List[Dict[str, Any]]:
        """Find continuous periods where mask is True"""
        timestamps = np.array([point.timestamp for point in reference_channel.data_points])
        
        # Find start and end indices of continuous True periods
        diff = np.diff(np.concatenate(([False], mask, [False])).astype(int))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        
        periods = []
        for start_idx, end_idx in zip(starts, ends):
            if end_idx > start_idx:  # Valid period
                start_time = timestamps[start_idx]
                end_time = timestamps[end_idx - 1]
                duration = end_time - start_time
                
                periods.append({
                    'start_time': float(start_time),
                    'end_time': float(end_time),
                    'duration': float(duration),
                    'start_index': int(start_idx),
                    'end_index': int(end_idx - 1)
                })
        
        return periods
    
    def _calculate_channel_statistics(self, data: List[ChannelData], stable_periods: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Calculate statistics for each channel during stable periods"""
        display_channels = config.get('displayChannels', [])
        statistics = {}
        
        for channel in data:
            if channel.channel_name not in display_channels:
                continue
                
            values = np.array([point.value for point in channel.data_points])
            
            # Calculate statistics for stable periods only
            stable_values = []
            for period in stable_periods:
                start_idx = period['start_index']
                end_idx = period['end_index']
                stable_values.extend(values[start_idx:end_idx+1])
            
            if stable_values:
                stable_values = np.array(stable_values)
                statistics[channel.channel_name] = {
                    'mean': float(np.mean(stable_values)),
                    'max': float(np.max(stable_values)),
                    'min': float(np.min(stable_values)),
                    'std': float(np.std(stable_values)),
                    'count': len(stable_values)
                }
            else:
                statistics[channel.channel_name] = {
                    'mean': 0.0, 'max': 0.0, 'min': 0.0, 'std': 0.0, 'count': 0
                }
        
        return statistics
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate stable state configuration"""
        required_fields = ['conditions']
        if not all(field in config for field in required_fields):
            return False
        
        conditions = config['conditions']
        if not isinstance(conditions, list) or len(conditions) == 0:
            return False
        
        for condition in conditions:
            required_condition_fields = ['channel', 'type']
            if not all(field in condition for field in required_condition_fields):
                return False
        
        return True
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for stable state analysis"""
        channels = set()
        
        if config is None:
            return []
        
        # Add channels from conditions (if exists)
        conditions = config.get('conditions', [])
        if conditions:
            for condition in conditions:
                if 'channel' in condition:
                    channels.add(condition['channel'])
        
        # Add channel from single condition (backward compatibility)
        condition = config.get('condition')
        if condition and isinstance(condition, dict) and 'channel' in condition:
            channels.add(condition['channel'])
        
        # Add display channels
        channels.update(config.get('displayChannels', []))
        channels.update(config.get('display_channels', []))
        
        return list(channels)


class RealFunctionalAnalyzer(FunctionalAnalyzer):
    """
    Real implementation of functional analyzer
    Implements timing calculations according to task specifications
    """
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Analyze functional timing metrics"""
        try:
            timing_metrics = self.calculate_timing_metrics(data, config)
            
            return AnalysisResult(
                analysis_type="functional_calc",
                result_data=timing_metrics,
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error in functional analysis: {e}")
            raise
    
    def calculate_timing_metrics(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, float]:
        """Calculate all timing metrics based on configuration"""
        data_dict = {channel.channel_name: channel for channel in data}
        results = {}
        
        # Calculate each configured metric
        for metric_name, metric_config in config.items():
            try:
                if metric_name == 'time_base':
                    results[metric_name] = self._calculate_time_base(data_dict, metric_config)
                elif metric_name == 'startup_time':
                    results[metric_name] = self._calculate_startup_time(data_dict, metric_config)
                elif metric_name == 'ignition_time':
                    results[metric_name] = self._calculate_ignition_time(data_dict, metric_config)
                elif metric_name in ['rundown_ng', 'rundown_np']:
                    results[metric_name] = self._calculate_rundown_time(data_dict, metric_config)
                else:
                    logger.warning(f"Unknown metric: {metric_name}")
            except Exception as e:
                logger.error(f"Error calculating {metric_name}: {e}")
                results[metric_name] = None
        
        logger.info(f"Calculated functional metrics: {results}")
        return results
    
    def _calculate_time_base(self, data_dict: Dict[str, ChannelData], config: Dict[str, Any]) -> Optional[float]:
        """Calculate time base - first time when condition is met"""
        channel_name = config['channel']
        statistic = config['statistic']
        duration = config['duration']
        logic = config['logic']
        threshold = config['threshold']
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        # Calculate rolling statistic
        sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
        window_size = int(duration * sample_rate)
        
        if statistic == '平均值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=False).mean()
        elif statistic == '最大值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=False).max()
        elif statistic == '最小值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=False).min()
        else:
            raise ValueError(f"Unknown statistic: {statistic}")
        
        # Find first time condition is met
        if logic == '>':
            mask = rolling_values > threshold
        elif logic == '<':
            mask = rolling_values < threshold
        else:
            raise ValueError(f"Unknown logic: {logic}")
        
        first_true_idx = mask.idxmax() if mask.any() else None
        
        if first_true_idx is not None and mask.iloc[first_true_idx]:
            return float(timestamps[first_true_idx])
        else:
            return None
    
    def _calculate_startup_time(self, data_dict: Dict[str, ChannelData], config: Dict[str, Any]) -> Optional[float]:
        """Calculate startup time - similar to time base but different threshold"""
        return self._calculate_time_base(data_dict, config)
    
    def _calculate_ignition_time(self, data_dict: Dict[str, ChannelData], config: Dict[str, Any]) -> Optional[float]:
        """Calculate ignition time based on temperature difference/change"""
        channel_name = config['channel']
        duration = config['duration']
        logic = config['logic']
        threshold = config['threshold']
        calc_type = config.get('type', 'difference')
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
        window_size = int(duration * sample_rate)
        
        if calc_type == 'difference':
            # Calculate rolling difference (max - min in window)
            rolling_max = pd.Series(values).rolling(window=window_size, center=False).max()
            rolling_min = pd.Series(values).rolling(window=window_size, center=False).min()
            rolling_diff = rolling_max - rolling_min
            
            if logic == '>':
                mask = rolling_diff > threshold
            elif logic == '<':
                mask = rolling_diff < threshold
            else:
                raise ValueError(f"Unknown logic: {logic}")
            
            first_true_idx = mask.idxmax() if mask.any() else None
            
            if first_true_idx is not None and mask.iloc[first_true_idx]:
                return float(timestamps[first_true_idx])
        
        return None
    
    def _calculate_rundown_time(self, data_dict: Dict[str, ChannelData], config: Dict[str, Any]) -> Optional[float]:
        """Calculate rundown time - time between two threshold crossings"""
        channel_name = config['channel']
        statistic = config.get('statistic', '平均值')
        duration = config.get('duration', 1.0)
        threshold1 = config['threshold1']  # Higher threshold
        threshold2 = config['threshold2']  # Lower threshold
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        # Calculate rolling statistic
        sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
        window_size = int(duration * sample_rate)
        
        if statistic == '平均值':
            rolling_values = pd.Series(values).rolling(window=window_size, center=False).mean()
        else:
            rolling_values = pd.Series(values)
        
        # Find crossing points
        # First find when value drops below threshold1
        below_threshold1 = rolling_values < threshold1
        first_below_threshold1 = below_threshold1.idxmax() if below_threshold1.any() else None
        
        if first_below_threshold1 is None or not below_threshold1.iloc[first_below_threshold1]:
            return None
        
        # Then find when value drops below threshold2 after threshold1 crossing
        after_threshold1 = rolling_values.iloc[first_below_threshold1:]
        below_threshold2 = after_threshold1 < threshold2
        first_below_threshold2 = below_threshold2.idxmax() if below_threshold2.any() else None
        
        if first_below_threshold2 is None or not below_threshold2.iloc[first_below_threshold2]:
            return None
        
        # Calculate time difference
        time1 = timestamps[first_below_threshold1]
        time2 = timestamps[first_below_threshold2 + first_below_threshold1]
        
        return float(time2 - time1)
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate functional calculation configuration"""
        if not config:
            return False
        
        # Check that at least one metric is configured
        valid_metrics = ['time_base', 'startup_time', 'ignition_time', 'rundown_ng', 'rundown_np']
        has_valid_metric = any(metric in config for metric in valid_metrics)
        
        return has_valid_metric
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for functional analysis"""
        channels = set()
        
        for metric_config in config.values():
            if isinstance(metric_config, dict) and 'channel' in metric_config:
                channels.add(metric_config['channel'])
        
        return list(channels)


class RealStatusEvaluator(StatusEvaluator):
    """
    Real implementation of status evaluator
    Implements status evaluation according to task specifications
    """
    
    def __init__(self):
        """Initialize evaluator with storage for functional results"""
        self.functional_results = {}
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Analyze status evaluation"""
        try:
            evaluation_result = self.evaluate_status(data, config)
            
            return AnalysisResult(
                analysis_type="status_eval",
                result_data=evaluation_result,
                calculation_time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error in status evaluation: {e}")
            raise
    
    def set_functional_results(self, functional_results: Dict[str, Any]) -> None:
        """Set functional calculation results for evaluation"""
        self.functional_results = functional_results or {}
    
    def evaluate_status(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all status items based on configuration"""
        data_dict = {channel.channel_name: channel for channel in data}
        evaluations = []
        warnings = []
        
        for eval_config in config.get('evaluations', []):
            try:
                result = self._evaluate_single_item(data_dict, eval_config)
                evaluations.append(result)
                
                if result['result'] != '正常':
                    warnings.append(f"{result['item']}: {result['result']}")
                    
            except Exception as e:
                logger.error(f"Error evaluating {eval_config.get('item', 'unknown')}: {e}")
                evaluations.append({
                    'item': eval_config.get('item', 'unknown'),
                    'result': '评估失败',
                    'status': '✗',
                    'error': str(e)
                })
        
        # Determine overall status
        overall_status = "正常" if not warnings else "存在异常"
        
        logger.info(f"Status evaluation completed. Overall: {overall_status}, Warnings: {len(warnings)}")
        
        return {
            "evaluations": evaluations,
            "overall_status": overall_status,
            "warnings": warnings
        }
    
    def _evaluate_single_item(self, data_dict: Dict[str, ChannelData], eval_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single status item"""
        item_name = eval_config['item']
        eval_type = eval_config.get('type', 'continuous_check')
        
        if eval_type == 'functional_result':
            return self._evaluate_functional_result(eval_config)
        elif eval_type == 'continuous_check':
            return self._evaluate_continuous_check(data_dict, eval_config)
        elif eval_type == 'event_check':
            return self._evaluate_event_check(data_dict, eval_config)
        else:
            raise ValueError(f"Unknown evaluation type: {eval_type}")
    
    def _evaluate_functional_result(self, eval_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate based on functional calculation results"""
        item_name = eval_config['item']
        source = eval_config['source']  # e.g., "time_base", "startup_time", "ignition_time"
        logic = eval_config['logic']  # e.g., ">", "<", ">=", "<=", "==", "!="
        threshold = eval_config['threshold']
        
        # Get the functional result value
        if source not in self.functional_results:
            return {
                'item': item_name,
                'result': '无数据',
                'status': '?',
                'details': f"未找到功能计算结果 {source}"
            }
        
        result_value = self.functional_results[source]
        
        # If result is None, evaluation failed
        if result_value is None:
            return {
                'item': item_name,
                'result': '无法计算',
                'status': '?',
                'details': f"{source} 计算失败"
            }
        
        # Perform comparison
        try:
            if logic == '>':
                passes = result_value > threshold
            elif logic == '<':
                passes = result_value < threshold
            elif logic == '>=':
                passes = result_value >= threshold
            elif logic == '<=':
                passes = result_value <= threshold
            elif logic == '==':
                passes = abs(result_value - threshold) < 1e-6
            elif logic == '!=':
                passes = abs(result_value - threshold) >= 1e-6
            else:
                raise ValueError(f"Unknown logic operator: {logic}")
            
            result = '正常' if passes else '异常'
            status = '✓' if passes else '✗'
            details = f"{source}={result_value:.2f}, 阈值{logic}{threshold}, 结果: {result}"
            
            return {
                'item': item_name,
                'result': result,
                'status': status,
                'details': details
            }
            
        except Exception as e:
            logger.error(f"Error evaluating functional result {source}: {e}")
            return {
                'item': item_name,
                'result': '评估失败',
                'status': '✗',
                'details': f"评估出错: {str(e)}"
            }
    
    def _evaluate_continuous_check(self, data_dict: Dict[str, ChannelData], eval_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate continuous conditions throughout the data"""
        item_name = eval_config['item']
        conditions = eval_config.get('conditions', [])
        condition_logic = eval_config.get('conditionLogic', 'AND')
        
        if not conditions:
            raise ValueError("No conditions specified for continuous check")
        
        # Evaluate each condition
        condition_results = []
        for condition in conditions:
            result = self._evaluate_condition_for_status(data_dict, condition)
            condition_results.append(result)
        
        # Combine conditions
        if condition_logic.upper() == 'AND':
            overall_pass = all(condition_results)
        else:  # OR
            overall_pass = any(condition_results)
        
        return {
            'item': item_name,
            'result': '正常' if overall_pass else '异常',
            'status': '✓' if overall_pass else '✗',
            'details': f"连续检查结果: {'通过' if overall_pass else '未通过'}"
        }
    
    def _evaluate_event_check(self, data_dict: Dict[str, ChannelData], eval_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate event-based conditions"""
        item_name = eval_config['item']
        condition = eval_config['condition']
        expected = eval_config.get('expected', 'never_happen')
        
        # Evaluate the condition
        event_occurred = self._check_event_condition(data_dict, condition)
        
        # Determine pass/fail based on expectation
        if expected == 'never_happen':
            result_ok = not event_occurred
        elif expected == 'should_happen':
            result_ok = event_occurred
        else:
            result_ok = True
        
        return {
            'item': item_name,
            'result': '正常' if result_ok else '异常',
            'status': '✓' if result_ok else '✗',
            'details': f"事件检查: {'未发生' if not event_occurred else '已发生'}"
        }
    
    def _evaluate_condition_for_status(self, data_dict: Dict[str, ChannelData], condition: Dict[str, Any]) -> bool:
        """Evaluate a condition for status evaluation"""
        channel_name = condition['channel']
        statistic = condition.get('statistic', '瞬时值')
        logic = condition['logic']
        threshold = condition['threshold']
        duration = condition.get('duration', 1.0)
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        # Calculate values to check
        if statistic == '瞬时值':
            check_values = values
        elif statistic == '平均值':
            sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
            window_size = int(duration * sample_rate)
            check_values = pd.Series(values).rolling(window=window_size, center=False).mean().fillna(0).values
        elif statistic == '最大值':
            sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
            window_size = int(duration * sample_rate)
            check_values = pd.Series(values).rolling(window=window_size, center=False).max().fillna(0).values
        elif statistic == '最小值':
            sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
            window_size = int(duration * sample_rate)
            check_values = pd.Series(values).rolling(window=window_size, center=False).min().fillna(0).values
        else:
            raise ValueError(f"Unknown statistic: {statistic}")
        
        # Apply logic
        if logic == '<':
            condition_met = np.all(check_values < threshold)
        elif logic == '>':
            condition_met = np.all(check_values > threshold)
        elif logic == '<=':
            condition_met = np.all(check_values <= threshold)
        elif logic == '>=':
            condition_met = np.all(check_values >= threshold)
        else:
            raise ValueError(f"Unknown logic: {logic}")
        
        return condition_met
    
    def _check_event_condition(self, data_dict: Dict[str, ChannelData], condition: Dict[str, Any]) -> bool:
        """Check if an event condition occurs"""
        channel_name = condition['channel']
        calc_type = condition.get('type', 'difference')
        duration = condition['duration']
        logic = condition['logic']
        threshold = condition['threshold']
        
        if channel_name not in data_dict:
            raise ValueError(f"Channel {channel_name} not found")
        
        channel_data = data_dict[channel_name]
        values = np.array([point.value for point in channel_data.data_points])
        timestamps = np.array([point.timestamp for point in channel_data.data_points])
        
        if calc_type == 'difference':
            # Calculate rolling difference
            sample_rate = 1.0 / (timestamps[1] - timestamps[0]) if len(timestamps) > 1 else 1.0
            window_size = int(duration * sample_rate)
            
            rolling_max = pd.Series(values).rolling(window=window_size, center=False).max()
            rolling_min = pd.Series(values).rolling(window=window_size, center=False).min()
            rolling_diff = rolling_max - rolling_min
            
            if logic == '>':
                event_mask = rolling_diff > threshold
            elif logic == '<':
                event_mask = rolling_diff < threshold
            else:
                raise ValueError(f"Unknown logic: {logic}")
            
            return event_mask.any()
        
        return False
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate status evaluation configuration"""
        evaluations = config.get('evaluations', [])
        if not evaluations:
            return False
        
        for evaluation in evaluations:
            if 'item' not in evaluation:
                return False
            
            eval_type = evaluation.get('type', 'continuous_check')
            if eval_type not in ['functional_result', 'continuous_check', 'event_check']:
                return False
        
        return True
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for status evaluation"""
        channels = set()
        
        for evaluation in config.get('evaluations', []):
            eval_type = evaluation.get('type', 'continuous_check')
            
            if eval_type == 'continuous_check':
                for condition in evaluation.get('conditions', []):
                    if 'channel' in condition:
                        channels.add(condition['channel'])
            elif eval_type == 'event_check':
                condition = evaluation.get('condition', {})
                if 'channel' in condition:
                    channels.add(condition['channel'])
        
        return list(channels)


class RealReportCalculationEngine(ReportCalculationEngine):
    """
    Real implementation of report calculation engine
    Coordinates all analysis components
    """
    
    def __init__(self):
        self.analyzers = {
            "stable_state": RealStableStateAnalyzer(),
            "functional_calc": RealFunctionalAnalyzer(),
            "status_eval": RealStatusEvaluator()
        }
        self.logger = logging.getLogger(__name__)
    
    def generate(self, data: List[ChannelData], full_config: ReportConfig) -> ReportData:
        """Generate complete report data"""
        try:
            # Validate data completeness
            if not self.validate_data_completeness(data, full_config):
                raise ValueError("Data is incomplete for the requested configuration")
            
            # Preprocess data
            processed_data = self.preprocess_data(data)
            
            # Initialize report data
            report_data = ReportData(
                report_id=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                source_file_id=full_config.source_file_id,
                generation_time=datetime.now()
            )
            
            sections = full_config.report_config.sections
            
            # Execute stable state analysis
            if "stableState" in sections and full_config.report_config.stable_state:
                self.logger.info("Starting stable state analysis...")
                stable_result = self.analyzers["stable_state"].analyze(
                    processed_data,
                    full_config.report_config.stable_state.model_dump()
                )
                
                report_data.stable_state_result = StableStateResult(
                    stable_periods=stable_result.result_data["stable_periods"],
                    channel_statistics=stable_result.result_data["channel_statistics"],
                    total_stable_time=stable_result.result_data["total_stable_time"]
                )
                self.logger.info("Stable state analysis completed")
            
            # Execute functional calculation analysis
            if "functionalCalc" in sections and full_config.report_config.functional_calc:
                self.logger.info("Starting functional calculation analysis...")
                func_result = self.analyzers["functional_calc"].analyze(
                    processed_data,
                    full_config.report_config.functional_calc.model_dump()
                )
                
                report_data.functional_calc_result = FunctionalCalcResult(
                    time_base=func_result.result_data.get("time_base"),
                    startup_time=func_result.result_data.get("startup_time"),
                    ignition_time=func_result.result_data.get("ignition_time"),
                    rundown_ng=func_result.result_data.get("rundown_ng")
                )
                self.logger.info("Functional calculation analysis completed")
            
            # Execute status evaluation
            if "statusEval" in sections and full_config.report_config.status_eval:
                self.logger.info("Starting status evaluation...")
                
                # Pass functional results to status evaluator if available
                if report_data.functional_calc_result:
                    functional_results = {
                        "time_base": report_data.functional_calc_result.time_base,
                        "startup_time": report_data.functional_calc_result.startup_time,
                        "ignition_time": report_data.functional_calc_result.ignition_time,
                        "rundown_ng": report_data.functional_calc_result.rundown_ng
                    }
                    self.analyzers["status_eval"].set_functional_results(functional_results)
                
                eval_result = self.analyzers["status_eval"].analyze(
                    processed_data,
                    full_config.report_config.status_eval.model_dump()
                )
                
                report_data.status_eval_result = StatusEvalResult(
                    evaluations=eval_result.result_data["evaluations"],
                    overall_status=eval_result.result_data["overall_status"],
                    warnings=eval_result.result_data["warnings"]
                )
                self.logger.info("Status evaluation completed")
            
            self.logger.info(f"Report generation completed: {report_data.report_id}")
            return report_data
            
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            raise
    
    def register_analyzer(self, analyzer_type: str, analyzer) -> None:
        """Register an analyzer"""
        self.analyzers[analyzer_type] = analyzer
    
    def validate_data_completeness(self, data: List[ChannelData], config: ReportConfig) -> bool:
        """Validate that all required data is available"""
        available_channels = {channel.channel_name for channel in data}
        
        # Check stable state requirements
        if "stableState" in config.report_config.sections and config.report_config.stable_state:
            stable_analyzer = self.analyzers["stable_state"]
            required_channels = stable_analyzer.get_required_channels(config.report_config.stable_state.model_dump())
            if not all(channel in available_channels for channel in required_channels):
                missing = set(required_channels) - available_channels
                self.logger.error(f"Missing channels for stable state analysis: {missing}")
                return False
        
        # Check functional calc requirements
        if "functionalCalc" in config.report_config.sections and config.report_config.functional_calc:
            func_analyzer = self.analyzers["functional_calc"]
            required_channels = func_analyzer.get_required_channels(config.report_config.functional_calc.model_dump())
            if not all(channel in available_channels for channel in required_channels):
                missing = set(required_channels) - available_channels
                self.logger.error(f"Missing channels for functional analysis: {missing}")
                return False
        
        # Check status eval requirements
        if "statusEval" in config.report_config.sections and config.report_config.status_eval:
            status_analyzer = self.analyzers["status_eval"]
            required_channels = status_analyzer.get_required_channels(config.report_config.status_eval.model_dump())
            if not all(channel in available_channels for channel in required_channels):
                missing = set(required_channels) - available_channels
                self.logger.error(f"Missing channels for status evaluation: {missing}")
                return False
        
        # Check data quality
        for channel in data:
            if len(channel.data_points) < 10:  # Minimum data points
                self.logger.error(f"Insufficient data points in channel {channel.channel_name}")
                return False
        
        return True
    
    def preprocess_data(self, data: List[ChannelData]) -> List[ChannelData]:
        """Preprocess data - clean, filter, validate"""
        processed_data = []
        
        for channel in data:
            # Create a copy
            processed_channel = ChannelData(
                channel_name=channel.channel_name,
                unit=channel.unit,
                data_points=[],
                sample_rate=channel.sample_rate
            )
            
            # Clean data points - remove NaN, outliers, etc.
            cleaned_points = []
            values = [point.value for point in channel.data_points]
            
            if values:
                # Calculate outlier bounds (simple method)
                q25, q75 = np.percentile(values, [25, 75])
                iqr = q75 - q25
                lower_bound = q25 - 1.5 * iqr
                upper_bound = q75 + 1.5 * iqr
                
                for point in channel.data_points:
                    # Skip NaN values
                    if np.isnan(point.value) or np.isinf(point.value):
                        continue
                    
                    # Skip extreme outliers (optional)
                    if point.value < lower_bound or point.value > upper_bound:
                        # For now, keep outliers but could filter them
                        pass
                    
                    cleaned_points.append(point)
            
            processed_channel.data_points = cleaned_points
            processed_data.append(processed_channel)
            
            self.logger.info(f"Preprocessed channel {channel.channel_name}: {len(channel.data_points)} -> {len(cleaned_points)} points")
        
        return processed_data
