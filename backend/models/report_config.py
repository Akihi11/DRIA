"""
Report configuration data models based on the specification
"""
from typing import List, Dict, Optional, Literal, Union
from pydantic import BaseModel, Field


class ConditionConfig(BaseModel):
    """稳定状态筛选条件配置"""
    channel: str = Field(..., description="通道名称")
    statistic: Literal["最大值", "最小值", "平均值", "有效值"] = Field(..., description="统计量类型")
    duration: float = Field(..., description="持续时间（秒）")
    logic: Literal[">", "<"] = Field(..., description="逻辑判断符")
    threshold: float = Field(..., description="阈值")


class StableStateConfig(BaseModel):
    """稳定状态参数汇总表配置"""
    display_channels: List[str] = Field(..., alias="displayChannels", description="需要显示的通道列表")
    condition: ConditionConfig = Field(..., description="稳定状态筛选条件")


class TimeBaseConfig(BaseModel):
    """时间基准配置"""
    channel: str = Field(..., description="通道名称")
    statistic: Literal["最大值", "最小值", "平均值", "有效值"] = Field(..., description="统计量类型")
    duration: float = Field(..., description="持续时间（秒）")
    logic: Literal[">", "<"] = Field(..., description="逻辑判断符")
    threshold: float = Field(..., description="阈值")


class StartupTimeConfig(BaseModel):
    """启动时间配置"""
    channel: str = Field(..., description="通道名称")
    statistic: Literal["最大值", "最小值", "平均值", "有效值"] = Field(..., description="统计量类型")
    duration: float = Field(..., description="持续时间（秒）")
    logic: Literal[">", "<"] = Field(..., description="逻辑判断符")
    threshold: float = Field(..., description="阈值")


class IgnitionTimeConfig(BaseModel):
    """点火时间配置"""
    channel: str = Field(..., description="通道名称")
    duration: float = Field(..., description="持续时间（秒）")
    logic: Literal["突变>", "突变<"] = Field(..., description="突变逻辑")
    threshold: float = Field(..., description="突变阈值")


class RundownNgConfig(BaseModel):
    """Ng余转时间配置"""
    channel: str = Field(..., description="通道名称")
    threshold1: float = Field(..., description="第一阈值")
    threshold2: float = Field(..., description="第二阈值")


class FunctionalCalcConfig(BaseModel):
    """功能计算汇总表配置"""
    time_base: Optional[TimeBaseConfig] = None
    startup_time: Optional[StartupTimeConfig] = None
    ignition_time: Optional[IgnitionTimeConfig] = None
    rundown_ng: Optional[RundownNgConfig] = None


class EvaluationConfig(BaseModel):
    """状态评估项配置"""
    item: str = Field(..., description="评估项名称")
    channel: Optional[str] = Field(None, description="通道名称（可选）")
    logic: Literal[">", "<"] = Field(..., description="逻辑判断符")
    threshold: float = Field(..., description="阈值")


class StatusEvalConfig(BaseModel):
    """状态评估表配置"""
    evaluations: List[EvaluationConfig] = Field(..., description="评估项列表")


class ReportConfigData(BaseModel):
    """报表配置数据"""
    sections: List[Literal["stableState", "functionalCalc", "statusEval"]] = Field(
        ..., description="需要生成的报表部分"
    )
    stable_state: Optional[StableStateConfig] = Field(None, alias="stableState")
    functional_calc: Optional[FunctionalCalcConfig] = Field(None, alias="functionalCalc")
    status_eval: Optional[StatusEvalConfig] = Field(None, alias="statusEval")


class ReportConfig(BaseModel):
    """完整的报表配置模型"""
    source_file_id: str = Field(..., alias="sourceFileId", description="源文件ID")
    report_config: ReportConfigData = Field(..., alias="reportConfig", description="报表配置数据")
    
    class Config:
        allow_population_by_field_name = True
