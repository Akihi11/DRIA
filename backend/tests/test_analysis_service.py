"""
Unit tests for analysis service implementations
"""
import pytest
import numpy as np
from datetime import datetime
from typing import List

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.real_analysis_service import (
    RealStableStateAnalyzer, RealFunctionalAnalyzer, 
    RealStatusEvaluator, RealReportCalculationEngine
)
from models.data_models import ChannelData, DataPoint
from models.report_config import (
    ReportConfig, ReportConfigData, StableStateConfig, FunctionalCalcConfig, 
    StatusEvalConfig, ConditionConfig, EvaluationConfig
)


class TestRealStableStateAnalyzer:
    """Test cases for RealStableStateAnalyzer"""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return RealStableStateAnalyzer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample channel data for testing"""
        # Create time series data with stable and unstable periods
        data = []
        
        # Channel 1: Ng(rpm) - has stable periods
        ng_data_points = []
        for i in range(1000):
            timestamp = i * 0.01  # 10ms intervals
            
            # Create stable periods: 2-4s and 6-8s
            if 200 <= i <= 400 or 600 <= i <= 800:
                # Stable period: 15000 ± 50
                value = 15000 + np.random.normal(0, 50)
            else:
                # Unstable period: varying values
                value = 10000 + 5000 * np.sin(i * 0.1) + np.random.normal(0, 200)
            
            ng_data_points.append(DataPoint(timestamp=timestamp, value=value))
        
        ng_channel = ChannelData(
            channel_name="Ng(rpm)",
            unit="rpm",
            data_points=ng_data_points,
            sample_rate=100.0
        )
        
        # Channel 2: Temperature
        temp_data_points = []
        for i in range(1000):
            timestamp = i * 0.01
            value = 650 + np.random.normal(0, 10)
            temp_data_points.append(DataPoint(timestamp=timestamp, value=value))
        
        temp_channel = ChannelData(
            channel_name="Temperature(°C)",
            unit="°C",
            data_points=temp_data_points,
            sample_rate=100.0
        )
        
        return [ng_channel, temp_channel]
    
    def test_analyze_stable_state(self, analyzer, sample_data):
        """Test stable state analysis"""
        config = {
            "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
            "conditionLogic": "AND",
            "conditions": [
                {
                    "type": "statistic",
                    "channel": "Ng(rpm)",
                    "statistic": "平均值",
                    "duration": 0.1,  # 100ms window
                    "logic": ">",
                    "threshold": 14000
                },
                {
                    "type": "amplitude_change",
                    "channel": "Ng(rpm)",
                    "duration": 0.5,  # 500ms window
                    "logic": "<",
                    "threshold": 200
                }
            ]
        }
        
        result = analyzer.analyze(sample_data, config)
        
        assert result.analysis_type == "stable_state"
        assert "stable_periods" in result.result_data
        assert "channel_statistics" in result.result_data
        assert "total_stable_time" in result.result_data
        
        stable_periods = result.result_data["stable_periods"]
        assert isinstance(stable_periods, list)
        
        # Should find some stable periods
        assert len(stable_periods) > 0
        
        for period in stable_periods:
            assert "start_time" in period
            assert "end_time" in period
            assert "duration" in period
            assert period["end_time"] > period["start_time"]
    
    def test_find_stable_periods(self, analyzer, sample_data):
        """Test finding stable periods"""
        config = {
            "conditionLogic": "AND",
            "conditions": [
                {
                    "type": "statistic",
                    "channel": "Ng(rpm)",
                    "statistic": "平均值",
                    "duration": 0.1,
                    "logic": ">",
                    "threshold": 14500
                }
            ]
        }
        
        periods = analyzer.find_stable_periods(sample_data, config)
        
        assert isinstance(periods, list)
        # Should find stable periods around 2-4s and 6-8s
        assert len(periods) >= 1
    
    def test_evaluate_statistic_condition(self, analyzer):
        """Test evaluating statistic conditions"""
        # Create simple test data
        values = np.array([10000, 15000, 15100, 14900, 15050, 10000])
        timestamps = np.array([0, 0.01, 0.02, 0.03, 0.04, 0.05])
        
        condition = {
            "statistic": "平均值",
            "duration": 0.02,  # 20ms window
            "logic": ">",
            "threshold": 14000
        }
        
        result = analyzer._evaluate_statistic_condition(values, timestamps, condition)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == len(values)
        assert result.dtype == bool
    
    def test_evaluate_amplitude_change_condition(self, analyzer):
        """Test evaluating amplitude change conditions"""
        # Create test data with varying amplitude
        values = np.array([15000, 15100, 14900, 15050, 15000, 16000])  # Last value has high amplitude
        timestamps = np.array([0, 0.01, 0.02, 0.03, 0.04, 0.05])
        
        condition = {
            "duration": 0.03,  # 30ms window
            "logic": "<",
            "threshold": 200
        }
        
        result = analyzer._evaluate_amplitude_change_condition(values, timestamps, condition)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == len(values)
        assert result.dtype == bool
    
    def test_validate_config(self, analyzer):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "conditions": [
                {
                    "channel": "Ng(rpm)",
                    "type": "statistic"
                }
            ]
        }
        
        assert analyzer.validate_config(valid_config) is True
        
        # Invalid config - no conditions
        invalid_config = {}
        assert analyzer.validate_config(invalid_config) is False
        
        # Invalid config - empty conditions
        invalid_config2 = {"conditions": []}
        assert analyzer.validate_config(invalid_config2) is False
    
    def test_get_required_channels(self, analyzer):
        """Test getting required channels"""
        config = {
            "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
            "conditions": [
                {"channel": "Ng(rpm)"},
                {"channel": "Pressure(kPa)"}
            ]
        }
        
        channels = analyzer.get_required_channels(config)
        
        expected_channels = {"Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"}
        assert set(channels) == expected_channels


class TestRealFunctionalAnalyzer:
    """Test cases for RealFunctionalAnalyzer"""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return RealFunctionalAnalyzer()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for functional analysis"""
        data = []
        
        # Pressure channel - for time_base and startup_time
        press_points = []
        for i in range(1000):
            timestamp = i * 0.01
            
            # Simulate pressure rise: low initially, then rises
            if timestamp < 2.0:
                value = 100 + np.random.normal(0, 10)  # Low pressure
            elif timestamp < 4.0:
                value = 600 + np.random.normal(0, 20)  # Medium pressure (>500)
            else:
                value = 1200 + np.random.normal(0, 30)  # High pressure (>1000)
            
            press_points.append(DataPoint(timestamp=timestamp, value=value))
        
        press_channel = ChannelData(
            channel_name="Pressure(kPa)",
            unit="kPa",
            data_points=press_points,
            sample_rate=100.0
        )
        
        # Temperature channel - for ignition_time
        temp_points = []
        for i in range(1000):
            timestamp = i * 0.01
            
            # Simulate temperature jump at t=3s
            if timestamp < 3.0:
                value = 200 + np.random.normal(0, 5)
            else:
                value = 300 + np.random.normal(0, 5)  # Jump of ~100°C
            
            temp_points.append(DataPoint(timestamp=timestamp, value=value))
        
        temp_channel = ChannelData(
            channel_name="Temperature(°C)",
            unit="°C",
            data_points=temp_points,
            sample_rate=100.0
        )
        
        # Ng channel - for rundown_ng
        ng_points = []
        for i in range(1000):
            timestamp = i * 0.01
            
            # Simulate rundown: high -> medium -> low
            if timestamp < 2.0:
                value = 15000 + np.random.normal(0, 100)  # High
            elif timestamp < 5.0:
                value = 6000 + np.random.normal(0, 100)   # Below threshold1 (8000)
            else:
                value = 500 + np.random.normal(0, 50)     # Below threshold2 (1000)
            
            ng_points.append(DataPoint(timestamp=timestamp, value=value))
        
        ng_channel = ChannelData(
            channel_name="Ng(rpm)",
            unit="rpm",
            data_points=ng_points,
            sample_rate=100.0
        )
        
        return [press_channel, temp_channel, ng_channel]
    
    def test_analyze_functional_calc(self, analyzer, sample_data):
        """Test functional calculation analysis"""
        config = {
            "time_base": {
                "channel": "Pressure(kPa)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 500
            },
            "startup_time": {
                "channel": "Pressure(kPa)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 1000
            },
            "ignition_time": {
                "channel": "Temperature(°C)",
                "type": "difference",
                "duration": 0.5,
                "logic": ">",
                "threshold": 50
            },
            "rundown_ng": {
                "channel": "Ng(rpm)",
                "statistic": "平均值",
                "duration": 0.1,
                "threshold1": 8000,
                "threshold2": 1000
            }
        }
        
        result = analyzer.analyze(sample_data, config)
        
        assert result.analysis_type == "functional_calc"
        
        metrics = result.result_data
        assert "time_base" in metrics
        assert "startup_time" in metrics
        assert "ignition_time" in metrics
        assert "rundown_ng" in metrics
        
        # Check that calculated values are reasonable
        if metrics["time_base"] is not None:
            assert 0 <= metrics["time_base"] <= 10
        
        if metrics["startup_time"] is not None:
            assert 0 <= metrics["startup_time"] <= 10
    
    def test_calculate_time_base(self, analyzer, sample_data):
        """Test time base calculation"""
        data_dict = {channel.channel_name: channel for channel in sample_data}
        
        config = {
            "channel": "Pressure(kPa)",
            "statistic": "平均值",
            "duration": 0.1,
            "logic": ">",
            "threshold": 500
        }
        
        time_base = analyzer._calculate_time_base(data_dict, config)
        
        # Should find time when pressure > 500 (around 2s based on our data)
        assert time_base is not None
        assert 1.5 <= time_base <= 3.0
    
    def test_calculate_rundown_time(self, analyzer, sample_data):
        """Test rundown time calculation"""
        data_dict = {channel.channel_name: channel for channel in sample_data}
        
        config = {
            "channel": "Ng(rpm)",
            "statistic": "平均值",
            "duration": 0.1,
            "threshold1": 8000,
            "threshold2": 1000
        }
        
        rundown_time = analyzer._calculate_rundown_time(data_dict, config)
        
        # Should find time between thresholds (around 3s based on our data)
        if rundown_time is not None:
            assert 0 <= rundown_time <= 6  # Allow slightly more tolerance
    
    def test_validate_config(self, analyzer):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "time_base": {"channel": "Pressure(kPa)"}
        }
        
        assert analyzer.validate_config(valid_config) is True
        
        # Invalid config - empty
        invalid_config = {}
        assert analyzer.validate_config(invalid_config) is False
    
    def test_get_required_channels(self, analyzer):
        """Test getting required channels"""
        config = {
            "time_base": {"channel": "Pressure(kPa)"},
            "ignition_time": {"channel": "Temperature(°C)"}
        }
        
        channels = analyzer.get_required_channels(config)
        
        expected_channels = {"Pressure(kPa)", "Temperature(°C)"}
        assert set(channels) == expected_channels


