"""
API测试脚本 - 用于验证第一阶段的Mock API服务
"""
import requests
import json
import time
from pathlib import Path

# API基础URL
BASE_URL = "http://127.0.0.1:8000/api"

def test_health_check():
    """测试健康检查端点"""
    print("🔍 测试健康检查...")
    
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 健康检查成功: {data['status']}")
        return True
    else:
        print(f"❌ 健康检查失败: {response.status_code}")
        return False

def test_file_upload():
    """测试文件上传端点"""
    print("📁 测试文件上传...")
    
    # 创建测试文件
    test_file_content = """timestamp,Ng(rpm),Temperature(°C),Pressure(kPa)
0.0,15234,650.2,800.5
0.03,15241,650.5,801.2
0.06,15238,650.1,799.8"""
    
    test_file_path = Path("test_data.csv")
    with open(test_file_path, "w") as f:
        f.write(test_file_content)
    
    try:
        with open(test_file_path, "rb") as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            response = requests.post(f"{BASE_URL}/upload", files=files)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 文件上传成功: {data['file_id']}")
            print(f"   检测到通道: {', '.join(data['detected_channels'])}")
            return data['file_id']
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None
    
    finally:
        # 清理测试文件
        if test_file_path.exists():
            test_file_path.unlink()

def test_dialogue_flow(file_id):
    """测试完整的对话流程"""
    print("💬 测试对话流程...")
    
    # 创建会话
    session_response = requests.post(f"{BASE_URL}/ai_report/sessions", params={"file_id": file_id})
    if session_response.status_code != 200:
        print("❌ 创建会话失败")
        return None
    
    session_id = session_response.json()["session_id"]
    print(f"   会话ID: {session_id}")
    
    # 对话步骤
    dialogue_steps = [
        {
            "user_input": "我想生成稳定状态报表",
            "dialogue_state": "file_uploaded",
            "expected_state": "configuring"
        },
        {
            "user_input": "使用Ng(rpm)作为判断通道",
            "dialogue_state": "configuring", 
            "expected_state": "confirming"
        },
        {
            "user_input": "确认配置，生成报表",
            "dialogue_state": "confirming",
            "expected_state": "completed"
        }
    ]
    
    report_url = None
    
    for i, step in enumerate(dialogue_steps, 1):
        print(f"   步骤 {i}: {step['user_input']}")
        
        dialogue_request = {
            "session_id": session_id,
            "file_id": file_id,
            "user_input": step["user_input"],
            "dialogue_state": step["dialogue_state"]
        }
        
        response = requests.post(f"{BASE_URL}/ai_report/dialogue", json=dialogue_request)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   AI回复: {data['ai_response'][:100]}...")
            print(f"   状态: {data['dialogue_state']}")
            
            if data['is_complete'] and data['report_url']:
                report_url = data['report_url']
                print(f"   ✅ 对话完成，报表URL: {report_url}")
        else:
            print(f"   ❌ 对话步骤失败: {response.status_code}")
    
    return report_url

def test_report_generation(file_id):
    """测试直接报表生成"""
    print("📊 测试报表生成...")
    
    # 报表配置
    report_config = {
        "session_id": "test_session_direct",
        "file_id": file_id,
        "config": {
            "sourceFileId": file_id,
            "reportConfig": {
                "sections": ["stableState", "functionalCalc"],
                "stableState": {
                    "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
                    "condition": {
                        "channel": "Ng(rpm)",
                        "statistic": "平均值",
                        "duration": 1,
                        "logic": ">",
                        "threshold": 15000
                    }
                },
                "functionalCalc": {
                    "time_base": {
                        "channel": "Pressure(kPa)",
                        "statistic": "平均值",
                        "duration": 1,
                        "logic": ">",
                        "threshold": 500
                    }
                }
            }
        }
    }
    
    response = requests.post(f"{BASE_URL}/reports/generate", json=report_config)
    
    if response.status_code == 200:
        data = response.json()
        if data['success']:
            print(f"✅ 报表生成成功: {data['report_id']}")
            print(f"   下载URL: {data['report_url']}")
            return data['report_id']
        else:
            print(f"❌ 报表生成失败: {data['error_message']}")
    else:
        print(f"❌ 报表生成请求失败: {response.status_code}")
    
    return None

def test_report_download(report_id):
    """测试报表下载"""
    print("⬇️ 测试报表下载...")
    
    # 从URL中提取实际的report_id
    if "/download/" in report_id:
        actual_report_id = report_id.split("/download/")[1].replace(".xlsx", "")
    else:
        actual_report_id = report_id
    
    response = requests.get(f"{BASE_URL}/reports/download/{actual_report_id}")
    
    if response.status_code == 200:
        # 保存下载的文件
        output_path = Path(f"downloaded_report_{actual_report_id}.xlsx")
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        print(f"✅ 报表下载成功: {output_path}")
        print(f"   文件大小: {len(response.content)} bytes")
        return True
    else:
        print(f"❌ 报表下载失败: {response.status_code}")
        return False

def run_comprehensive_test():
    """运行完整的API测试流程"""
    print("🚀 开始API综合测试...\n")
    
    # 1. 健康检查
    if not test_health_check():
        return
    print()
    
    # 2. 文件上传
    file_id = test_file_upload()
    if not file_id:
        return
    print()
    
    # 3. 对话流程测试
    dialogue_report_url = test_dialogue_flow(file_id)
    print()
    
    # 4. 直接报表生成测试
    direct_report_id = test_report_generation(file_id)
    print()
    
    # 5. 报表下载测试
    if direct_report_id:
        test_report_download(direct_report_id)
        print()
    
    # 6. 获取报表列表
    print("📋 获取报表列表...")
    response = requests.get(f"{BASE_URL}/reports")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 共找到 {data['total']} 个报表")
        for report in data['reports']:
            print(f"   - {report['report_id']} (生成时间: {report['generation_time']})")
    print()
    
    print("🎉 API测试完成！")
    print("\n📚 API文档地址: http://127.0.0.1:8000/api/docs")
    print("🔍 ReDoc文档: http://127.0.0.1:8000/api/redoc")

if __name__ == "__main__":
    print("=" * 60)
    print("AI Report Generation API - 测试脚本")
    print("=" * 60)
    print()
    
    try:
        run_comprehensive_test()
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到API服务器")
        print("请确保服务器正在运行: python main.py")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
