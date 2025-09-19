"""
Dialogue management API endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid
from datetime import datetime
import sys
from pathlib import Path

# 添加父目录到Python路径以支持相对导入
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent
sys.path.insert(0, str(parent_dir))

from backend.models.api_models import DialogueRequest, DialogueResponse, DialogueState, ErrorResponse
from backend.services import DialogueManager, NluProcessor, RuleProvider, DIALOGUE_IMPLEMENTATION_TYPE

router = APIRouter()

# Initialize dialogue service
dialogue_manager = DialogueManager()

# Log implementation type
print(f"[INFO] Dialogue API using {DIALOGUE_IMPLEMENTATION_TYPE} implementation")


@router.post("/ai_report/dialogue", response_model=DialogueResponse, summary="AI对话接口")
async def process_dialogue(request: DialogueRequest):
    """
    处理AI对话请求
    
    核心的对话式配置接口，通过多轮对话引导用户完成报表配置
    
    - **session_id**: 会话ID
    - **file_id**: 数据文件ID（可选）
    - **user_input**: 用户输入内容
    - **dialogue_state**: 当前对话状态
    """
    
    try:
        # Use real dialogue manager to process the request
        response = dialogue_manager.process(request)
        return response
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Dialogue API Error: {e}")
        print(traceback.format_exc())
        return DialogueResponse(
            session_id=request.session_id,
            ai_response="抱歉，处理您的请求时出现了错误。请稍后重试。",
            dialogue_state=DialogueState.ERROR,
            suggested_actions=["请重新开始对话"],
            is_complete=False,
            error_message=str(e)
        )


async def generate_mock_response(request: DialogueRequest, session: Dict[str, Any]):
    """生成模拟AI响应"""
    
    current_state = DialogueState(request.dialogue_state)
    user_input = request.user_input.lower()
    
    if current_state == DialogueState.INITIAL:
        if "上传" in user_input or "文件" in user_input:
            return (
                "欢迎使用AI报表生成系统！我看到您想要上传文件。请先上传您的数据文件，然后告诉我您希望生成什么类型的报表。\n\n我可以帮您生成以下类型的报表：\n1. 稳定状态参数汇总表\n2. 功能计算汇总表\n3. 状态评估表\n\n您希望生成哪种报表呢？",
                ["稳定状态报表", "功能计算报表", "状态评估报表", "全部报表"],
                DialogueState.FILE_UPLOADED,
                False,
                None
            )
        else:
            return (
                "您好！我是AI报表生成助手。请先上传您的数据文件，然后我会引导您完成报表配置。",
                ["上传文件"],
                DialogueState.INITIAL,
                False,
                None
            )
    
    elif current_state == DialogueState.FILE_UPLOADED:
        if "稳定状态" in user_input:
            session["config"]["sections"] = ["stableState"]
            return (
                "好的，我将帮您配置稳定状态参数汇总表。\n\n首先，请告诉我您想要显示哪些通道的数据？我检测到您的文件中包含以下通道：\n- Ng(rpm)\n- Temperature(°C)\n- Pressure(kPa)\n- Fuel_Flow(kg/h)\n- Vibration(mm/s)",
                ["Ng(rpm), Temperature(°C)", "全部通道", "自定义选择"],
                DialogueState.CONFIGURING,
                False,
                None
            )
        elif "功能计算" in user_input:
            session["config"]["sections"] = ["functionalCalc"]
            return (
                "好的，我将帮您配置功能计算汇总表。\n\n功能计算包括以下几个时间指标：\n1. 时间基准\n2. 启动时间\n3. 点火时间\n4. Ng余转时间\n\n您希望计算哪些指标？",
                ["全部指标", "时间基准+启动时间", "自定义选择"],
                DialogueState.CONFIGURING,
                False,
                None
            )
        elif "全部" in user_input:
            session["config"]["sections"] = ["stableState", "functionalCalc", "statusEval"]
            return (
                "很好！我将帮您生成包含所有三个部分的完整报表。让我们从稳定状态配置开始。\n\n请选择用于稳定状态判断的主要通道：",
                ["Ng(rpm)", "Temperature(°C)", "Pressure(kPa)"],
                DialogueState.CONFIGURING,
                False,
                None
            )
    
    elif current_state == DialogueState.CONFIGURING:
        if "ng" in user_input or "转速" in user_input:
            return (
                "好的，使用Ng(rpm)作为稳定状态判断通道。\n\n现在请设置稳定状态的判断条件：\n- 统计量类型：平均值\n- 持续时间：1秒\n- 判断逻辑：大于\n- 阈值：15000 rpm\n\n这些设置是否合适？",
                ["是的，继续", "修改阈值", "修改其他参数"],
                DialogueState.CONFIRMING,
                False,
                None
            )
        else:
            return (
                "请您再详细说明一下配置要求，或者选择一个推荐的配置选项。",
                ["使用默认配置", "重新选择"],
                DialogueState.CONFIGURING,
                False,
                None
            )
    
    elif current_state == DialogueState.CONFIRMING:
        if "是" in user_input or "继续" in user_input or "确认" in user_input:
            # Mock report generation
            report_url = f"/api/reports/download/{uuid.uuid4()}.xlsx"
            return (
                "配置完成！正在生成您的报表，请稍候...\n\n✅ 报表生成成功！\n\n您的报表已经准备好，包含以下内容：\n- 稳定状态参数汇总表\n- 数据分析图表\n\n点击下方链接下载报表文件。",
                ["下载报表", "生成新报表"],
                DialogueState.COMPLETED,
                True,
                report_url
            )
        else:
            return (
                "好的，让我们重新配置参数。请告诉我您希望修改什么？",
                ["修改阈值", "修改通道", "重新开始"],
                DialogueState.CONFIGURING,
                False,
                None
            )
    
    else:
        return (
            "感谢使用AI报表生成系统！如需生成新的报表，请重新开始对话。",
            ["开始新对话"],
            DialogueState.COMPLETED,
            True,
            None
        )


@router.get("/ai_report/sessions/{session_id}", summary="获取会话信息")
async def get_session(session_id: str):
    """
    获取指定会话的详细信息
    
    - **session_id**: 会话ID
    """
    
    if session_id not in mock_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"会话 {session_id} 不存在"
        )
    
    return {
        "session_id": session_id,
        "session_data": mock_sessions[session_id]
    }


@router.delete("/ai_report/sessions/{session_id}", summary="删除会话")
async def delete_session(session_id: str):
    """
    删除指定的会话
    
    - **session_id**: 要删除的会话ID
    """
    
    if session_id not in mock_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"会话 {session_id} 不存在"
        )
    
    del mock_sessions[session_id]
    
    return {"message": f"会话 {session_id} 已成功删除"}


@router.post("/ai_report/sessions", summary="创建新会话")
async def create_session(file_id: str = None):
    """
    创建新的对话会话
    
    - **file_id**: 可选的文件ID
    """
    
    session_id = str(uuid.uuid4())
    
    mock_sessions[session_id] = {
        "state": DialogueState.INITIAL,
        "file_id": file_id,
        "config": {},
        "message_history": [],
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "session_id": session_id,
        "message": "新会话创建成功"
    }