"""
配置状态管理器 - 支持配置对话功能
"""
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ConfigStatus(str, Enum):
    """配置状态枚举"""
    CONFIGURING = "configuring"  # 配置中
    CONFIRMING = "confirming"    # 确认中
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消

class ConfigManager:
    """配置状态管理器 - 支持配置对话功能"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 3600  # 1小时超时
    
    async def start_config_session(self, report_type: str, user_id: str) -> Dict[str, Any]:
        """
        开始配置会话
        
        Args:
            report_type: 报表类型
            user_id: 用户ID
            
        Returns:
            会话信息字典
        """
        session_id = f"{user_id}_{report_type}_{int(time.time())}"
        
        # 获取默认配置
        default_config = self.get_default_config(report_type)
        
        self.active_sessions[session_id] = {
            "report_type": report_type,
            "config": default_config,
            "status": ConfigStatus.CONFIGURING,
            "created_at": datetime.now(),
            "user_id": user_id,
            "last_activity": datetime.now(),
            "step": 0,
            "history": []  # 配置历史记录
        }
        
        logger.info(f"开始配置会话: {session_id}, 报表类型: {report_type}")
        
        # 初始建议：通道选择
        try:
            from backend.services.config_dialogue_parser import config_parser
            suggested_actions = config_parser.get_suggested_actions("channel_selection", default_config)
        except Exception:
            suggested_actions = []

        return {
            "session_id": session_id,
            "config": default_config,
            "status": ConfigStatus.CONFIGURING,
            "message": f"开始配置{report_type}报表，您可以通过对话方式修改参数",
            "suggested_actions": suggested_actions
        }
    
    async def update_config(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新配置参数
        
        Args:
            session_id: 会话ID
            updates: 更新参数字典
            
        Returns:
            更新后的配置信息
        """
        if session_id not in self.active_sessions:
            raise ValueError("配置会话不存在")
        
        session = self.active_sessions[session_id]
        
        # 记录配置历史
        old_config = session["config"].copy()
        
        # 应用更新
        for field, value in updates.items():
            if field in session["config"]:
                session["config"][field] = value
                logger.info(f"更新配置: {field} = {value}")
        
        # 更新活动时间
        session["last_activity"] = datetime.now()
        session["step"] += 1
        
        # 记录历史
        session["history"].append({
            "timestamp": datetime.now(),
            "action": "update",
            "field": list(updates.keys())[0] if updates else "unknown",
            "value": list(updates.values())[0] if updates else None,
            "old_config": old_config,
            "new_config": session["config"].copy()
        })
        
        return {
            "config": session["config"],
            "status": session["status"],
            "message": "配置已更新"
        }
    
    async def complete_config(self, session_id: str) -> Dict[str, Any]:
        """
        完成配置
        
        Args:
            session_id: 会话ID
            
        Returns:
            完成状态信息
        """
        if session_id not in self.active_sessions:
            raise ValueError("配置会话不存在")
        
        session = self.active_sessions[session_id]
        
        if session["status"] == ConfigStatus.CONFIGURING:
            # 校验：必须选择一个转速通道类型（Ng/Np）
            rpm_selected = session["config"].get("use_rpm_channel") is True
            rpm_type = session["config"].get("rpm_channel_type")
            if not rpm_selected or rpm_type not in ("Ng", "Np"):
                return {
                    "config": session["config"],
                    "status": ConfigStatus.CONFIGURING,
                    "message": "请先选择一个转速通道（Ng 或 Np）后再确认"
                }
            # 第一次点击完成配置，进入确认状态
            session["status"] = ConfigStatus.CONFIRMING
            session["last_activity"] = datetime.now()
            
            return {
                "config": session["config"],
                "status": ConfigStatus.CONFIRMING,
                "message": "请确认配置参数，再次点击完成配置开始生成报表"
            }
        elif session["status"] == ConfigStatus.CONFIRMING:
            # 第二次点击完成配置，真正完成
            session["status"] = ConfigStatus.COMPLETED
            session["last_activity"] = datetime.now()
            
            # 记录完成历史
            session["history"].append({
                "timestamp": datetime.now(),
                "action": "complete",
                "config": session["config"].copy()
            })
            # 持久化到JSON（每个会话一份）
            try:
                project_root = Path(__file__).resolve().parents[2]
                out_dir = project_root / "samples" / "config_sessions"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{session_id}.json"
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump({
                        "session_id": session_id,
                        "report_type": session["report_type"],
                        "config": session["config"]
                    }, f, ensure_ascii=False, indent=2)
            except Exception as persist_err:
                logger.warning(f"保存配置到JSON失败: {persist_err}")
            
            logger.info(f"配置会话完成: {session_id}")
            
            return {
                "config": session["config"],
                "status": ConfigStatus.COMPLETED,
                "message": "配置完成，开始生成报表"
            }
        
        return {
            "config": session["config"],
            "status": session["status"],
            "message": "配置已完成"
        }
    
    async def cancel_config(self, session_id: str) -> Dict[str, Any]:
        """
        取消配置
        
        Args:
            session_id: 会话ID
            
        Returns:
            取消状态信息
        """
        if session_id not in self.active_sessions:
            raise ValueError("配置会话不存在")
        
        session = self.active_sessions[session_id]
        session["status"] = ConfigStatus.CANCELLED
        session["last_activity"] = datetime.now()
        
        # 记录取消历史
        session["history"].append({
            "timestamp": datetime.now(),
            "action": "cancel",
            "config": session["config"].copy()
        })
        
        logger.info(f"配置会话取消: {session_id}")
        
        return {
            "config": session["config"],
            "status": ConfigStatus.CANCELLED,
            "message": "配置已取消"
        }
    
    def get_active_session(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取活跃的配置会话
        
        Args:
            user_id: 用户ID，如果提供则只返回该用户的会话
            
        Returns:
            活跃会话信息
        """
        # 清理过期会话
        self._cleanup_expired_sessions()
        
        for session_id, session in self.active_sessions.items():
            if session["status"] in [ConfigStatus.CONFIGURING, ConfigStatus.CONFIRMING]:
                if user_id is None or session["user_id"] == user_id:
                    return {
                        "session_id": session_id,
                        "report_type": session["report_type"],
                        "config": session["config"],
                        "status": session["status"],
                        "user_id": session["user_id"]
                    }
        
        return None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息
        """
        return self.active_sessions.get(session_id)
    
    def get_default_config(self, report_type: str) -> Dict[str, Any]:
        """
        获取默认配置参数
        
        Args:
            report_type: 报表类型
            
        Returns:
            默认配置字典
        """
        default_configs = {
            "steady_state": {
                "use_rpm_channel": False,
                "rpm_channel_type": None,  # 必选，其值为 "Ng" 或 "Np"
                "use_temperature_channel": False,
                "use_pressure_channel": False,
                "threshold": 10000,
                "statistical_method": "平均值",
                "time_window": 5,
                "time_unit": "分钟"
            },
            "function_calc": {
                "use_rpm_channel": False,
                "rpm_channel_type": None,
                "use_temperature_channel": True,
                "use_pressure_channel": False,
                "calculation_method": "多项式拟合",
                "polynomial_degree": 2,
                "time_window": 10,
                "time_unit": "分钟"
            },
            "status_eval": {
                "use_rpm_channel": False,
                "rpm_channel_type": None,
                "use_temperature_channel": True,
                "use_pressure_channel": True,
                "evaluation_criteria": "综合评估",
                "threshold_rpm": 10000,
                "threshold_temperature": 80,
                "threshold_pressure": 100
            },
            "complete": {
                "use_rpm_channel": False,
                "rpm_channel_type": None,
                "use_temperature_channel": True,
                "use_pressure_channel": True,
                "include_steady_state": True,
                "include_function_calc": True,
                "include_status_eval": True,
                "time_window": 15,
                "time_unit": "分钟"
            }
        }
        
        return default_configs.get(report_type, {})
    
    def _cleanup_expired_sessions(self):
        """清理过期的会话"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            time_diff = (current_time - session["last_activity"]).total_seconds()
            if time_diff > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            logger.info(f"清理过期会话: {session_id}")
            del self.active_sessions[session_id]
    
    def get_config_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取配置历史记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            历史记录列表
        """
        session = self.active_sessions.get(session_id)
        if session:
            return session.get("history", [])
        return []
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有会话信息（调试用）
        
        Returns:
            所有会话信息
        """
        return self.active_sessions.copy()

# 全局配置管理器实例
config_manager = ConfigManager()
