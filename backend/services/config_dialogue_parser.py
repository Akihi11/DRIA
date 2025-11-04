"""
配置对话解析服务 - 混合解析系统
"""
import re
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class ConfigDialogueParser:
    """配置对话解析器 - 混合解析系统"""
    
    def __init__(self):
        # 配置字段映射
        self.field_mappings = {
            # 转速通道相关
            "rpm_channel": {
                "keywords": ["转速", "ng", "rpm", "转数"],
                "enable_words": ["使用", "开启", "选择", "启用", "打开"],
                "disable_words": ["不用", "关闭", "取消", "禁用", "关闭"]
            },
            # 温度通道相关
            "temperature_channel": {
                "keywords": ["温度", "temperature", "°c", "摄氏度"],
                "enable_words": ["使用", "开启", "选择", "启用"],
                "disable_words": ["不用", "关闭", "取消", "禁用"]
            },
            # 压力通道相关
            "pressure_channel": {
                "keywords": ["压力", "pressure", "kpa", "帕"],
                "enable_words": ["使用", "开启", "选择", "启用"],
                "disable_words": ["不用", "关闭", "取消", "禁用"]
            },
            # 阈值相关
            "threshold": {
                "keywords": ["阈值", "门限", "临界值", "threshold"],
                "value_pattern": r'(\d+(?:\.\d+)?)'
            },
            # 转速类型相关（Ng/Np）
            "rpm_type": {
                "keywords": ["ng", "np", "转速", "高压转速", "低压转速"],
                "ng_words": ["ng", "低压", "低压转速"],
                "np_words": ["np", "高压", "高压转速"]
            },
            # 统计方法相关
            "statistical_method": {
                "keywords": ["统计", "方法", "计算", "统计方法"],
                "values": {
                    "平均值": ["平均", "均值", "mean", "average"],
                    "最大值": ["最大", "max", "maximum"],
                    "最小值": ["最小", "min", "minimum"],
                    "标准差": ["标准差", "std", "standard deviation"]
                }
            },
            # 时间窗口相关
            "time_window": {
                "keywords": ["时间", "窗口", "时间窗口", "time", "window"],
                "value_pattern": r'(\d+)',
                "units": {
                    "分钟": ["分钟", "min", "minute"],
                    "秒": ["秒", "sec", "second"],
                    "小时": ["小时", "hour", "h"]
                }
            }
        }
    
    def parse_user_intent(self, user_input: str, current_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        混合解析用户意图
        
        Args:
            user_input: 用户输入文本
            current_config: 当前配置参数
            
        Returns:
            解析结果字典，包含action、field、value等信息
        """
        user_input_lower = user_input.lower().strip()
        
        # 第一步：规则解析（快速、准确）
        parsed_action = self._rule_based_parser(user_input_lower, current_config)
        if parsed_action:
            logger.info(f"规则解析成功: {parsed_action}")
            return parsed_action
        
        # 第二步：AI解析（智能、灵活）
        # 这里可以调用LLM服务进行更复杂的解析
        ai_parsed = self._ai_based_parser(user_input_lower, current_config)
        if ai_parsed:
            logger.info(f"AI解析成功: {ai_parsed}")
            return ai_parsed
        
        logger.warning(f"无法解析用户输入: {user_input}")
        return None
    
    def _rule_based_parser(self, text: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """基于关键词的快速解析"""
        
        # 优先解析转速类型（避免包含“选择 Ng 转速通道”时只命中开启转速通道）
        rpm_type_result = self._parse_rpm_type(text)
        if rpm_type_result:
            return rpm_type_result

        # 解析转速通道
        rpm_result = self._parse_channel_config(text, "rpm_channel", "use_rpm_channel")
        if rpm_result:
            return rpm_result
        
        # 解析温度通道
        temp_result = self._parse_channel_config(text, "temperature_channel", "use_temperature_channel")
        if temp_result:
            return temp_result
        
        # 解析压力通道
        pressure_result = self._parse_channel_config(text, "pressure_channel", "use_pressure_channel")
        if pressure_result:
            return pressure_result
        
        # 解析阈值
        threshold_result = self._parse_threshold(text)
        if threshold_result:
            return threshold_result

        # 解析统计方法
        method_result = self._parse_statistical_method(text)
        if method_result:
            return method_result
        
        # 解析时间窗口
        time_result = self._parse_time_window(text)
        if time_result:
            return time_result
        
        # 解析确认/取消操作
        action_result = self._parse_action(text)
        if action_result:
            return action_result
        
        return None
    
    def _parse_channel_config(self, text: str, channel_type: str, field_name: str) -> Optional[Dict[str, Any]]:
        """解析通道配置"""
        channel_config = self.field_mappings[channel_type]
        
        # 检查是否包含通道关键词
        if not any(keyword in text for keyword in channel_config["keywords"]):
            return None
        
        # 检查启用/禁用关键词
        if any(word in text for word in channel_config["enable_words"]):
            return {
                "action": "update",
                "field": field_name,
                "value": True,
                "message": f"已为您选择{channel_config['keywords'][0]}通道"
            }
        elif any(word in text for word in channel_config["disable_words"]):
            return {
                "action": "update",
                "field": field_name,
                "value": False,
                "message": f"已为您取消{channel_config['keywords'][0]}通道"
            }
        
        return None

    def _parse_rpm_type(self, text: str) -> Optional[Dict[str, Any]]:
        """解析转速类型（Ng/Np）"""
        rpm_type_config = self.field_mappings["rpm_type"]
        if not any(keyword in text for keyword in rpm_type_config["keywords"]):
            return None

        is_ng = any(word in text for word in rpm_type_config["ng_words"])
        is_np = any(word in text for word in rpm_type_config["np_words"])

        if is_ng and not is_np:
            return {
                "action": "update",
                "field": "rpm_channel_type",
                "value": "Ng",
                "message": "已选择 Ng 转速通道"
            }
        if is_np and not is_ng:
            return {
                "action": "update",
                "field": "rpm_channel_type",
                "value": "Np",
                "message": "已选择 Np 转速通道"
            }
        return None
    
    def _parse_threshold(self, text: str) -> Optional[Dict[str, Any]]:
        """解析阈值设置"""
        threshold_config = self.field_mappings["threshold"]
        
        # 检查是否包含阈值关键词
        if not any(keyword in text for keyword in threshold_config["keywords"]):
            return None
        
        # 提取数值
        pattern = threshold_config["value_pattern"]
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            return {
                "action": "update",
                "field": "threshold",
                "value": value,
                "message": f"已将阈值修改为{value}"
            }
        
        return None
    
    def _parse_statistical_method(self, text: str) -> Optional[Dict[str, Any]]:
        """解析统计方法"""
        method_config = self.field_mappings["statistical_method"]
        
        # 检查是否包含统计方法关键词
        if not any(keyword in text for keyword in method_config["keywords"]):
            return None
        
        # 检查具体的方法值
        for method_name, keywords in method_config["values"].items():
            if any(keyword in text for keyword in keywords):
                return {
                    "action": "update",
                    "field": "statistical_method",
                    "value": method_name,
                    "message": f"已将统计方法修改为{method_name}"
                }
        
        return None
    
    def _parse_time_window(self, text: str) -> Optional[Dict[str, Any]]:
        """解析时间窗口"""
        time_config = self.field_mappings["time_window"]
        
        # 检查是否包含时间关键词
        if not any(keyword in text for keyword in time_config["keywords"]):
            return None
        
        # 提取数值
        pattern = time_config["value_pattern"]
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            
            # 检查单位
            unit = "分钟"  # 默认单位
            for unit_name, keywords in time_config["units"].items():
                if any(keyword in text for keyword in keywords):
                    unit = unit_name
                    break
            
            return {
                "action": "update",
                "field": "time_window",
                "value": value,
                "unit": unit,
                "message": f"已将时间窗口修改为{value}{unit}"
            }
        
        return None
    
    def _parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """解析操作指令"""
        # 确认操作
        confirm_words = ["确认", "完成", "好了", "可以", "确定", "ok", "yes"]
        if any(word in text for word in confirm_words):
            return {
                "action": "confirm",
                "message": "配置已确认，开始生成报表"
            }
        
        # 取消操作
        cancel_words = ["取消", "退出", "不要", "算了", "no", "cancel"]
        if any(word in text for word in cancel_words):
            return {
                "action": "cancel",
                "message": "已取消配置"
            }
        
        # 重置操作
        reset_words = ["重置", "重新", "reset", "重新开始"]
        if any(word in text for word in reset_words):
            return {
                "action": "reset",
                "message": "已重置配置"
            }
        
        return None
    
    def _ai_based_parser(self, text: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """基于AI的智能解析（预留接口）"""
        # 这里可以调用LLM服务进行更复杂的自然语言理解
        # 目前返回None，表示规则解析失败
        return None
    
    def get_suggested_actions(self, current_state: str, current_config: Dict[str, Any]) -> List[str]:
        """获取建议操作（根据当前状态与配置推断）"""
        suggestions: List[str] = []

        # 统一将状态名映射
        state = (current_state or "").lower()
        # 当状态为 configuring 或首次进入时，优先通道选择
        if state in ("configuring", "channel_selection", ""):
            suggestions.extend([
                "选择 Ng 转速通道",
                "选择 Np 转速通道",
                "选择温度通道",
                "选择压力通道",
            ])
            rpm_ok = current_config.get("use_rpm_channel") is True and current_config.get("rpm_channel_type") in ("Ng", "Np")
            if rpm_ok:
                suggestions.append("确认配置")
            else:
                suggestions.append("需先选择一个转速通道")
            suggestions.append("取消配置")
            return suggestions

        if state in ("confirming", "confirmation"):
            return ["确认配置", "取消配置"]

        # 参数阶段的通用建议
        suggestions.extend([
            "阈值改成15000",
            "使用平均值",
            "时间窗口改成5分钟",
            "确认配置",
            "取消配置"
        ])
        return suggestions

# 全局解析器实例
config_parser = ConfigDialogueParser()
