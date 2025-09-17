"""
Data processing and analysis models
"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class DataPoint(BaseModel):
    """单个数据点模型"""
    timestamp: float = Field(..., description="时间戳")
    value: Union[float, int] = Field(..., description="数值")


class ChannelData(BaseModel):
    """通道数据模型"""
    channel_name: str = Field(..., description="通道名称")
    unit: Optional[str] = Field(None, description="单位")
    data_points: List[DataPoint] = Field(..., description="数据点列表")
    sample_rate: Optional[float] = Field(None, description="采样率")
    
    @property
    def values(self) -> List[Union[float, int]]:
        """获取所有数值"""
        return [point.value for point in self.data_points]
    
    @property
    def timestamps(self) -> List[float]:
        """获取所有时间戳"""
        return [point.timestamp for point in self.data_points]


class FileMetadata(BaseModel):
    """文件元数据模型"""
    file_id: str = Field(..., description="文件ID")
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(..., description="文件大小")
    upload_time: datetime = Field(..., description="上传时间")
    channels: List[str] = Field(..., description="通道列表")
    total_samples: int = Field(..., description="总样本数")
    duration: Optional[float] = Field(None, description="数据时长（秒）")


class AnalysisResult(BaseModel):
    """分析结果模型"""
    analysis_type: str = Field(..., description="分析类型")
    result_data: Dict[str, Any] = Field(..., description="结果数据")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    calculation_time: datetime = Field(..., description="计算时间")


class StableStateResult(BaseModel):
    """稳定状态分析结果"""
    stable_periods: List[Dict[str, Any]] = Field(..., description="稳定时段列表")
    channel_statistics: Dict[str, Dict[str, float]] = Field(..., description="通道统计数据")
    total_stable_time: float = Field(..., description="总稳定时间")


class FunctionalCalcResult(BaseModel):
    """功能计算分析结果"""
    time_base: Optional[float] = Field(None, description="时间基准")
    startup_time: Optional[float] = Field(None, description="启动时间")
    ignition_time: Optional[float] = Field(None, description="点火时间")
    rundown_ng: Optional[float] = Field(None, description="Ng余转时间")


class StatusEvalResult(BaseModel):
    """状态评估分析结果"""
    evaluations: List[Dict[str, Any]] = Field(..., description="评估结果列表")
    overall_status: str = Field(..., description="总体状态")
    warnings: List[str] = Field(default_factory=list, description="警告信息")


class ReportData(BaseModel):
    """完整报表数据模型"""
    report_id: str = Field(..., description="报表ID")
    source_file_id: str = Field(..., description="源文件ID")
    generation_time: datetime = Field(..., description="生成时间")
    stable_state_result: Optional[StableStateResult] = Field(None, description="稳定状态结果")
    functional_calc_result: Optional[FunctionalCalcResult] = Field(None, description="功能计算结果")
    status_eval_result: Optional[StatusEvalResult] = Field(None, description="状态评估结果")
    excel_file_path: Optional[str] = Field(None, description="Excel文件路径")