class TestRealStatusEvaluator:
    """Test cases for RealStatusEvaluator"""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance"""
        return RealStatusEvaluator()
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for status evaluation"""
        data = []
        
        # Temperature channel - for overtemperature check
        temp_points = []
        for i in range(1000):
            timestamp = i * 0.01
            # Keep temperature below 850°C (normal)
            value = 650 + np.random.normal(0, 50)
            temp_points.append(DataPoint(timestamp=timestamp, value=value))
        
        temp_channel = ChannelData(
            channel_name="Temperature(°C)",
            unit="°C",
            data_points=temp_points,
            sample_rate=100.0
        )
        
        # Pressure channel - for surge check
        press_points = []
        for i in range(1000):
            timestamp = i * 0.01
            # Keep pressure stable (no surge)
            value = 800 + np.random.normal(0, 20)
            press_points.append(DataPoint(timestamp=timestamp, value=value))
        
        press_channel = ChannelData(
            channel_name="Pressure(kPa)",
            unit="kPa",
            data_points=press_points,
            sample_rate=100.0
        )
        
        # Ng channel - for overspeed check
        ng_points = []
        for i in range(1000):
            timestamp = i * 0.01
            # Keep speed below 18000 rpm (normal)
            value = 15000 + np.random.normal(0, 200)
            ng_points.append(DataPoint(timestamp=timestamp, value=value))
        
        ng_channel = ChannelData(
            channel_name="Ng(rpm)",
            unit="rpm",
            data_points=ng_points,
            sample_rate=100.0
        )
        
        return [temp_channel, press_channel, ng_channel]
    
    def test_analyze_status_eval(self, evaluator, sample_data):
        """Test status evaluation analysis"""
        config = {
            "evaluations": [
                {
                    "item": "超温评估",
                    "type": "continuous_check",
                    "conditionLogic": "AND",
                    "conditions": [
                        {
                            "channel": "Temperature(°C)",
                            "statistic": "瞬时值",
                            "logic": "<",
                            "threshold": 850
                        }
                    ]
                },
                {
                    "item": "超转评估",
                    "type": "continuous_check",
                    "conditionLogic": "AND",
                    "conditions": [
                        {
                            "channel": "Ng(rpm)",
                            "statistic": "瞬时值",
                            "logic": "<",
                            "threshold": 18000
                        }
                    ]
                },
                {
                    "item": "喘振评估",
                    "type": "event_check",
                    "condition": {
                        "channel": "Pressure(kPa)",
                        "type": "difference",
                        "duration": 0.1,
                        "logic": ">",
                        "threshold": 200
                    },
                    "expected": "never_happen"
                }
            ]
        }
        
        result = evaluator.analyze(sample_data, config)
        
        assert result.analysis_type == "status_eval"
        
        eval_data = result.result_data
        assert "evaluations" in eval_data
        assert "overall_status" in eval_data
        assert "warnings" in eval_data
        
        evaluations = eval_data["evaluations"]
        assert len(evaluations) == 3
        
        for evaluation in evaluations:
            assert "item" in evaluation
            assert "result" in evaluation
            assert "status" in evaluation
    
    def test_evaluate_continuous_check(self, evaluator, sample_data):
        """Test continuous check evaluation"""
        data_dict = {channel.channel_name: channel for channel in sample_data}
        
        eval_config = {
            "item": "超温评估",
            "type": "continuous_check",
            "conditionLogic": "AND",
            "conditions": [
                {
                    "channel": "Temperature(°C)",
                    "statistic": "瞬时值",
                    "logic": "<",
                    "threshold": 850
                }
            ]
        }
        
        result = evaluator._evaluate_single_item(data_dict, eval_config)
        
        assert result["item"] == "超温评估"
        assert result["result"] in ["正常", "异常"]
        assert result["status"] in ["✓", "✗"]
    
    def test_evaluate_event_check(self, evaluator, sample_data):
        """Test event check evaluation"""
        data_dict = {channel.channel_name: channel for channel in sample_data}
        
        eval_config = {
            "item": "喘振评估",
            "type": "event_check",
            "condition": {
                "channel": "Pressure(kPa)",
                "type": "difference",
                "duration": 0.1,
                "logic": ">",
                "threshold": 200
            },
            "expected": "never_happen"
        }
        
        result = evaluator._evaluate_single_item(data_dict, eval_config)
        
        assert result["item"] == "喘振评估"
        assert result["result"] in ["正常", "异常"]
    
    def test_validate_config(self, evaluator):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "evaluations": [
                {"item": "test", "type": "continuous_check"}
            ]
        }
        
        assert evaluator.validate_config(valid_config) is True
        
        # Invalid config - no evaluations
        invalid_config = {}
        assert evaluator.validate_config(invalid_config) is False
        
        # Invalid config - empty evaluations
        invalid_config2 = {"evaluations": []}
        assert evaluator.validate_config(invalid_config2) is False


