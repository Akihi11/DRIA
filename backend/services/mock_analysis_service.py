"""
Mock implementations of analysis service interfaces for Phase 1 testing
"""
from typing import List, Dict, Any
from datetime import datetime
import random

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from interfaces.analysis_interfaces import (
    ReportCalculationEngine, Analyzer, StableStateAnalyzer, 
    FunctionalAnalyzer, StatusEvaluator
)
from models.data_models import ChannelData, AnalysisResult, ReportData
from models.report_config import ReportConfig


class MockStableStateAnalyzer(StableStateAnalyzer):
    """Mock implementation of stable state analyzer"""
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Mock stable state analysis"""
        
        stable_periods = self.find_stable_periods(data, config)
        
        # Mock channel statistics
        channel_statistics = {}
        for channel in data:
            channel_statistics[channel.channel_name] = {
                "mean": sum(channel.values) / len(channel.values),
                "max": max(channel.values),
                "min": min(channel.values),
                "std": random.uniform(10, 100)  # Mock standard deviation
            }
        
        result_data = {
            "stable_periods": stable_periods,
            "channel_statistics": channel_statistics,
            "total_stable_time": sum(period["duration"] for period in stable_periods)
        }
        
        return AnalysisResult(
            analysis_type="stable_state",
            result_data=result_data,
            calculation_time=datetime.now()
        )
    
    def find_stable_periods(self, data: List[ChannelData], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Mock stable period detection"""
        
        # Generate mock stable periods
        stable_periods = []
        
        for i in range(3):  # Mock 3 stable periods
            start_time = i * 100 + random.uniform(0, 20)
            duration = random.uniform(30, 60)
            
            period = {
                "start_time": start_time,
                "end_time": start_time + duration,
                "duration": duration,
                "channel_values": {}
            }
            
            # Mock channel values during stable period
            for channel in data:
                period["channel_values"][channel.channel_name] = {
                    "mean": random.uniform(14000, 16000) if "Ng" in channel.channel_name else random.uniform(600, 700),
                    "stability_score": random.uniform(0.8, 0.95)
                }
            
            stable_periods.append(period)
        
        return stable_periods
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate stable state configuration"""
        
        required_fields = ["channel", "statistic", "duration", "logic", "threshold"]
        return all(field in config for field in required_fields)
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for stable state analysis"""
        
        channels = [config.get("channel", "")]
        display_channels = config.get("displayChannels", [])
        
        return list(set(channels + display_channels))


class MockFunctionalAnalyzer(FunctionalAnalyzer):
    """Mock implementation of functional analyzer"""
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Mock functional calculation analysis"""
        
        timing_metrics = self.calculate_timing_metrics(data, config)
        
        return AnalysisResult(
            analysis_type="functional_calc",
            result_data=timing_metrics,
            calculation_time=datetime.now()
        )
    
    def calculate_timing_metrics(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, float]:
        """Mock timing metrics calculation"""
        
        metrics = {}
        
        # Mock calculation results
        if "time_base" in config:
            metrics["time_base"] = random.uniform(40, 50)
        
        if "startup_time" in config:
            metrics["startup_time"] = random.uniform(10, 15)
        
        if "ignition_time" in config:
            metrics["ignition_time"] = random.uniform(2, 5)
        
        if "rundown_ng" in config:
            metrics["rundown_ng"] = random.uniform(25, 35)
        
        return metrics
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate functional calculation configuration"""
        
        valid_metrics = ["time_base", "startup_time", "ignition_time", "rundown_ng"]
        return any(metric in config for metric in valid_metrics)
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for functional analysis"""
        
        channels = []
        
        for metric_config in config.values():
            if isinstance(metric_config, dict) and "channel" in metric_config:
                channels.append(metric_config["channel"])
        
        return list(set(channels))


class MockStatusEvaluator(StatusEvaluator):
    """Mock implementation of status evaluator"""
    
    def analyze(self, data: List[ChannelData], config: Dict[str, Any]) -> AnalysisResult:
        """Mock status evaluation analysis"""
        
        evaluation_result = self.evaluate_status(data, config)
        
        return AnalysisResult(
            analysis_type="status_eval",
            result_data=evaluation_result,
            calculation_time=datetime.now()
        )
    
    def evaluate_status(self, data: List[ChannelData], config: Dict[str, Any]) -> Dict[str, Any]:
        """Mock status evaluation"""
        
        evaluations = []
        warnings = []
        
        for evaluation_config in config.get("evaluations", []):
            item = evaluation_config["item"]
            
            # Mock evaluation result
            is_normal = random.choice([True, True, True, False])  # 75% chance of normal
            
            evaluation_result = {
                "item": item,
                "result": "正常" if is_normal else "异常",
                "status": "✓" if is_normal else "✗",
                "measured_value": random.uniform(100, 800),
                "threshold": evaluation_config.get("threshold", 0),
                "details": f"Mock evaluation for {item}"
            }
            
            evaluations.append(evaluation_result)
            
            if not is_normal:
                warnings.append(f"{item}状态异常")
        
        overall_status = "正常" if not warnings else "存在异常"
        
        return {
            "evaluations": evaluations,
            "overall_status": overall_status,
            "warnings": warnings
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate status evaluation configuration"""
        
        evaluations = config.get("evaluations", [])
        if not evaluations:
            return False
        
        for evaluation in evaluations:
            required_fields = ["item", "logic", "threshold"]
            if not all(field in evaluation for field in required_fields):
                return False
        
        return True
    
    def get_required_channels(self, config: Dict[str, Any]) -> List[str]:
        """Get required channels for status evaluation"""
        
        channels = []
        
        for evaluation in config.get("evaluations", []):
            if "channel" in evaluation:
                channels.append(evaluation["channel"])
        
        return list(set(channels))


