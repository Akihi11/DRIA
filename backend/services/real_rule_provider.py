"""
Real Rule Provider Implementation
实现从配置文件读取报表规则的功能
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Add parent directory to path for imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from interfaces.dialogue_interfaces import RuleProvider
from models.report_config import ReportConfig

logger = logging.getLogger(__name__)

class RealRuleProvider(RuleProvider):
    """实际的规则提供者实现"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化规则提供者
        
        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir)
        self.rules_cache = {}
        self.templates_cache = {}
        
        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则配置"""
        try:
            # 创建默认的报表规则模板
            default_rules = {
                "stable_state_rules": {
                    "description": "稳态分析规则",
                    "default_channels": ["Ng(rpm)", "Np(rpm)", "Temperature(°C)", "Pressure(kPa)"],
                    "condition_templates": [
                        {
                            "name": "高转速稳态",
                            "type": "statistic",
                            "channel": "Ng(rpm)",
                            "statistic": "平均值",
                            "duration": 0.1,
                            "logic": ">",
                            "threshold": 14000
                        },
                        {
                            "name": "低振幅变化",
                            "type": "amplitude_change",
                            "channel": "Ng(rpm)",
                            "duration": 0.5,
                            "logic": "<",
                            "threshold": 200
                        }
                    ]
                },
                "functional_calc_rules": {
                    "description": "功能计算规则",
                    "time_base_template": {
                        "channel": "Pressure(kPa)",
                        "statistic": "平均值",
                        "duration": 0.1,
                        "logic": ">",
                        "threshold": 500
                    },
                    "startup_time_template": {
                        "channel": "Pressure(kPa)",
                        "statistic": "平均值",
                        "duration": 0.1,
                        "logic": ">",
                        "threshold": 1000
                    },
                    "ignition_time_template": {
                        "channel": "Temperature(°C)",
                        "type": "difference",
                        "duration": 0.2,
                        "logic": "突变>",
                        "threshold": 50
                    },
                    "rundown_templates": {
                        "ng": {
                            "channel": "Ng(rpm)",
                            "statistic": "平均值",
                            "duration": 0.1,
                            "threshold1": 13000,
                            "threshold2": 8000
                        },
                        "np": {
                            "channel": "Np(rpm)",
                            "statistic": "平均值",
                            "duration": 0.1,
                            "threshold1": 10000,
                            "threshold2": 6000
                        }
                    }
                },
                "status_eval_rules": {
                    "description": "状态评估规则",
                    "evaluation_templates": [
                        {
                            "item": "超温评估",
                            "type": "continuous_check",
                            "condition": {
                                "channel": "Temperature(°C)",
                                "statistic": "瞬时值",
                                "logic": "<",
                                "threshold": 850
                            }
                        },
                        {
                            "item": "超转评估",
                            "type": "continuous_check",
                            "condition": {
                                "channel": "Ng(rpm)",
                                "statistic": "瞬时值",
                                "logic": "<",
                                "threshold": 18000
                            }
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
            
            # 保存默认规则到文件
            rules_file = self.config_dir / "default_rules.json"
            if not rules_file.exists():
                with open(rules_file, 'w', encoding='utf-8') as f:
                    json.dump(default_rules, f, indent=2, ensure_ascii=False)
                logger.info(f"Created default rules file: {rules_file}")
            
            self.rules_cache['default'] = default_rules
            
        except Exception as e:
            logger.error(f"Failed to initialize default rules: {e}")
    
    def get_report_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        获取报表模板配置
        
        Args:
            template_name: 模板名称
            
        Returns:
            模板配置字典，如果未找到返回None
        """
        try:
            template_file = self.config_dir / f"{template_name}_template.json"
            
            if template_file.exists():
                with open(template_file, 'r', encoding='utf-8') as f:
                    template = json.load(f)
                self.templates_cache[template_name] = template
                return template
            
            # 如果没有找到模板文件，返回默认模板
            if template_name == "stable_state":
                return self._get_default_stable_state_template()
            elif template_name == "functional_calc":
                return self._get_default_functional_calc_template()
            elif template_name == "status_eval":
                return self._get_default_status_eval_template()
            
            logger.warning(f"Template not found: {template_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get template {template_name}: {e}")
            return None
    
    def get_rules_by_type(self, rule_type: str) -> List[Dict[str, Any]]:
        """
        根据类型获取规则列表
        
        Args:
            rule_type: 规则类型 (stable_state, functional_calc, status_eval)
            
        Returns:
            规则列表
        """
        try:
            if 'default' not in self.rules_cache:
                self._init_default_rules()
            
            rules = self.rules_cache.get('default', {})
            
            if rule_type == "stable_state":
                return rules.get("stable_state_rules", {}).get("condition_templates", [])
            elif rule_type == "functional_calc":
                return self._extract_functional_calc_rules(rules.get("functional_calc_rules", {}))
            elif rule_type == "status_eval":
                return rules.get("status_eval_rules", {}).get("evaluation_templates", [])
            
            logger.warning(f"Unknown rule type: {rule_type}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get rules by type {rule_type}: {e}")
            return []
    
    def get_channel_mappings(self, file_channels: List[str]) -> Dict[str, str]:
        """
        获取通道映射关系
        
        Args:
            file_channels: 文件中的通道列表
            
        Returns:
            通道映射字典 {标准通道名: 文件通道名}
        """
        try:
            # 标准通道名列表
            standard_channels = [
                "Ng(rpm)", "Np(rpm)", "Temperature(°C)", "Pressure(kPa)",
                "滑油压力", "排气温度", "燃气流量", "空气流量"
            ]
            
            channel_mapping = {}
            
            # 精确匹配
            for std_channel in standard_channels:
                if std_channel in file_channels:
                    channel_mapping[std_channel] = std_channel
                    continue
                
                # 模糊匹配
                for file_channel in file_channels:
                    if self._is_channel_match(std_channel, file_channel):
                        channel_mapping[std_channel] = file_channel
                        break
            
            logger.info(f"Channel mapping created: {len(channel_mapping)} mappings")
            return channel_mapping
            
        except Exception as e:
            logger.error(f"Failed to create channel mappings: {e}")
            return {}
    
    def create_config_from_intent(self, user_intent: str, available_channels: List[str]) -> Optional[ReportConfig]:
        """
        根据用户意图创建报表配置
        
        Args:
            user_intent: 用户意图描述
            available_channels: 可用通道列表
            
        Returns:
            生成的报表配置
        """
        try:
            # 分析用户意图
            intent_analysis = self._analyze_user_intent(user_intent)
            
            # 创建基础配置
            config_dict = {
                "sourceFileId": "user_intent_file",
                "reportConfig": {
                    "sections": intent_analysis["sections"]
                }
            }
            
            # 根据意图添加具体配置
            if "stableState" in intent_analysis["sections"]:
                config_dict["reportConfig"]["stableState"] = self._create_stable_state_config(
                    intent_analysis, available_channels
                )
            
            if "functionalCalc" in intent_analysis["sections"]:
                config_dict["reportConfig"]["functionalCalc"] = self._create_functional_calc_config(
                    intent_analysis, available_channels
                )
            
            if "statusEval" in intent_analysis["sections"]:
                config_dict["reportConfig"]["statusEval"] = self._create_status_eval_config(
                    intent_analysis, available_channels
                )
            
            # 创建ReportConfig对象
            return ReportConfig(**config_dict)
            
        except Exception as e:
            logger.error(f"Failed to create config from intent: {e}")
            return None
    
    def _analyze_user_intent(self, user_intent: str) -> Dict[str, Any]:
        """分析用户意图"""
        intent_lower = user_intent.lower()
        
        analysis = {
            "sections": [],
            "keywords": [],
            "analysis_type": "basic"
        }
        
        # 检测分析类型
        if any(keyword in intent_lower for keyword in ["稳态", "stable", "平稳"]):
            analysis["sections"].append("stableState")
            analysis["keywords"].append("stable_state")
        
        if any(keyword in intent_lower for keyword in ["功能", "计算", "时间", "functional", "time"]):
            analysis["sections"].append("functionalCalc")
            analysis["keywords"].append("functional_calc")
        
        if any(keyword in intent_lower for keyword in ["状态", "评估", "检查", "status", "evaluation"]):
            analysis["sections"].append("statusEval")
            analysis["keywords"].append("status_eval")
        
        # 如果没有明确指定，默认包含稳态分析
        if not analysis["sections"]:
            analysis["sections"] = ["stableState"]
        
        return analysis
    
    def _create_stable_state_config(self, intent_analysis: Dict[str, Any], available_channels: List[str]) -> Dict[str, Any]:
        """创建稳态分析配置"""
        # 选择最相关的通道
        selected_channels = self._select_relevant_channels(available_channels, ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"])
        
        config = {
            "displayChannels": selected_channels[:4],  # 最多4个通道
            "condition": {
                "channel": selected_channels[0] if selected_channels else "Ng(rpm)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 14000
            }
        }
        
        return config
    
    def _create_functional_calc_config(self, intent_analysis: Dict[str, Any], available_channels: List[str]) -> Dict[str, Any]:
        """创建功能计算配置"""
        config = {}
        
        # 时间基准
        if "Pressure(kPa)" in available_channels:
            config["time_base"] = {
                "channel": "Pressure(kPa)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 500
            }
        
        # 启动时间
        if "Pressure(kPa)" in available_channels:
            config["startup_time"] = {
                "channel": "Pressure(kPa)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 1000
            }
        
        # 点火时间
        if "Temperature(°C)" in available_channels:
            config["ignition_time"] = {
                "channel": "Temperature(°C)",
                "type": "difference",
                "duration": 0.2,
                "logic": "突变>",
                "threshold": 50
            }
        
        # 停车时间
        if "Ng(rpm)" in available_channels:
            config["rundown_ng"] = {
                "channel": "Ng(rpm)",
                "statistic": "平均值",
                "duration": 0.1,
                "threshold1": 13000,
                "threshold2": 8000
            }
        
        return config
    
    def _create_status_eval_config(self, intent_analysis: Dict[str, Any], available_channels: List[str]) -> Dict[str, Any]:
        """创建状态评估配置"""
        evaluations = []
        
        # 超温评估
        if "Temperature(°C)" in available_channels:
            evaluations.append({
                "item": "超温评估",
                "type": "continuous_check",
                "condition": {
                    "channel": "Temperature(°C)",
                    "statistic": "瞬时值",
                    "logic": "<",
                    "threshold": 850
                }
            })
        
        # 超转评估
        if "Ng(rpm)" in available_channels:
            evaluations.append({
                "item": "超转评估",
                "type": "continuous_check",
                "condition": {
                    "channel": "Ng(rpm)",
                    "statistic": "瞬时值",
                    "logic": "<",
                    "threshold": 18000
                }
            })
        
        return {"evaluations": evaluations}
    
    def _select_relevant_channels(self, available_channels: List[str], preferred_channels: List[str]) -> List[str]:
        """选择相关通道"""
        selected = []
        
        # 首先选择首选通道
        for pref_channel in preferred_channels:
            if pref_channel in available_channels:
                selected.append(pref_channel)
        
        # 然后添加其他可用通道
        for channel in available_channels:
            if channel not in selected and len(selected) < 6:
                selected.append(channel)
        
        return selected
    
    def _is_channel_match(self, std_channel: str, file_channel: str) -> bool:
        """检查通道是否匹配"""
        # 提取关键词
        std_keywords = self._extract_channel_keywords(std_channel)
        file_keywords = self._extract_channel_keywords(file_channel)
        
        # 检查关键词重叠
        return len(set(std_keywords) & set(file_keywords)) > 0
    
    def _extract_channel_keywords(self, channel: str) -> List[str]:
        """提取通道关键词"""
        keywords = []
        
        # 基本关键词映射
        keyword_map = {
            "Ng": ["ng", "气发转速", "燃气轮机"],
            "Np": ["np", "动力转速", "功率"],
            "Temperature": ["温度", "temp", "排气"],
            "Pressure": ["压力", "压强", "滑油"]
        }
        
        for key, values in keyword_map.items():
            if key.lower() in channel.lower():
                keywords.extend(values)
        
        return keywords
    
    def _get_default_stable_state_template(self) -> Dict[str, Any]:
        """获取默认稳态分析模板"""
        return {
            "displayChannels": ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"],
            "condition": {
                "channel": "Ng(rpm)",
                "statistic": "平均值",
                "duration": 0.1,
                "logic": ">",
                "threshold": 14000
            }
        }
    
    def _get_default_functional_calc_template(self) -> Dict[str, Any]:
        """获取默认功能计算模板"""
        return {
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
            }
        }
    
    def _get_default_status_eval_template(self) -> Dict[str, Any]:
        """获取默认状态评估模板"""
        return {
            "evaluations": [
                {
                    "item": "超温评估",
                    "type": "continuous_check",
                    "condition": {
                        "channel": "Temperature(°C)",
                        "statistic": "瞬时值",
                        "logic": "<",
                        "threshold": 850
                    }
                }
            ]
        }
    
    def _extract_functional_calc_rules(self, rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取功能计算规则"""
        extracted_rules = []
        
        for key, value in rules.items():
            if key.endswith("_template") and isinstance(value, dict):
                extracted_rules.append({
                    "name": key.replace("_template", ""),
                    "config": value
                })
        
        return extracted_rules