class TestRealReportCalculationEngine:
    """Test cases for RealReportCalculationEngine"""
    
    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return RealReportCalculationEngine()
    
    @pytest.fixture
    def sample_data(self):
        """Create comprehensive sample data"""
        data = []
        
        # Create multiple channels for comprehensive testing
        channels_config = [
            ("Ng(rpm)", "rpm", lambda i, t: 15000 + 500 * np.sin(i * 0.1) + np.random.normal(0, 100)),
            ("Temperature(°C)", "°C", lambda i, t: 650 + 50 * np.sin(i * 0.05) + np.random.normal(0, 20)),
            ("Pressure(kPa)", "kPa", lambda i, t: 800 + 200 * np.sin(i * 0.08) + np.random.normal(0, 30))
        ]
        
        for channel_name, unit, value_func in channels_config:
            points = []
            for i in range(500):
                timestamp = i * 0.01
                value = value_func(i, timestamp)
                points.append(DataPoint(timestamp=timestamp, value=value))
            
            channel = ChannelData(
                channel_name=channel_name,
                unit=unit,
                data_points=points,
                sample_rate=100.0
            )
            data.append(channel)
        
        return data
    
    @pytest.fixture
    def sample_config(self):
        """Create sample report configuration"""
        from models.report_config import (
            ReportConfig, ReportConfigData, StableStateConfig,
            FunctionalCalcConfig, StatusEvalConfig, ConditionConfig, EvaluationConfig
        )
        
        stable_config = StableStateConfig(
            displayChannels=["Ng(rpm)", "Temperature(°C)"],
            condition=ConditionConfig(
                channel="Ng(rpm)",
                statistic="平均值",
                duration=0.1,
                logic=">",
                threshold=14000
            )
        )
        
        func_config = FunctionalCalcConfig()
        
        status_config = StatusEvalConfig(
            evaluations=[
                EvaluationConfig(
                    item="超温",
                    channel="Temperature(°C)",
                    logic="<",
                    threshold=850
                )
            ]
        )
        
        report_config_data = ReportConfigData(
            sections=["stableState", "functionalCalc", "statusEval"],
            stableState=stable_config,
            functionalCalc=func_config,
            statusEval=status_config
        )
        
        return ReportConfig(
            sourceFileId="test_file",
            reportConfig=report_config_data
        )
    
    def test_generate_report(self, engine, sample_data, sample_config):
        """Test complete report generation"""
        report_data = engine.generate(sample_data, sample_config)
        
        assert report_data.report_id is not None
        assert report_data.source_file_id == "test_file"
        assert report_data.generation_time is not None
        
        # Check that results were generated
        assert report_data.stable_state_result is not None
        assert report_data.status_eval_result is not None
    
    def test_validate_data_completeness(self, engine, sample_data, sample_config):
        """Test data completeness validation"""
        # Should pass with complete data
        assert engine.validate_data_completeness(sample_data, sample_config) is True
        
        # Should fail with incomplete data (missing required channels)
        # Create config that requires channels not in our single-channel data
        minimal_config = ReportConfig(
            source_file_id="test_file",
            report_config=ReportConfigData(
                sections=["stableState"],
                stableState=StableStateConfig(
                    displayChannels=["Ng(rpm)", "Temperature(°C)"],  # Requires 2 channels
                    condition=ConditionConfig(
                        channel="Ng(rpm)",
                        statistic="平均值",
                        duration=0.1,
                        logic=">",
                        threshold=14000.0
                    )
                ),
                functionalCalc=FunctionalCalcConfig(),
                statusEval=StatusEvalConfig(evaluations=[])
            )
        )
        incomplete_data = sample_data[:1]  # Only one channel
        assert engine.validate_data_completeness(incomplete_data, minimal_config) is False
    
    def test_preprocess_data(self, engine, sample_data):
        """Test data preprocessing"""
        processed_data = engine.preprocess_data(sample_data)
        
        assert len(processed_data) == len(sample_data)
        
        for original, processed in zip(sample_data, processed_data):
            assert processed.channel_name == original.channel_name
            assert processed.unit == original.unit
            # Processed data should have same or fewer points (after cleaning)
            assert len(processed.data_points) <= len(original.data_points)
    
    def test_register_analyzer(self, engine):
        """Test analyzer registration"""
        # Create a mock analyzer
        class MockAnalyzer:
            pass
        
        mock_analyzer = MockAnalyzer()
        engine.register_analyzer("test_analyzer", mock_analyzer)
        
        assert "test_analyzer" in engine.analyzers
        assert engine.analyzers["test_analyzer"] is mock_analyzer
