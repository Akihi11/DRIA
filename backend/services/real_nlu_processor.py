"""
Real NLU Processor Implementation
实现自然语言理解处理器
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
import logging

# Add parent directory to path for imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from interfaces.dialogue_interfaces import NluProcessor
from models.api_models import DialogueRequest, DialogueResponse, DialogueState

logger = logging.getLogger(__name__)

class RealNluProcessor(NluProcessor):
    """实际的自然语言理解处理器实现"""
    
    def __init__(self):
        """初始化NLU处理器"""
        self.intent_patterns = self._init_intent_patterns()
        self.entity_patterns = self._init_entity_patterns()
        self.response_templates = self._init_response_templates()
    
    def _init_intent_patterns(self) -> Dict[str, List[str]]:
        """初始化意图识别模式"""
        return {
            "file_upload": [
                r"上传.*文件", r"导入.*数据", r"加载.*文件", r"处理.*文件",
                r"文件.*上传", r"数据.*导入", r".*\.csv", r".*\.xlsx"
            ],
            "stable_state_analysis": [
                r"稳态.*分析", r"稳定.*状态", r"平稳.*分析", r"稳态.*报表",
                r"stable.*state", r"steady.*analysis", r"稳定性.*分析"
            ],
            "functional_calculation": [
                r"功能.*计算", r"时间.*计算", r"启动.*时间", r"点火.*时间",
                r"停车.*时间", r"functional.*calc", r"time.*calculation"
            ],
            "status_evaluation": [
                r"状态.*评估", r"健康.*检查", r"故障.*检测", r"异常.*分析",
                r"status.*eval", r"health.*check", r"超温", r"超转", r"喘振"
            ],
            "report_generation": [
                r"生成.*报表", r"创建.*报告", r"输出.*报表", r"导出.*报告",
                r"generate.*report", r"create.*report", r"生成.*分析"
            ],
            "report_download": [
                r"下载.*报表", r"导出.*文件", r"保存.*报告", r"获取.*报表",
                r"download.*report", r"export.*file"
            ],
            "greeting": [
                r"你好", r"您好", r"hello", r"hi", r"开始", r"帮助",
                r"怎么.*使用", r"如何.*操作"
            ],
            "configure_parameters": [
                r"设置.*参数", r"配置.*选项", r"修改.*设置", r"调整.*参数",
                r"设定.*阈值", r"configure.*param", r"set.*parameter"
            ]
        }
    
    def _init_entity_patterns(self) -> Dict[str, List[str]]:
        """初始化实体识别模式"""
        return {
            "channel_names": [
                r"Ng\(rpm\)", r"Np\(rpm\)", r"Temperature\(°C\)", r"Pressure\(kPa\)",
                r"气发转速", r"动力转速", r"排气温度", r"滑油压力", r"燃气流量", r"空气流量"
            ],
            "statistics": [
                r"平均值", r"最大值", r"最小值", r"瞬时值", r"标准差", r"极差",
                r"average", r"maximum", r"minimum", r"instant", r"std", r"range"
            ],
            "logic_operators": [
                r"大于", r"小于", r"等于", r"不等于", r">=", r"<=", r">", r"<", r"=", r"!="
            ],
            "time_units": [
                r"秒", r"毫秒", r"分钟", r"小时", r"s", r"ms", r"min", r"h"
            ],
            "numbers": [
                r"\d+\.?\d*", r"[一二三四五六七八九十百千万]+"
            ]
        }
    
    def _init_response_templates(self) -> Dict[str, List[str]]:
        """初始化响应模板"""
        return {
            "greeting": [
                "您好！我是DRIA AI报表生成助手。请上传您的数据文件，我将帮助您生成专业的分析报表。",
                "欢迎使用DRIA智能报表系统！请告诉我您需要什么类型的分析。",
                "很高兴为您服务！您可以上传CSV或Excel文件开始分析。"
            ],
            "file_upload_success": [
                "文件上传成功！我已经识别出{channel_count}个数据通道。请告诉我您需要进行什么类型的分析？",
                "数据文件已成功处理，包含{channel_count}个通道：{channels}。您希望生成哪种类型的报表？",
                "文件解析完成！发现{channel_count}个数据通道。我可以为您进行稳态分析、功能计算或状态评估。"
            ],
            "stable_state_intent": [
                "我将为您进行稳态分析。请确认以下配置或告诉我需要调整的参数：",
                "稳态分析配置已准备就绪。我将分析数据的稳定状态特征。",
                "好的，我来为您分析数据的稳态特性。以下是建议的分析参数："
            ],
            "functional_calc_intent": [
                "我将进行功能计算分析，包括启动时间、点火时间等关键指标。",
                "功能计算分析即将开始，我将计算各项时间参数。",
                "好的，让我为您计算关键的功能参数和时间指标。"
            ],
            "status_eval_intent": [
                "我将进行状态评估分析，检查超温、超转、喘振等异常情况。",
                "状态评估分析已配置，将检测各种异常状态。",
                "好的，我来为您评估系统运行状态和健康指标。"
            ],
            "config_confirmation": [
                "配置已生成，请确认是否开始生成报表？",
                "分析参数已设置完成，是否立即开始报表生成？",
                "配置看起来不错！我现在可以开始生成您的专业报表了。"
            ],
            "report_generating": [
                "正在生成您的专业分析报表，请稍候...",
                "报表生成中，预计需要几十秒时间，请耐心等待。",
                "数据分析和报表生成正在进行中，马上就好！"
            ],
            "report_completed": [
                "报表生成完成！您可以点击下载按钮获取完整的分析报告。",
                "分析报表已成功生成，包含详细的数据分析和图表。",
                "您的专业报表已准备就绪，可以下载查看分析结果了！"
            ],
            "parameter_request": [
                "请告诉我您希望调整哪些分析参数？",
                "您想要修改阈值、时间窗口还是其他配置参数？",
                "我可以帮您调整分析条件，请具体说明您的需求。"
            ],
            "error_response": [
                "抱歉，我没有完全理解您的需求。请您再详细描述一下？",
                "请您换个方式描述，或者告诉我您具体想要什么类型的分析？",
                "让我重新理解一下您的需求，您可以更具体地说明吗？"
            ]
        }
    
    def process_user_input(self, user_input: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            context: 对话上下文
            
        Returns:
            (intent, extracted_info) 意图和提取的信息
        """
        try:
            # 预处理用户输入
            processed_input = self._preprocess_input(user_input)
            
            # 识别意图
            intent = self._recognize_intent(processed_input)
            
            # 提取实体信息
            entities = self._extract_entities(processed_input)
            
            # 结合上下文分析
            context_intent = self._analyze_context(intent, context)
            
            # 构建提取的信息
            extracted_info = {
                "intent": context_intent,
                "entities": entities,
                "confidence": self._calculate_confidence(intent, entities),
                "original_input": user_input,
                "processed_input": processed_input
            }
            
            logger.info(f"NLU processed: intent={context_intent}, confidence={extracted_info['confidence']}")
            return context_intent, extracted_info
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return "error", {"error": str(e)}
    
    def generate_response(self, intent: str, context: Dict[str, Any], extracted_info: Dict[str, Any]) -> str:
        """
        生成AI响应
        
        Args:
            intent: 识别的意图
            context: 对话上下文
            extracted_info: 提取的信息
            
        Returns:
            生成的响应文本
        """
        try:
            # 根据意图选择响应模板
            template_key = self._map_intent_to_template(intent)
            templates = self.response_templates.get(template_key, self.response_templates["error_response"])
            
            # 选择最适合的模板
            template = self._select_best_template(templates, context)
            
            # 填充模板变量
            response = self._fill_template_variables(template, context, extracted_info)
            
            logger.info(f"Generated response for intent: {intent}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "抱歉，处理您的请求时出现了错误。请稍后重试。"
    
    def extract_configuration_parameters(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        从用户输入中提取配置参数
        
        Args:
            user_input: 用户输入
            context: 上下文信息
            
        Returns:
            提取的配置参数
        """
        try:
            config_params = {}
            
            # 提取通道名称
            channels = self._extract_channel_names(user_input)
            if channels:
                config_params["channels"] = channels
            
            # 提取数值参数
            numbers = self._extract_numbers(user_input)
            if numbers:
                config_params["thresholds"] = numbers
            
            # 提取统计类型
            statistics = self._extract_statistics(user_input)
            if statistics:
                config_params["statistics"] = statistics
            
            # 提取逻辑操作符
            logic_ops = self._extract_logic_operators(user_input)
            if logic_ops:
                config_params["logic_operators"] = logic_ops
            
            # 提取时间参数
            time_params = self._extract_time_parameters(user_input)
            if time_params:
                config_params.update(time_params)
            
            return config_params
            
        except Exception as e:
            logger.error(f"Error extracting configuration parameters: {e}")
            return {}
    
    def _preprocess_input(self, user_input: str) -> str:
        """预处理用户输入"""
        # 转换为小写（保留中文）
        processed = user_input.strip()
        
        # 移除多余的空白字符
        processed = re.sub(r'\s+', ' ', processed)
        
        # 标准化标点符号
        processed = processed.replace('，', ',').replace('。', '.').replace('？', '?').replace('！', '!')
        
        return processed
    
    def _recognize_intent(self, processed_input: str) -> str:
        """识别用户意图"""
        intent_scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, processed_input, re.IGNORECASE):
                    score += 1
            
            if score > 0:
                intent_scores[intent] = score
        
        if intent_scores:
            # 返回得分最高的意图
            return max(intent_scores, key=intent_scores.get)
        
        return "unknown"
    
    def _extract_entities(self, processed_input: str) -> Dict[str, List[str]]:
        """提取实体信息"""
        entities = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            matches = []
            for pattern in patterns:
                found_matches = re.findall(pattern, processed_input, re.IGNORECASE)
                matches.extend(found_matches)
            
            if matches:
                entities[entity_type] = list(set(matches))  # 去重
        
        return entities
    
    def _analyze_context(self, intent: str, context: Dict[str, Any]) -> str:
        """结合上下文分析意图"""
        current_state = context.get("current_state", "initial")
        
        # 根据当前状态调整意图
        if current_state == "initial" and intent == "unknown":
            return "greeting"
        elif current_state == "file_uploaded" and intent in ["stable_state_analysis", "functional_calculation", "status_evaluation"]:
            return intent
        elif current_state == "configuring" and intent == "report_generation":
            return "config_confirmation"
        elif intent == "unknown":
            return "parameter_request"
        
        return intent
    
    def _calculate_confidence(self, intent: str, entities: Dict[str, List[str]]) -> float:
        """计算置信度"""
        base_confidence = 0.7 if intent != "unknown" else 0.3
        
        # 根据实体数量调整置信度
        entity_bonus = len(entities) * 0.05
        
        return min(1.0, base_confidence + entity_bonus)
    
    def _map_intent_to_template(self, intent: str) -> str:
        """将意图映射到响应模板"""
        intent_template_map = {
            "greeting": "greeting",
            "file_upload": "file_upload_success",
            "stable_state_analysis": "stable_state_intent",
            "functional_calculation": "functional_calc_intent",
            "status_evaluation": "status_eval_intent",
            "report_generation": "config_confirmation",
            "configure_parameters": "parameter_request",
            "unknown": "error_response"
        }
        
        return intent_template_map.get(intent, "error_response")
    
    def _select_best_template(self, templates: List[str], context: Dict[str, Any]) -> str:
        """选择最适合的模板"""
        # 简单实现：随机选择或根据上下文选择
        import random
        return random.choice(templates)
    
    def _fill_template_variables(self, template: str, context: Dict[str, Any], extracted_info: Dict[str, Any]) -> str:
        """填充模板变量"""
        response = template
        
        # 填充文件信息
        if "{channel_count}" in response:
            file_info = context.get("file_info", {})
            channel_count = len(file_info.get("available_channels", []))
            response = response.replace("{channel_count}", str(channel_count))
        
        if "{channels}" in response:
            file_info = context.get("file_info", {})
            channels = file_info.get("available_channels", [])
            channels_str = "、".join(channels[:3])  # 只显示前3个
            if len(channels) > 3:
                channels_str += f"等{len(channels)}个通道"
            response = response.replace("{channels}", channels_str)
        
        return response
    
    def _extract_channel_names(self, text: str) -> List[str]:
        """提取通道名称"""
        channels = []
        patterns = self.entity_patterns["channel_names"]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            channels.extend(matches)
        
        return list(set(channels))
    
    def _extract_numbers(self, text: str) -> List[float]:
        """提取数值"""
        numbers = []
        number_patterns = [r'\d+\.?\d*']
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    numbers.append(float(match))
                except ValueError:
                    continue
        
        return numbers
    
    def _extract_statistics(self, text: str) -> List[str]:
        """提取统计类型"""
        statistics = []
        patterns = self.entity_patterns["statistics"]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                statistics.append(pattern)
        
        return statistics
    
    def _extract_logic_operators(self, text: str) -> List[str]:
        """提取逻辑操作符"""
        operators = []
        patterns = self.entity_patterns["logic_operators"]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                operators.append(pattern)
        
        return operators
    
    def _extract_time_parameters(self, text: str) -> Dict[str, Any]:
        """提取时间参数"""
        time_params = {}
        
        # 提取时间数值和单位
        time_pattern = r'(\d+\.?\d*)\s*(秒|毫秒|分钟|小时|s|ms|min|h)'
        matches = re.findall(time_pattern, text, re.IGNORECASE)
        
        for value, unit in matches:
            try:
                time_value = float(value)
                # 转换为秒
                if unit in ['毫秒', 'ms']:
                    time_value = time_value / 1000
                elif unit in ['分钟', 'min']:
                    time_value = time_value * 60
                elif unit in ['小时', 'h']:
                    time_value = time_value * 3600
                
                time_params["duration"] = time_value
                break
            except ValueError:
                continue
        
        return time_params