class MockReportCalculationEngine(ReportCalculationEngine):
    """Mock implementation of report calculation engine"""
    
    def __init__(self):
        self.analyzers = {
            "stable_state": MockStableStateAnalyzer(),
            "functional_calc": MockFunctionalAnalyzer(),
            "status_eval": MockStatusEvaluator()
        }
    
    def generate(self, data: List[ChannelData], full_config: ReportConfig) -> ReportData:
        """Mock report generation"""
        
        # Validate data completeness
        if not self.validate_data_completeness(data, full_config):
            raise ValueError("Data is incomplete for the requested configuration")
        
        # Preprocess data
        processed_data = self.preprocess_data(data)
        
        # Initialize report data
        report_data = ReportData(
            report_id=f"mock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            source_file_id=full_config.source_file_id,
            generation_time=datetime.now()
        )
        
        # Execute analysis for each requested section
        sections = full_config.report_config.sections
        
        if "stableState" in sections and full_config.report_config.stable_state:
            stable_result = self.analyzers["stable_state"].analyze(
                processed_data,
                full_config.report_config.stable_state.dict()
            )
            
            from ..models.data_models import StableStateResult
            report_data.stable_state_result = StableStateResult(
                stable_periods=stable_result.result_data["stable_periods"],
                channel_statistics=stable_result.result_data["channel_statistics"],
                total_stable_time=stable_result.result_data["total_stable_time"]
            )
        
        if "functionalCalc" in sections and full_config.report_config.functional_calc:
            func_result = self.analyzers["functional_calc"].analyze(
                processed_data,
                full_config.report_config.functional_calc.dict()
            )
            
            from ..models.data_models import FunctionalCalcResult
            report_data.functional_calc_result = FunctionalCalcResult(
                time_base=func_result.result_data.get("time_base"),
                startup_time=func_result.result_data.get("startup_time"),
                ignition_time=func_result.result_data.get("ignition_time"),
                rundown_ng=func_result.result_data.get("rundown_ng")
            )
        
        if "statusEval" in sections and full_config.report_config.status_eval:
            eval_result = self.analyzers["status_eval"].analyze(
                processed_data,
                full_config.report_config.status_eval.dict()
            )
            
            from ..models.data_models import StatusEvalResult
            report_data.status_eval_result = StatusEvalResult(
                evaluations=eval_result.result_data["evaluations"],
                overall_status=eval_result.result_data["overall_status"],
                warnings=eval_result.result_data["warnings"]
            )
        
        return report_data
    
    def register_analyzer(self, analyzer_type: str, analyzer: Analyzer) -> None:
        """Register an analyzer"""
        
        self.analyzers[analyzer_type] = analyzer
    
    def validate_data_completeness(self, data: List[ChannelData], config: ReportConfig) -> bool:
        """Mock data completeness validation"""
        
        # Check if we have any data
        if not data:
            return False
        
        # Check if each channel has sufficient data points
        for channel in data:
            if len(channel.data_points) < 100:  # Mock minimum requirement
                return False
        
        # Mock validation - in reality would check specific requirements
        return True
    
    def preprocess_data(self, data: List[ChannelData]) -> List[ChannelData]:
        """Mock data preprocessing"""
        
        # Mock preprocessing - in reality would clean, filter, and normalize data
        processed_data = []
        
        for channel in data:
            # Create a copy of the channel data
            processed_channel = ChannelData(
                channel_name=channel.channel_name,
                unit=channel.unit,
                data_points=channel.data_points.copy(),
                sample_rate=channel.sample_rate
            )
            
            processed_data.append(processed_channel)
        
        return processed_data
