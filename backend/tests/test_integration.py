"""
Integration tests for complete end-to-end functionality
"""
import pytest
import tempfile
import os
import json
from pathlib import Path
import numpy as np

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.real_data_service import RealDataReader, RealReportWriter
from services.real_analysis_service import RealReportCalculationEngine
from models.report_config import ReportConfig


class TestEndToEndIntegration:
    """Test complete end-to-end report generation"""
    
    @pytest.fixture
    def sample_data_file(self):
        """Create a comprehensive test data file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            # Write header
            f.write("time[s],Ng(rpm),Np(rpm),Temperature(°C),Pressure(kPa)\n")
            
            # Generate 1000 data points (10 seconds at 100Hz)
            for i in range(1000):
                time_val = i * 0.01
                
                # Ng: stable periods at 2-4s and 6-8s
                if 200 <= i <= 400 or 600 <= i <= 800:
                    ng_val = 15000 + np.random.normal(0, 50)  # Stable
                else:
                    ng_val = 10000 + 3000 * np.sin(i * 0.05) + np.random.normal(0, 200)  # Unstable
                
                # Np: similar pattern but different values
                if 200 <= i <= 400 or 600 <= i <= 800:
                    np_val = 12000 + np.random.normal(0, 40)
                else:
                    np_val = 8000 + 2000 * np.sin(i * 0.04) + np.random.normal(0, 150)
                
                # Temperature: gradual rise with jump at t=3s
                if time_val < 3.0:
                    temp_val = 200 + time_val * 50 + np.random.normal(0, 10)
                else:
                    temp_val = 400 + (time_val - 3.0) * 30 + np.random.normal(0, 15)
                
                # Pressure: step changes for functional analysis
                if time_val < 1.0:
                    press_val = 100 + np.random.normal(0, 10)  # Low
                elif time_val < 3.0:
                    press_val = 600 + np.random.normal(0, 20)  # Medium (>500)
                elif time_val < 7.0:
                    press_val = 1200 + np.random.normal(0, 30)  # High (>1000)
                else:
                    press_val = 800 + np.random.normal(0, 25)  # Back to medium
                
                f.write(f"{time_val},{ng_val},{np_val},{temp_val},{press_val}\n")
            
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        os.unlink(temp_file)
    
    @pytest.fixture
    def comprehensive_config(self):
        """Create comprehensive test configuration"""
        config_dict = {
            "sourceFileId": "test_integration_file",
            "reportConfig": {
                "sections": ["stableState", "functionalCalc", "statusEval"],
                "stableState": {
                    "displayChannels": ["Ng(rpm)", "Np(rpm)", "Temperature(°C)", "Pressure(kPa)"],
                    "conditionLogic": "AND",
                    "conditions": [
                        {
                            "type": "statistic",
                            "channel": "Ng(rpm)",
                            "statistic": "平均值",
                            "duration": 0.1,
                            "logic": ">",
                            "threshold": 14000
                        },
                        {
                            "type": "amplitude_change",
                            "channel": "Ng(rpm)",
                            "duration": 0.5,
                            "logic": "<",
                            "threshold": 200
                        }
                    ]
                },
                "functionalCalc": {
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
                        "duration": 0.2,
                        "logic": ">",
                        "threshold": 50
                    },
                    "rundown_ng": {
                        "channel": "Ng(rpm)",
                        "statistic": "平均值",
                        "duration": 0.1,
                        "threshold1": 13000,
                        "threshold2": 8000
                    }
                },
                "statusEval": {
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
                                "threshold": 300
                            },
                            "expected": "never_happen"
                        }
                    ]
                }
            }
        }
        
        return ReportConfig(**config_dict)
    
    def test_complete_pipeline(self, sample_data_file, comprehensive_config):
        """Test the complete data processing pipeline"""
        # Step 1: Read data
        data_reader = RealDataReader()
        
        # Get available channels
        available_channels = data_reader.get_available_channels(sample_data_file)
        assert len(available_channels) >= 4
        
        # Get file metadata
        metadata = data_reader.get_file_metadata(sample_data_file)
        assert metadata["total_samples"] == 1000
        assert metadata["duration_seconds"] > 9.0
        
        # Read channel data
        required_channels = ["Ng(rpm)", "Np(rpm)", "Temperature(°C)", "Pressure(kPa)"]
        channel_data = data_reader.read(sample_data_file, required_channels)
        
        assert len(channel_data) == 4
        for channel in channel_data:
            assert len(channel.data_points) == 1000
        
        # Step 2: Analyze data
        calculation_engine = RealReportCalculationEngine()
        
        # Validate data completeness
        assert calculation_engine.validate_data_completeness(channel_data, comprehensive_config)
        
        # Generate report
        report_data = calculation_engine.generate(channel_data, comprehensive_config)
        
        # Verify report structure
        assert report_data.report_id is not None
        assert report_data.source_file_id == "test_integration_file"
        
        # Verify stable state results
        assert report_data.stable_state_result is not None
        stable_result = report_data.stable_state_result
        assert stable_result.total_stable_time >= 0
        assert isinstance(stable_result.stable_periods, list)
        assert isinstance(stable_result.channel_statistics, dict)
        
        # Verify functional calc results
        assert report_data.functional_calc_result is not None
        func_result = report_data.functional_calc_result
        # At least some metrics should be calculated
        metrics = [func_result.time_base, func_result.startup_time, 
                  func_result.ignition_time, func_result.rundown_ng]
        assert any(metric is not None for metric in metrics)
        
        # Verify status evaluation results
        assert report_data.status_eval_result is not None
        status_result = report_data.status_eval_result
        assert len(status_result.evaluations) == 3
        assert status_result.overall_status in ["正常", "存在异常"]
        
        # Step 3: Write report
        report_writer = RealReportWriter()
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name
        
        try:
            success = report_writer.write(output_path, report_data)
            assert success is not None
            
            # Verify file was created
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
            
        finally:
            if Path(output_path).exists():
                os.unlink(output_path)
    
    def test_error_handling(self, comprehensive_config):
        """Test error handling in the pipeline"""
        # Test with non-existent file
        data_reader = RealDataReader()
        
        with pytest.raises(FileNotFoundError):
            data_reader.read("non_existent_file.csv", ["Ng(rpm)"])
        
        # Test with incomplete data
        calculation_engine = RealReportCalculationEngine()
        
        # Create minimal data that will fail validation
        from models.data_models import ChannelData, DataPoint
        
        minimal_data = [
            ChannelData(
                channel_name="Ng(rpm)",
                unit="rpm",
                data_points=[DataPoint(timestamp=0.0, value=15000.0)],  # Only 1 point
                sample_rate=1.0
            )
        ]
        
        # Should fail data completeness check
        assert not calculation_engine.validate_data_completeness(minimal_data, comprehensive_config)
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        # Test invalid configuration
        invalid_config_dict = {
            "sourceFileId": "test",
            "reportConfig": {
                "sections": ["invalidSection"]  # Invalid section
            }
        }
        
        # Should raise validation error when creating ReportConfig
        with pytest.raises(Exception):  # Pydantic validation error
            ReportConfig(**invalid_config_dict)
    
    def test_sample_config_compatibility(self, sample_data_file):
        """Test compatibility with the sample configuration file"""
        # Load the actual sample configuration
        sample_config_path = Path(__file__).parent.parent.parent / "samples" / "config_full.json"
        
        if sample_config_path.exists():
            with open(sample_config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # Create ReportConfig from sample
            config = ReportConfig(**config_dict)
            
            # Test with our sample data
            data_reader = RealDataReader()
            required_channels = ["Ng", "Np", "Temperature", "Pressure"]  # Simplified names
            
            try:
                channel_data = data_reader.read(sample_data_file, required_channels)
                
                calculation_engine = RealReportCalculationEngine()
                
                # This might fail due to channel name mismatches, but should not crash
                try:
                    report_data = calculation_engine.generate(channel_data, config)
                    assert report_data is not None
                except (ValueError, KeyError) as e:
                    # Expected due to channel name differences
                    assert "not found" in str(e) or "Channel" in str(e)
                    
            except Exception as e:
                # Channel mapping issues are expected
                assert "Channel" in str(e) or "not found" in str(e)


class TestPerformanceAndScalability:
    """Test performance and scalability aspects"""
    
    def test_large_dataset_processing(self):
        """Test processing of large datasets"""
        # Create large dataset (10,000 points)
        from models.data_models import ChannelData, DataPoint
        
        large_data = []
        
        for channel_name in ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"]:
            points = []
            for i in range(10000):
                timestamp = i * 0.001  # 1ms intervals
                value = 1000 + 500 * np.sin(i * 0.01) + np.random.normal(0, 50)
                points.append(DataPoint(timestamp=timestamp, value=value))
            
            channel = ChannelData(
                channel_name=channel_name,
                unit="unit",
                data_points=points,
                sample_rate=1000.0
            )
            large_data.append(channel)
        
        # Test that processing completes within reasonable time
        import time
        start_time = time.time()
        
        calculation_engine = RealReportCalculationEngine()
        processed_data = calculation_engine.preprocess_data(large_data)
        
        processing_time = time.time() - start_time
        
        # Should complete within 10 seconds for 10k points
        assert processing_time < 10.0
        assert len(processed_data) == 3
        
        for channel in processed_data:
            # Should retain most data points after preprocessing
            assert len(channel.data_points) >= 9000
    
    def test_memory_efficiency(self):
        """Test memory usage with multiple analyses"""
        # This is a basic test - in production you'd use memory profiling tools
        
        from models.data_models import ChannelData, DataPoint
        
        # Create moderate-sized dataset
        data = []
        for channel_name in ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"]:
            points = []
            for i in range(1000):
                points.append(DataPoint(timestamp=i * 0.01, value=1000 + i))
            
            data.append(ChannelData(
                channel_name=channel_name,
                unit="unit",
                data_points=points,
                sample_rate=100.0
            ))
        
        # Run multiple analyses to check for memory leaks
        calculation_engine = RealReportCalculationEngine()
        
        for _ in range(10):
            processed_data = calculation_engine.preprocess_data(data)
            # Should not accumulate memory
            assert len(processed_data) == 3
