"""
Mock implementations of dialogue service interfaces for Phase 1 testing
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from interfaces.dialogue_interfaces import DialogueManager, NluProcessor, RuleProvider
from models.api_models import DialogueRequest, DialogueResponse, DialogueState
from models.report_config import ReportConfig


class MockNluProcessor(NluProcessor):
    """Mock implementation of NLU processor"""
    
    def process_text(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock natural language understanding"""
        
        text_lower = text.lower()
        
        # Simple keyword-based intent recognition
        intent = self.classify_intent(text)
        
        # Mock parameter extraction
        parameters = self.extract_parameters(text, {})
        
        return {
            "intent": intent,
            "parameters": parameters,
            "confidence": 0.85,  # Mock confidence score
            "entities": self._extract_entities(text_lower)
        }
    
    def extract_parameters(self, text: str, parameter_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Mock parameter extraction"""
        
        text_lower = text.lower()
        parameters = {}
        
        # Extract numeric values
        import re
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            parameters["threshold"] = float(numbers[0])
        
        # Extract channel names
        channels = ["ng", "temperature", "pressure", "fuel", "vibration"]
        for channel in channels:
            if channel in text_lower:
                parameters["channel"] = channel
                break
        
        # Extract time values
        if "秒" in text or "second" in text_lower:
            time_matches = re.findall(r'(\d+\.?\d*)\s*秒', text)
            if time_matches:
                parameters["duration"] = float(time_matches[0])
        
        return parameters
    
    def classify_intent(self, text: str) -> str:
        """Mock intent classification"""
        
        text_lower = text.lower()
        
        intent_keywords = {
            "configure_stable_state": ["稳定状态", "稳定", "stable"],
            "configure_functional": ["功能计算", "功能", "时间", "functional"],
            "configure_evaluation": ["状态评估", "评估", "evaluation"],
            "confirm_config": ["确认", "是的", "好的", "继续", "confirm", "yes"],
            "modify_config": ["修改", "更改", "调整", "modify", "change"],
            "upload_file": ["上传", "文件", "upload", "file"],
            "generate_report": ["生成", "报表", "generate", "report"]
        }
        
        for intent, keywords in intent_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent
        
        return "unknown"
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        
        entities = []
        
        # Mock entity extraction
        if "ng" in text or "转速" in text:
            entities.append({"type": "channel", "value": "Ng(rpm)", "confidence": 0.9})
        
        if "温度" in text or "temperature" in text:
            entities.append({"type": "channel", "value": "Temperature(°C)", "confidence": 0.9})
        
        return entities


class MockRuleProvider(RuleProvider):
    """Mock implementation of rule provider"""
    
    def __init__(self):
        # Mock rule templates
        self.templates = {
            "stableState": {
                "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
                "condition": {
                    "channel": "Ng(rpm)",
                    "statistic": "平均值",
                    "duration": 1.0,
                    "logic": ">",
                    "threshold": 15000
                }
            },
            "functionalCalc": {
                "time_base": {
                    "channel": "Pressure(kPa)",
                    "statistic": "平均值",
                    "duration": 1.0,
                    "logic": ">",
                    "threshold": 500
                },
                "startup_time": {
                    "channel": "Pressure(kPa)",
                    "statistic": "平均值", 
                    "duration": 1.0,
                    "logic": ">",
                    "threshold": 1000
                }
            },
            "statusEval": {
                "evaluations": [
                    {
                        "item": "超温",
                        "channel": "Temperature(°C)",
                        "logic": "<",
                        "threshold": 850
                    }
                ]
            }
        }
    
    def get_report_template(self, report_type: str) -> Dict[str, Any]:
        """Get report template"""
        
        return self.templates.get(report_type, {})
    
    def get_configuration_rules(self, section: str) -> Dict[str, Any]:
        """Get configuration rules for a section"""
        
        rules = {
            "stableState": {
                "required_fields": ["displayChannels", "condition"],
                "valid_statistics": ["最大值", "最小值", "平均值", "有效值"],
                "valid_logic": [">", "<"],
                "threshold_range": {"min": 0, "max": 20000}
            },
            "functionalCalc": {
                "available_metrics": ["time_base", "startup_time", "ignition_time", "rundown_ng"],
                "required_channels": ["Pressure(kPa)", "Temperature(°C)", "Ng(rpm)"]
            },
            "statusEval": {
                "evaluation_items": ["超温", "Ng余转时间", "压力异常", "振动异常"]
            }
        }
        
        return rules.get(section, {})
    
    def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate configuration against rules"""
        
        try:
            # Basic validation - in reality this would be more comprehensive
            if "sections" not in config:
                return False
            
            for section in config["sections"]:
                if section not in self.templates:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_default_parameters(self, report_section: str) -> Dict[str, Any]:
        """Get default parameters for a report section"""
        
        return self.templates.get(report_section, {})


class MockDialogueManager(DialogueManager):
    """Mock implementation of dialogue manager"""
    
    def __init__(self):
        self.nlu_processor = MockNluProcessor()
        self.rule_provider = MockRuleProvider()
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def process(self, user_request: DialogueRequest) -> DialogueResponse:
        """Process dialogue request"""
        
        try:
            # Initialize session if needed
            if user_request.session_id not in self.sessions:
                self.initialize_session(user_request.session_id, user_request.file_id)
            
            session = self.sessions[user_request.session_id]
            
            # Process user input with NLU
            nlu_result = self.nlu_processor.process_text(
                user_request.user_input,
                session
            )
            
            # Generate AI response
            ai_response = self.generate_ai_response(user_request.user_input, session)
            
            # Determine next state and quick choices
            new_state, quick_choices, is_complete, report_url = self._determine_next_state(
                user_request, session, nlu_result
            )
            
            # Update session
            session["state"] = new_state
            session["last_user_input"] = user_request.user_input
            session["last_nlu_result"] = nlu_result
            session["updated_at"] = datetime.now().isoformat()
            
            return DialogueResponse(
                session_id=user_request.session_id,
                ai_response=ai_response,
                quick_choices=quick_choices,
                dialogue_state=new_state,
                is_complete=is_complete,
                report_url=report_url
            )
            
        except Exception as e:
            return DialogueResponse(
                session_id=user_request.session_id,
                ai_response=f"处理请求时发生错误: {str(e)}",
                dialogue_state=DialogueState.ERROR,
                is_complete=False,
                error_message=str(e)
            )
    
    def initialize_session(self, session_id: str, file_id: Optional[str] = None) -> Dict[str, Any]:
        """Initialize dialogue session"""
        
        session_data = {
            "session_id": session_id,
            "file_id": file_id,
            "state": DialogueState.INITIAL,
            "config": {"sections": []},
            "message_history": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.sessions[session_id] = session_data
        return session_data
    
    def update_configuration(self, session_id: str, config_updates: Dict[str, Any]) -> bool:
        """Update configuration"""
        
        if session_id not in self.sessions:
            return False
        
        try:
            session = self.sessions[session_id]
            session["config"].update(config_updates)
            session["updated_at"] = datetime.now().isoformat()
            return True
            
        except Exception:
            return False
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """Get session state"""
        
        return self.sessions.get(session_id, {})
    
    def generate_ai_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """Generate AI response"""
        
        current_state = context.get("state", DialogueState.INITIAL)
        user_input_lower = user_input.lower()
        
        # Mock response generation based on state and input
        responses = {
            DialogueState.INITIAL: self._generate_initial_response(user_input_lower),
            DialogueState.FILE_UPLOADED: self._generate_file_uploaded_response(user_input_lower),
            DialogueState.CONFIGURING: self._generate_configuring_response(user_input_lower),
            DialogueState.CONFIRMING: self._generate_confirming_response(user_input_lower),
            DialogueState.COMPLETED: "感谢使用AI报表生成系统！如需生成新报表，请重新开始。"
        }
        
        return responses.get(current_state, "我不太明白您的意思，请您再详细说明一下。")
    
    def finalize_configuration(self, session_id: str) -> ReportConfig:
        """Finalize configuration"""
        
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        config_data = session["config"]
        
        # Create mock final configuration
        final_config = {
            "sourceFileId": session["file_id"] or "mock_file_id",
            "reportConfig": config_data
        }
        
        return ReportConfig(**final_config)
    
    def _determine_next_state(self, request: DialogueRequest, session: Dict[str, Any], nlu_result: Dict[str, Any]):
        """Determine next dialogue state"""
        
        current_state = DialogueState(request.dialogue_state)
        intent = nlu_result.get("intent", "unknown")
        
        # Mock state transitions
        if current_state == DialogueState.INITIAL:
            if intent == "upload_file":
                return DialogueState.FILE_UPLOADED, ["稳定状态报表", "功能计算报表", "全部报表"], False, None
            else:
                return DialogueState.INITIAL, ["上传文件"], False, None
        
        elif current_state == DialogueState.FILE_UPLOADED:
            if intent in ["configure_stable_state", "configure_functional", "configure_evaluation"]:
                return DialogueState.CONFIGURING, ["确认配置", "修改参数"], False, None
            else:
                return DialogueState.FILE_UPLOADED, ["稳定状态报表", "功能计算报表"], False, None
        
        elif current_state == DialogueState.CONFIGURING:
            if intent == "confirm_config":
                return DialogueState.CONFIRMING, ["生成报表", "修改配置"], False, None
            else:
                return DialogueState.CONFIGURING, ["确认配置", "重新设置"], False, None
        
        elif current_state == DialogueState.CONFIRMING:
            if intent == "generate_report":
                return DialogueState.COMPLETED, ["下载报表"], True, "/api/reports/download/mock_report.xlsx"
            else:
                return DialogueState.CONFIGURING, ["重新配置"], False, None
        
        return current_state, [], False, None
    
    def _generate_initial_response(self, user_input: str) -> str:
        """Generate initial state response"""
        return "欢迎使用AI报表生成系统！请先上传您的数据文件，然后我会引导您完成报表配置。"
    
    def _generate_file_uploaded_response(self, user_input: str) -> str:
        """Generate file uploaded state response"""
        return "文件上传成功！我检测到您的数据包含多个通道。请告诉我您希望生成什么类型的报表？"
    
    def _generate_configuring_response(self, user_input: str) -> str:
        """Generate configuring state response"""
        return "好的，让我帮您配置报表参数。根据您的需求，我建议使用以下配置..."
    
    def _generate_confirming_response(self, user_input: str) -> str:
        """Generate confirming state response"""
        return "配置已完成！请确认以下设置是否正确，然后我将为您生成报表。"
