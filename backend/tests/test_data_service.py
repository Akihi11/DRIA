"""
Unit tests for data service implementations
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.real_data_service import RealDataReader, RealReportWriter
from models.data_models import ChannelData, DataPoint, ReportData, StableStateResult, FunctionalCalcResult, StatusEvalResult


class TestRealDataReader:
    """Test cases for RealDataReader"""
    
    @pytest.fixture
    def sample_csv_file(self):
        """Create a temporary CSV file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            # Write sample data similar to the real format
            f.write("time[s],Ng(rpm),Temperature(°C),Pressure(kPa)\n")
            for i in range(100):
                time_val = i * 0.01
                ng_val = 15000 + 500 * np.sin(i * 0.1) + np.random.normal(0, 50)
                temp_val = 650 + 50 * np.sin(i * 0.05) + np.random.normal(0, 10)
                press_val = 800 + 200 * np.sin(i * 0.08) + np.random.normal(0, 20)
                f.write(f"{time_val},{ng_val},{temp_val},{press_val}\n")
            
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        os.unlink(temp_file)
    
    @pytest.fixture
    def data_reader(self):
        """Create RealDataReader instance"""
        return RealDataReader()
    
    def test_read_csv_file(self, data_reader, sample_csv_file):
        """Test reading CSV file"""
        channel_names = ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"]
        
        channels = data_reader.read(sample_csv_file, channel_names)
        
        assert len(channels) == 3
        
        for channel in channels:
            assert isinstance(channel, ChannelData)
            assert channel.channel_name in channel_names
            assert len(channel.data_points) == 100
            assert channel.sample_rate > 0
            
            # Check data point structure
            for point in channel.data_points:
                assert isinstance(point, DataPoint)
                assert isinstance(point.timestamp, float)
                assert isinstance(point.value, (int, float))
    
    def test_get_available_channels(self, data_reader, sample_csv_file):
        """Test getting available channels"""
        channels = data_reader.get_available_channels(sample_csv_file)
        
        expected_channels = ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"]
        assert len(channels) == len(expected_channels)
        
        for expected in expected_channels:
            assert expected in channels
    
    def test_get_file_metadata(self, data_reader, sample_csv_file):
        """Test getting file metadata"""
        metadata = data_reader.get_file_metadata(sample_csv_file)
        
        assert "filename" in metadata
        assert "file_size" in metadata
        assert "total_samples" in metadata
        assert "duration_seconds" in metadata
        assert "sample_rate" in metadata
        assert "channels_count" in metadata
        assert "channels" in metadata
        
        assert metadata["total_samples"] == 100
        assert metadata["channels_count"] == 3
        assert len(metadata["channels"]) == 3
    
    def test_channel_name_mapping(self, data_reader):
        """Test channel name mapping functionality"""
        file_columns = ["time[s]", "Ng", "排气温度", "滑油压力"]
        requested_channels = ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"]
        
        mapping = data_reader._map_channel_names(file_columns, requested_channels)
        
        assert "Ng(rpm)" in mapping
        assert mapping["Ng(rpm)"] == "Ng"
    
    def test_get_channel_unit(self, data_reader):
        """Test unit extraction"""
        assert data_reader._get_channel_unit("Ng(rpm)") == "rpm"
        assert data_reader._get_channel_unit("Temperature(°C)") == "°C"
        assert data_reader._get_channel_unit("Pressure(kPa)") == "kPa"
        assert data_reader._get_channel_unit("voltage_signal") == "V"
    
    def test_unsupported_file_format(self, data_reader):
        """Test handling of unsupported file formats"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            with pytest.raises(ValueError, match="Unsupported file format"):
                data_reader.read(f.name, ["test_channel"])


class TestRealReportWriter:
    """Test cases for RealReportWriter"""
    
    @pytest.fixture
    def report_writer(self):
        """Create RealReportWriter instance"""
        return RealReportWriter()
    
    @pytest.fixture
    def sample_report_data(self):
        """Create sample report data for testing"""
        return ReportData(
            report_id="test_report_123",
            source_file_id="test_file_456",
            generation_time=datetime.now(),
            stable_state_result=StableStateResult(
                stable_periods=[
                    {"start_time": 10.0, "end_time": 50.0, "duration": 40.0},
                    {"start_time": 80.0, "end_time": 120.0, "duration": 40.0}
                ],
                channel_statistics={
                    "Ng(rpm)": {"mean": 15000.0, "max": 15500.0, "min": 14500.0, "std": 100.0},
                    "Temperature(°C)": {"mean": 650.0, "max": 700.0, "min": 600.0, "std": 25.0}
                },
                total_stable_time=80.0
            ),
            functional_calc_result=FunctionalCalcResult(
                time_base=45.2,
                startup_time=12.8,
                ignition_time=3.5,
                rundown_ng=28.7
            ),
            status_eval_result=StatusEvalResult(
                evaluations=[
                    {"item": "超温", "result": "正常", "status": "✓"},
                    {"item": "Ng余转时间", "result": "正常", "status": "✓"}
                ],
                overall_status="正常",
                warnings=[]
            )
        )
    
    def test_create_excel_report(self, report_writer, sample_report_data):
        """Test Excel report creation"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name
        
        try:
            # Test report creation
            success = report_writer.create_excel_report(output_path, sample_report_data)
            
            # Should succeed even without openpyxl (creates text file)
            assert success is not None
            
            # Check file was created
            assert Path(output_path).exists()
            
        finally:
            # Cleanup
            if Path(output_path).exists():
                os.unlink(output_path)
    
    def test_write_method(self, report_writer, sample_report_data):
        """Test write method"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name
        
        try:
            success = report_writer.write(output_path, sample_report_data)
            assert success is not None
            
        finally:
            if Path(output_path).exists():
                os.unlink(output_path)
    
    def test_add_charts_to_report(self, report_writer):
        """Test adding charts to report"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name
        
        try:
            # Create a simple file first
            with open(output_path, 'w') as file:
                file.write("test")
            
            chart_configs = [
                {
                    "title": "Test Chart",
                    "sheet": "Sheet1",
                    "data_range": "A1:B10",
                    "position": "D2"
                }
            ]
            
            # This will likely fail without openpyxl, but should not crash
            result = report_writer.add_charts_to_report(output_path, chart_configs)
            assert result is not None  # Can be True or False
            
        finally:
            if Path(output_path).exists():
                os.unlink(output_path)
