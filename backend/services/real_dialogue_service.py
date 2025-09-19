"""
Real implementations of dialogue service interfaces for Phase 3
实现真实的对话服务，包括状态机管理、LLM集成等
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import uuid
from enum import Enum
import logging
import re

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from interfaces.dialogue_interfaces import DialogueManager, NluProcessor, RuleProvider
from models.api_models import DialogueRequest, DialogueResponse, DialogueState
from models.report_config import ReportConfig, ReportConfigData, StableStateConfig, FunctionalCalcConfig, StatusEvalConfig


class DialogueStage(Enum):
    """对话阶段枚举"""
    INITIAL = "initial"                    # 初始阶段
    FILE_CONFIRMATION = "file_confirmation" # 文件确认阶段
    REPORT_TYPE_SELECTION = "report_type_selection"  # 报表类型选择
    STABLE_STATE_CONFIG = "stable_state_config"      # 稳定状态配置
    FUNCTIONAL_CONFIG = "functional_config"          # 功能计算配置
    STATUS_EVAL_CONFIG = "status_eval_config"        # 状态评估配置
    CONFIGURATION_REVIEW = "configuration_review"    # 配置审查
    REPORT_GENERATION = "report_generation"          # 报表生成
    COMPLETED = "completed"                          # 完成


class SessionState:
    """会话状态管理"""
    def __init__(self, session_id: str, file_id: Optional[str] = None):
        self.session_id = session_id
        self.file_id = file_id
        self.stage = DialogueStage.INITIAL
        self.config_data = {}
        self.available_channels = []
        self.conversation_history = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.user_preferences = {}
        self.current_section = None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "file_id": self.file_id,
            "stage": self.stage.value,
            "config_data": self.config_data,
            "available_channels": self.available_channels,
            "conversation_history": self.conversation_history,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "user_preferences": self.user_preferences,
            "current_section": self.current_section
        }


class RealRuleProvider(RuleProvider):
    """真实的规则提供者实现"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rules_cache = {}
        self._load_default_rules()
    
    def _load_default_rules(self):
        """加载默认规则"""
        self.rules_cache = {
            "report_templates": {
                "standard": {
                    "sections": ["stableState", "functionalCalc", "statusEval"],
                    "description": "标准报表，包含所有分析部分"
                },
                "simple": {
                    "sections": ["stableState"],
                    "description": "简单报表，仅包含稳定状态分析"
                },
                "functional_only": {
                    "sections": ["functionalCalc"],
                    "description": "功能分析报表"
                }
            },
            "configuration_rules": {
                "stableState": {
                    "required_fields": ["displayChannels", "condition"],
                    "optional_fields": ["conditionLogic", "conditions"],
                    "validation_rules": {
                        "displayChannels": {"type": "list", "min_length": 1},
                        "condition": {"type": "object", "required_fields": ["channel", "logic", "threshold"]}
                    }
                },
                "functionalCalc": {
                    "optional_fields": ["time_base", "startup_time", "ignition_time", "rundown_ng", "rundown_np"],
                    "validation_rules": {
                        "time_base": {"type": "object", "fields": ["channel", "statistic", "logic", "threshold"]},
                        "ignition_time": {"type": "object", "fields": ["channel", "type", "logic", "threshold"]}
                    }
                },
                "statusEval": {
                    "required_fields": ["evaluations"],
                    "validation_rules": {
                        "evaluations": {"type": "list", "min_length": 1}
                    }
                }
            },
            "default_parameters": {
                "stableState": {
                    "condition": {
                        "statistic": "平均值",
                        "duration": 1.0,
                        "logic": ">",
                        "threshold": 10000
                    }
                },
                "functionalCalc": {
                    "time_base": {
                        "statistic": "平均值",
                        "duration": 1.0,
                        "logic": ">",
                        "threshold": 500
                    }
                },
                "statusEval": {
                    "evaluation_template": {
                        "type": "continuous_check",
                        "logic": "<",
                        "threshold": 850
                    }
                }
            }
        }
    
    def get_report_template(self, report_type: str) -> Dict[str, Any]:
        """获取报表模板"""
        templates = self.rules_cache.get("report_templates", {})
        if report_type not in templates:
            report_type = "standard"  # 默认模板
        return templates.get(report_type, {})
    
    def get_configuration_rules(self, section: str) -> Dict[str, Any]:
        """获取配置规则"""
        rules = self.rules_cache.get("configuration_rules", {})
        return rules.get(section, {})
    
    def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """验证配置是否符合规则"""
        try:
            for section_name, section_config in config.items():
                rules = self.get_configuration_rules(section_name)
                if not self._validate_section(section_config, rules):
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Configuration validation error: {e}")
            return False
    
    def _validate_section(self, config: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """验证单个配置部分"""
        # 检查必需字段
        required_fields = rules.get("required_fields", [])
        for field in required_fields:
            if field not in config:
                return False
        
        # 检查验证规则
        validation_rules = rules.get("validation_rules", {})
        for field, rule in validation_rules.items():
            if field in config:
                if not self._validate_field(config[field], rule):
                    return False
        
        return True
    
    def _validate_field(self, value: Any, rule: Dict[str, Any]) -> bool:
        """验证单个字段"""
        field_type = rule.get("type")
        
        if field_type == "list":
            if not isinstance(value, list):
                return False
            min_length = rule.get("min_length", 0)
            if len(value) < min_length:
                return False
        
        elif field_type == "object":
            if not isinstance(value, dict):
                return False
            required_fields = rule.get("required_fields", [])
            for field in required_fields:
                if field not in value:
                    return False
        
        return True
    
    def get_default_parameters(self, report_section: str) -> Dict[str, Any]:
        """获取默认参数"""
        defaults = self.rules_cache.get("default_parameters", {})
        return defaults.get(report_section, {})


class RealNluProcessor(NluProcessor):
    """真实的NLU处理器实现"""
    
    def __init__(self, llm_api_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.llm_api_key = llm_api_key
        self.use_llm = llm_api_key is not None
        
        # 预定义的意图模式
        self.intent_patterns = {
            "greeting": [r"你好", r"hello", r"hi", r"开始", r"开始生成"],
            "file_upload": [r"上传", r"文件", r"数据", r"导入"],
            "report_type": [r"报表", r"类型", r"标准", r"简单", r"功能"],
            "stable_state": [r"稳定", r"状态", r"稳态", r"平均值", r"阈值"],
            "functional_calc": [r"功能", r"计算", r"时间", r"点火", r"余转"],
            "status_eval": [r"评估", r"状态", r"超温", r"超转", r"异常"],
            "confirmation": [r"确认", r"是的", r"对", r"好的", r"继续"],
            "negation": [r"不", r"否", r"取消", r"重新"],
            "completion": [r"完成", r"生成", r"结束", r"好了"]
        }
    
    def process_text(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户输入的自然语言文本"""
        try:
            # 清理输入文本
            cleaned_text = text.strip()
            
            # 分类意图
            intent = self.classify_intent(cleaned_text)
            
            # 提取参数
            parameters = self.extract_parameters(cleaned_text, context.get("parameter_schema", {}))
            
            # 提取实体
            entities = self._extract_entities(cleaned_text)
            
            # 计算置信度
            confidence = self._calculate_confidence(cleaned_text, intent)
            
            return {
                "intent": intent,
                "parameters": parameters,
                "entities": entities,
                "confidence": confidence,
                "processed_text": cleaned_text
            }
            
        except Exception as e:
            self.logger.error(f"Text processing error: {e}")
            return {
                "intent": "unknown",
                "parameters": {},
                "entities": [],
                "confidence": 0.0,
                "error": str(e)
            }
    
    def extract_parameters(self, text: str, parameter_schema: Dict[str, Any]) -> Dict[str, Any]:
        """从文本中提取特定参数"""
        parameters = {}
        text_lower = text.lower()
        
        # 提取数值参数
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            # 根据上下文确定数值的含义
            if "阈值" in text_lower or "threshold" in text_lower:
                parameters["threshold"] = float(numbers[0])
            elif "时间" in text_lower or "duration" in text_lower:
                parameters["duration"] = float(numbers[0])
        
        # 提取通道名称
        channel_patterns = [r'ng\(rpm\)', r'np\(rpm\)', r'temperature', r'pressure', r'温度', r'压力', r'转速']
        for pattern in channel_patterns:
            if re.search(pattern, text_lower):
                if "channel" not in parameters:
                    parameters["channels"] = []
                parameters["channels"].append(pattern)
        
        # 提取逻辑操作符
        if "大于" in text_lower or ">" in text:
            parameters["logic"] = ">"
        elif "小于" in text_lower or "<" in text:
            parameters["logic"] = "<"
        elif "等于" in text_lower or "=" in text:
            parameters["logic"] = "="
        
        # 提取统计量类型
        if "平均值" in text_lower or "平均" in text_lower:
            parameters["statistic"] = "平均值"
        elif "最大值" in text_lower or "最大" in text_lower:
            parameters["statistic"] = "最大值"
        elif "最小值" in text_lower or "最小" in text_lower:
            parameters["statistic"] = "最小值"
        
        return parameters
    
    def classify_intent(self, text: str) -> str:
        """分类用户意图"""
        text_lower = text.lower()
        
        # 使用模式匹配进行意图识别
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        # 如果没有匹配的模式，返回unknown
        return "unknown"
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """提取命名实体"""
        entities = []
        text_lower = text.lower()
        
        # 提取数值实体
        numbers = re.finditer(r'\d+\.?\d*', text)
        for match in numbers:
            entities.append({
                "type": "NUMBER",
                "value": float(match.group()),
                "start": match.start(),
                "end": match.end()
            })
        
        # 提取通道实体
        channel_patterns = {
            r'ng\(rpm\)|ng转速': "Ng(rpm)",
            r'np\(rpm\)|np转速': "Np(rpm)", 
            r'temperature|温度|排气温度': "Temperature(°C)",
            r'pressure|压力|滑油压力': "Pressure(kPa)"
        }
        
        for pattern, standard_name in channel_patterns.items():
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                entities.append({
                    "type": "CHANNEL",
                    "value": standard_name,
                    "start": match.start(),
                    "end": match.end()
                })
        
        return entities
    
    def _calculate_confidence(self, text: str, intent: str) -> float:
        """计算置信度"""
        if intent == "unknown":
            return 0.1
        
        # 基于匹配模式的数量和文本长度计算置信度
        patterns = self.intent_patterns.get(intent, [])
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text.lower()):
                matches += 1
        
        # 基础置信度
        base_confidence = min(0.9, 0.3 + (matches * 0.2))
        
        # 根据文本长度调整
        text_length_factor = min(1.0, len(text) / 50)
        
        return min(0.95, base_confidence * (0.5 + text_length_factor * 0.5))


class RealDialogueManager(DialogueManager):
    """真实的对话管理器实现"""
    
    def __init__(self, nlu_processor: NluProcessor = None, rule_provider: RuleProvider = None):
        self.logger = logging.getLogger(__name__)
        self.nlu_processor = nlu_processor or RealNluProcessor()
        self.rule_provider = rule_provider or RealRuleProvider()
        
        # 会话存储
        self.sessions: Dict[str, SessionState] = {}
        
        # 状态机转换规则
        self.state_transitions = {
            DialogueStage.INITIAL: [DialogueStage.FILE_CONFIRMATION],
            DialogueStage.FILE_CONFIRMATION: [DialogueStage.REPORT_TYPE_SELECTION],
            DialogueStage.REPORT_TYPE_SELECTION: [DialogueStage.STABLE_STATE_CONFIG, DialogueStage.FUNCTIONAL_CONFIG, DialogueStage.STATUS_EVAL_CONFIG],
            DialogueStage.STABLE_STATE_CONFIG: [DialogueStage.FUNCTIONAL_CONFIG, DialogueStage.STATUS_EVAL_CONFIG, DialogueStage.CONFIGURATION_REVIEW],
            DialogueStage.FUNCTIONAL_CONFIG: [DialogueStage.STATUS_EVAL_CONFIG, DialogueStage.CONFIGURATION_REVIEW],
            DialogueStage.STATUS_EVAL_CONFIG: [DialogueStage.CONFIGURATION_REVIEW],
            DialogueStage.CONFIGURATION_REVIEW: [DialogueStage.REPORT_GENERATION],
            DialogueStage.REPORT_GENERATION: [DialogueStage.COMPLETED],
            DialogueStage.COMPLETED: []
        }
    
    def process(self, user_request: DialogueRequest) -> DialogueResponse:
        """处理用户对话请求"""
        try:
            session_id = user_request.session_id
            user_input = user_request.user_input
            
            # 获取或创建会话
            session = self._get_or_create_session(session_id, user_request.file_id)
            
            # 更新活动时间
            session.last_activity = datetime.now()
            
            # 处理用户输入
            nlu_result = self.nlu_processor.process_text(user_input, {
                "stage": session.stage.value,
                "config_data": session.config_data,
                "available_channels": session.available_channels
            })
            
            # 记录对话历史
            session.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "nlu_result": nlu_result
            })
            
            # 根据当前状态和NLU结果生成响应
            ai_response, new_stage, config_updates = self._generate_response(session, nlu_result)
            
            # 更新会话状态
            if new_stage:
                session.stage = new_stage
            
            if config_updates:
                session.config_data.update(config_updates)
            
            # 记录AI响应
            session.conversation_history[-1]["ai_response"] = ai_response
            session.conversation_history[-1]["new_stage"] = new_stage.value if new_stage else None
            
            # 判断是否完成配置
            is_complete = session.stage == DialogueStage.COMPLETED
            report_url = None
            
            if is_complete:
                # 生成最终配置
                try:
                    final_config = self.finalize_configuration(session_id)
                    report_url = f"/api/reports/generate"  # 这里应该调用实际的报表生成API
                except Exception as e:
                    self.logger.error(f"Failed to finalize configuration: {e}")
                    is_complete = False
                    ai_response += f" 配置生成时发生错误：{str(e)}"
            
            # 将内部DialogueStage映射到API DialogueState
            api_state = self._map_stage_to_state(session.stage)
            
            return DialogueResponse(
                session_id=session_id,
                ai_response=ai_response,
                dialogue_state=api_state,
                suggested_actions=self._get_suggested_actions(session.stage),
                is_complete=is_complete,
                report_url=report_url,
                error_message=None
            )
            
        except Exception as e:
            self.logger.error(f"Dialogue processing error: {e}")
            return DialogueResponse(
                session_id=user_request.session_id,
                ai_response=f"抱歉，处理您的请求时发生了错误：{str(e)}",
                dialogue_state=DialogueState.ERROR,
                suggested_actions=["请重新开始对话"],
                is_complete=False,
                report_url=None,
                error_message=str(e)
            )
    
    def _get_or_create_session(self, session_id: str, file_id: Optional[str] = None) -> SessionState:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id, file_id)
            self.logger.info(f"Created new session: {session_id}")
        
        session = self.sessions[session_id]
        
        # 如果提供了新的file_id，更新会话
        if file_id and session.file_id != file_id:
            session.file_id = file_id
            # 这里可以调用数据服务获取可用通道
            session.available_channels = self._get_available_channels(file_id)
        
        return session
    
    def _get_available_channels(self, file_id: str) -> List[str]:
        """获取文件的可用通道（模拟实现）"""
        # 这里应该调用实际的数据服务
        return ["Ng(rpm)", "Np(rpm)", "Temperature(°C)", "Pressure(kPa)"]
    
    def _generate_response(self, session: SessionState, nlu_result: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """根据会话状态和NLU结果生成响应"""
        current_stage = session.stage
        intent = nlu_result.get("intent", "unknown")
        parameters = nlu_result.get("parameters", {})
        
        if current_stage == DialogueStage.INITIAL:
            return self._handle_initial_stage(session, intent, parameters)
        elif current_stage == DialogueStage.FILE_CONFIRMATION:
            return self._handle_file_confirmation(session, intent, parameters)
        elif current_stage == DialogueStage.REPORT_TYPE_SELECTION:
            return self._handle_report_type_selection(session, intent, parameters)
        elif current_stage == DialogueStage.STABLE_STATE_CONFIG:
            return self._handle_stable_state_config(session, intent, parameters)
        elif current_stage == DialogueStage.FUNCTIONAL_CONFIG:
            return self._handle_functional_config(session, intent, parameters)
        elif current_stage == DialogueStage.STATUS_EVAL_CONFIG:
            return self._handle_status_eval_config(session, intent, parameters)
        elif current_stage == DialogueStage.CONFIGURATION_REVIEW:
            return self._handle_configuration_review(session, intent, parameters)
        else:
            return "我不确定如何处理当前状态，请重新开始。", DialogueStage.INITIAL, {}
    
    def _handle_initial_stage(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理初始阶段"""
        if session.file_id:
            # 如果用户提到"上传"或"文件"，直接跳到报表类型选择
            response = f"文件上传成功！我已经检测到 {len(session.available_channels)} 个数据通道。\n\n"
            response += "现在，请选择您需要生成的报表类型：\n\n"
            response += "1. **稳态分析报表** - 分析稳定状态下的参数\n"
            response += "2. **功能计算报表** - 计算时间基准、启动时间等功能指标\n"
            response += "3. **状态评估报表** - 评估超温、超转等状态\n"
            response += "4. **完整分析报表** - 包含以上所有分析内容\n"
            return response, DialogueStage.REPORT_TYPE_SELECTION, {}
        else:
            response = "您好！欢迎使用AI报表生成系统。请先上传您的数据文件，然后我们可以开始配置报表。"
            return response, None, {}
    
    def _handle_file_confirmation(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理文件确认阶段"""
        if intent == "confirmation":
            response = "很好！现在让我们选择报表类型。您希望生成哪种类型的报表？\n\n"
            response += "1. 标准报表 - 包含稳定状态、功能计算和状态评估\n"
            response += "2. 简单报表 - 仅包含稳定状态分析\n"
            response += "3. 功能分析报表 - 专注于功能计算分析\n\n"
            response += "请选择一个选项（1、2或3），或者告诉我您的具体需求。"
            return response, DialogueStage.REPORT_TYPE_SELECTION, {}
        else:
            response = "请确认文件是否正确。如果需要重新上传文件，请在文件上传区域选择新文件。"
            return response, None, {}
    
    def _handle_report_type_selection(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理报表类型选择"""
        # 简化实现：默认选择标准报表
        config_updates = {"sections": ["stableState", "functionalCalc", "statusEval"]}
        session.current_section = "stableState"
        
        response = "好的！我们将生成标准报表。现在让我们配置稳定状态分析。\n\n"
        response += "稳定状态分析用于识别数据中的稳定工况期间。请告诉我：\n"
        response += "1. 您希望分析哪些通道？\n"
        response += "2. 稳定状态的判定条件是什么？\n\n"
        response += f"可用通道：{', '.join(session.available_channels)}"
        
        return response, DialogueStage.STABLE_STATE_CONFIG, config_updates
    
    def _handle_stable_state_config(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理稳定状态配置"""
        # 简化实现：使用默认配置
        config_updates = {
            "stableState": {
                "displayChannels": session.available_channels[:2],  # 取前两个通道
                "condition": {
                    "channel": session.available_channels[0] if session.available_channels else "Ng(rpm)",
                    "statistic": "平均值",
                    "duration": 1.0,
                    "logic": ">",
                    "threshold": parameters.get("threshold", 10000)
                }
            }
        }
        
        session.current_section = "functionalCalc"
        
        response = "稳定状态配置完成！现在让我们配置功能计算分析。\n\n"
        response += "功能计算包括：\n"
        response += "- 时间基准计算\n"
        response += "- 启动时间分析\n"
        response += "- 点火时间检测\n"
        response += "- 余转时间计算\n\n"
        response += "您希望配置哪些功能计算项目？或者使用默认配置？"
        
        return response, DialogueStage.FUNCTIONAL_CONFIG, config_updates
    
    def _handle_functional_config(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理功能计算配置"""
        # 简化实现：使用默认配置
        config_updates = {
            "functionalCalc": {
                "time_base": {
                    "channel": "Pressure(kPa)",
                    "statistic": "平均值",
                    "duration": 1.0,
                    "logic": ">",
                    "threshold": 500
                },
                "ignition_time": {
                    "channel": "Temperature(°C)",
                    "type": "difference",
                    "duration": 10.0,
                    "logic": ">",
                    "threshold": 50
                }
            }
        }
        
        session.current_section = "statusEval"
        
        response = "功能计算配置完成！最后让我们配置状态评估。\n\n"
        response += "状态评估用于检测异常情况，如：\n"
        response += "- 超温检测\n"
        response += "- 超转检测\n"
        response += "- 压力异常\n\n"
        response += "您希望配置哪些状态评估项目？"
        
        return response, DialogueStage.STATUS_EVAL_CONFIG, config_updates
    
    def _handle_status_eval_config(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理状态评估配置"""
        # 简化实现：使用默认配置
        config_updates = {
            "statusEval": {
                "evaluations": [
                    {
                        "item": "超温评估",
                        "channel": "Temperature(°C)",
                        "logic": "<",
                        "threshold": 850
                    },
                    {
                        "item": "超转评估", 
                        "channel": "Ng(rpm)",
                        "logic": "<",
                        "threshold": 18000
                    }
                ]
            }
        }
        
        response = "配置完成！让我总结一下您的报表配置：\n\n"
        response += self._generate_config_summary_text(session.config_data, config_updates)
        response += "\n\n请确认配置是否正确？确认后我将开始生成报表。"
        
        return response, DialogueStage.CONFIGURATION_REVIEW, config_updates
    
    def _handle_configuration_review(self, session: SessionState, intent: str, parameters: Dict[str, Any]) -> Tuple[str, Optional[DialogueStage], Dict[str, Any]]:
        """处理配置审查"""
        if intent == "confirmation":
            response = "配置确认！正在生成报表，请稍候..."
            return response, DialogueStage.COMPLETED, {}
        else:
            response = "请确认配置，或者告诉我需要修改哪个部分。"
            return response, None, {}
    
    def _generate_config_summary_text(self, base_config: Dict[str, Any], updates: Dict[str, Any]) -> str:
        """生成配置摘要文本"""
        merged_config = {**base_config, **updates}
        
        summary = "📋 报表配置摘要：\n"
        
        if "sections" in merged_config:
            summary += f"报表类型：{', '.join(merged_config['sections'])}\n"
        
        if "stableState" in merged_config:
            stable = merged_config["stableState"]
            summary += f"稳定状态分析：{', '.join(stable.get('displayChannels', []))}\n"
        
        if "functionalCalc" in merged_config:
            summary += "功能计算：时间基准、点火时间等\n"
        
        if "statusEval" in merged_config:
            evals = merged_config["statusEval"].get("evaluations", [])
            eval_items = [e.get("item", "未知") for e in evals]
            summary += f"状态评估：{', '.join(eval_items)}\n"
        
        return summary
    
    def _map_stage_to_state(self, stage: DialogueStage) -> DialogueState:
        """将内部DialogueStage映射到API DialogueState"""
        stage_to_state = {
            DialogueStage.INITIAL: DialogueState.INITIAL,
            DialogueStage.FILE_CONFIRMATION: DialogueState.FILE_UPLOADED,
            DialogueStage.REPORT_TYPE_SELECTION: DialogueState.FILE_UPLOADED,
            DialogueStage.STABLE_STATE_CONFIG: DialogueState.CONFIGURING,
            DialogueStage.FUNCTIONAL_CONFIG: DialogueState.CONFIGURING,
            DialogueStage.STATUS_EVAL_CONFIG: DialogueState.CONFIGURING,
            DialogueStage.CONFIGURATION_REVIEW: DialogueState.CONFIGURING,
            DialogueStage.REPORT_GENERATION: DialogueState.GENERATING,
            DialogueStage.COMPLETED: DialogueState.COMPLETED
        }
        return stage_to_state.get(stage, DialogueState.INITIAL)
    
    def _calculate_progress(self, stage: DialogueStage) -> float:
        """计算对话进度"""
        stage_progress = {
            DialogueStage.INITIAL: 0.0,
            DialogueStage.FILE_CONFIRMATION: 0.1,
            DialogueStage.REPORT_TYPE_SELECTION: 0.2,
            DialogueStage.STABLE_STATE_CONFIG: 0.4,
            DialogueStage.FUNCTIONAL_CONFIG: 0.6,
            DialogueStage.STATUS_EVAL_CONFIG: 0.8,
            DialogueStage.CONFIGURATION_REVIEW: 0.9,
            DialogueStage.REPORT_GENERATION: 0.95,
            DialogueStage.COMPLETED: 1.0
        }
        return stage_progress.get(stage, 0.0)
    
    def _generate_config_summary(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成配置摘要"""
        return {
            "sections": config_data.get("sections", []),
            "stable_state_configured": "stableState" in config_data,
            "functional_calc_configured": "functionalCalc" in config_data,
            "status_eval_configured": "statusEval" in config_data
        }
    
    def _get_suggested_actions(self, stage: DialogueStage) -> List[str]:
        """获取建议操作"""
        suggestions = {
            DialogueStage.INITIAL: ["上传CSV文件", "上传Excel文件"],
            DialogueStage.FILE_CONFIRMATION: ["确认文件", "重新上传"],
            DialogueStage.REPORT_TYPE_SELECTION: [
                "生成稳态分析报表", 
                "生成功能计算报表", 
                "生成状态评估报表",
                "生成完整分析报表",
                "生成其他报表类型(.json)"
            ],
            DialogueStage.STABLE_STATE_CONFIG: ["使用 Ng(rpm)", "使用 Temperature(°C)", "使用 Pressure(kPa)", "自定义通道"],
            DialogueStage.FUNCTIONAL_CONFIG: ["全部指标", "时间基准+启动时间", "自定义选择"],
            DialogueStage.STATUS_EVAL_CONFIG: ["添加超温检测", "添加超转检测", "全部检测"],
            DialogueStage.CONFIGURATION_REVIEW: ["确认生成", "修改配置", "取消"],
            DialogueStage.COMPLETED: ["下载报表", "开始新会话"]
        }
        return suggestions.get(stage, ["继续对话"])
    
    def initialize_session(self, session_id: str, file_id: Optional[str] = None) -> Dict[str, Any]:
        """初始化对话会话"""
        session = SessionState(session_id, file_id)
        if file_id:
            session.available_channels = self._get_available_channels(file_id)
        
        self.sessions[session_id] = session
        
        return session.to_dict()
    
    def update_configuration(self, session_id: str, config_updates: Dict[str, Any]) -> bool:
        """更新配置信息"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.config_data.update(config_updates)
        session.last_activity = datetime.now()
        
        return True
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        if session_id not in self.sessions:
            return {}
        
        return self.sessions[session_id].to_dict()
    
    def generate_ai_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """生成AI回复"""
        # 这是一个简化的实现，实际应该更智能
        return f"我理解您的输入：{user_input}。让我来帮助您配置报表。"
    
    def finalize_configuration(self, session_id: str) -> ReportConfig:
        """完成配置并返回最终配置对象"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        config_data = session.config_data
        
        # 构建ReportConfig对象
        sections = config_data.get("sections", ["stableState"])
        
        # 构建稳定状态配置
        stable_state = None
        if "stableState" in sections and "stableState" in config_data:
            stable_config = config_data["stableState"]
            stable_state = StableStateConfig(
                displayChannels=stable_config.get("displayChannels", []),
                condition=stable_config.get("condition")
            )
        
        # 构建功能计算配置
        functional_calc = None
        if "functionalCalc" in sections and "functionalCalc" in config_data:
            functional_calc = FunctionalCalcConfig(**config_data["functionalCalc"])
        
        # 构建状态评估配置
        status_eval = None
        if "statusEval" in sections and "statusEval" in config_data:
            status_eval = StatusEvalConfig(**config_data["statusEval"])
        
        report_config_data = ReportConfigData(
            sections=sections,
            stableState=stable_state,
            functionalCalc=functional_calc,
            statusEval=status_eval
        )
        
        return ReportConfig(
            sourceFileId=session.file_id or "unknown",
            reportConfig=report_config_data
        )

