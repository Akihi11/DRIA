"""
Mock implementations of data service interfaces for Phase 1 testing - Python 3.12 compatible
"""
from typing import List, Dict, Any
from pathlib import Path
import csv
import json
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from interfaces.data_interfaces import DataReader, ReportWriter
from models.data_models import ChannelData, DataPoint, ReportData


class MockDataReader(DataReader):
    """Mock implementation of DataReader for testing - Python 3.12 compatible"""
    
    def read(self, file_path: str, channel_names: List[str]) -> List[ChannelData]:
        """Mock data reading - generates sample data without pandas dependency"""
        
        # Simulate reading different file types
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in ['.csv', '.xlsx', '.xls']:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        channels = []
        
        for channel_name in channel_names:
            # Generate mock data points based on channel type
            data_points = self._generate_mock_data_points(channel_name)
            
            channel_data = ChannelData(
                channel_name=channel_name,
                unit=self._get_channel_unit(channel_name),
                data_points=data_points,
                sample_rate=33.3  # Mock sample rate
            )
            
            channels.append(channel_data)
        
        return channels
    
    def get_available_channels(self, file_path: str) -> List[str]:
        """Mock channel detection"""
        
        # Return standard mock channels
        return [
            "Ng(rpm)",
            "Temperature(°C)", 
            "Pressure(kPa)",
            "Fuel_Flow(kg/h)",
            "Vibration(mm/s)",
            "Voltage(V)",
            "Current(A)"
        ]
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Mock file metadata extraction"""
        
        file_path_obj = Path(file_path)
        
        return {
            "filename": file_path_obj.name,
            "file_size": 1024000,  # Mock 1MB
            "total_samples": 10000,
            "duration_seconds": 300.3,
            "sample_rate": 33.3,
            "channels_count": 7,
            "file_format": file_path_obj.suffix.lower(),
            "created_time": datetime.now().isoformat()
        }
    
    def _generate_mock_data_points(self, channel_name: str) -> List[DataPoint]:
        """Generate mock data points for a channel"""
        
        data_points = []
        
        # Generate 1000 mock data points
        for i in range(1000):
            timestamp = i * 0.03  # 30ms intervals
            value = self._generate_mock_value(channel_name, i)
            
            data_points.append(DataPoint(timestamp=timestamp, value=value))
        
        return data_points
    
    def _generate_mock_value(self, channel_name: str, index: int) -> float:
        """Generate mock values based on channel type"""
        
        import math
        import random
        
        base_patterns = {
            "Ng(rpm)": 15000 + 500 * math.sin(index * 0.01) + random.uniform(-100, 100),
            "Temperature(°C)": 650 + 50 * math.sin(index * 0.005) + random.uniform(-10, 10),
            "Pressure(kPa)": 800 + 200 * math.sin(index * 0.008) + random.uniform(-20, 20),
            "Fuel_Flow(kg/h)": 5.5 + 0.5 * math.sin(index * 0.006) + random.uniform(-0.1, 0.1),
            "Vibration(mm/s)": 2.0 + 0.3 * math.sin(index * 0.02) + random.uniform(-0.2, 0.2),
            "Voltage(V)": 24.0 + 1.0 * math.sin(index * 0.003) + random.uniform(-0.5, 0.5),
            "Current(A)": 10.0 + 2.0 * math.sin(index * 0.004) + random.uniform(-0.3, 0.3)
        }
        
        return base_patterns.get(channel_name, random.uniform(0, 100))
    
    def _get_channel_unit(self, channel_name: str) -> str:
        """Get unit for channel"""
        
        unit_map = {
            "Ng(rpm)": "rpm",
            "Temperature(°C)": "°C",
            "Pressure(kPa)": "kPa", 
            "Fuel_Flow(kg/h)": "kg/h",
            "Vibration(mm/s)": "mm/s",
            "Voltage(V)": "V",
            "Current(A)": "A"
        }
        
        return unit_map.get(channel_name, "")


class MockReportWriter(ReportWriter):
    """Mock implementation of ReportWriter for testing - Python 3.12 compatible"""
    
    def write(self, output_path: str, report_data: ReportData) -> bool:
        """Mock report writing"""
        
        try:
            # Create output directory
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Mock Excel file creation
            return self.create_excel_report(output_path, report_data)
            
        except Exception as e:
            print(f"Mock report writing failed: {e}")
            return False
    
    def create_excel_report(self, output_path: str, report_data: ReportData) -> bool:
        """Mock Excel report creation - creates a detailed text file instead"""
        
        try:
            content = self._generate_mock_excel_content(report_data)
            
            # Write as UTF-8 encoded text file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Mock Excel creation failed: {e}")
            return False
    
    def add_charts_to_report(self, report_path: str, chart_configs: List[Dict[str, Any]]) -> bool:
        """Mock chart addition"""
        
        # Mock implementation - in reality would add charts to Excel
        print(f"Mock: Adding {len(chart_configs)} charts to {report_path}")
        return True
    
    def _generate_mock_excel_content(self, report_data: ReportData) -> str:
        """Generate mock Excel file content with detailed structure"""
        
        content = [
            "AI Report Generation System - Mock Excel Report",
            "=" * 60,
            f"Generated at: {report_data.generation_time}",
            f"Report ID: {report_data.report_id}",
            f"Source File ID: {report_data.source_file_id}",
            "",
            "This is a mock Excel report file for Phase 1 testing.",
            "In Phase 2, this will be replaced with real Excel generation using openpyxl.",
            "",
            "=" * 60
        ]
        
        if report_data.stable_state_result:
            content.extend([
                "",
                "📊 稳定状态参数汇总表",
                "=" * 30,
                f"总稳定时间: {report_data.stable_state_result.total_stable_time:.2f} 秒",
                f"稳定时段数量: {len(report_data.stable_state_result.stable_periods)}",
                "",
                "稳定时段详情:",
                "-" * 20
            ])
            
            for i, period in enumerate(report_data.stable_state_result.stable_periods, 1):
                content.append(f"时段 {i}: {period.get('start_time', 0):.2f}s - {period.get('end_time', 0):.2f}s")
            
            content.extend([
                "",
                "通道统计数据:",
                "-" * 20
            ])
            
            for channel, stats in report_data.stable_state_result.channel_statistics.items():
                content.append(f"{channel}: 平均值={stats.get('mean', 0):.2f}, 最大值={stats.get('max', 0):.2f}")
        
        if report_data.functional_calc_result:
            content.extend([
                "",
                "⚡ 功能计算汇总表", 
                "=" * 30
            ])
            
            if report_data.functional_calc_result.time_base:
                content.append(f"时间基准: {report_data.functional_calc_result.time_base:.2f} 秒")
            if report_data.functional_calc_result.startup_time:
                content.append(f"启动时间: {report_data.functional_calc_result.startup_time:.2f} 秒")
            if report_data.functional_calc_result.ignition_time:
                content.append(f"点火时间: {report_data.functional_calc_result.ignition_time:.2f} 秒")
            if report_data.functional_calc_result.rundown_ng:
                content.append(f"Ng余转时间: {report_data.functional_calc_result.rundown_ng:.2f} 秒")
        
        if report_data.status_eval_result:
            content.extend([
                "",
                "✅ 状态评估表",
                "=" * 30,
                f"总体状态: {report_data.status_eval_result.overall_status}",
                f"评估项数量: {len(report_data.status_eval_result.evaluations)}",
                ""
            ])
            
            if report_data.status_eval_result.warnings:
                content.extend([
                    "⚠️ 警告信息:",
                    "-" * 15
                ])
                for warning in report_data.status_eval_result.warnings:
                    content.append(f"• {warning}")
            
            content.extend([
                "",
                "评估结果详情:",
                "-" * 15
            ])
            
            for eval_item in report_data.status_eval_result.evaluations:
                item_name = eval_item.get('item', 'Unknown')
                result = eval_item.get('result', 'Unknown')
                status = eval_item.get('status', '?')
                content.append(f"{item_name}: {result} {status}")
        
        content.extend([
            "",
            "=" * 60,
            "报表生成完成",
            f"文件路径: {report_data.excel_file_path or 'N/A'}",
            "",
            "注意：这是Phase 1的Mock实现，用于API测试。",
            "Phase 2将实现真实的Excel文件生成功能。"
        ])
        
        return "\n".join(content)
