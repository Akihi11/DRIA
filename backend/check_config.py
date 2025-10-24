#!/usr/bin/env python3
"""
配置检查工具
用于检查.env文件中的大模型配置是否正确
"""

import sys
from pathlib import Path
from config import settings

def check_config():
    """检查配置文件"""
    print("🔍 DRIA AI对话系统 - 配置检查工具")
    print("=" * 50)
    
    # 检查.env文件是否存在
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("❌ 未找到.env文件")
        print("💡 请复制 env.example 为 .env 并填入您的配置")
        return False
    
    print("✅ 找到.env配置文件")
    
    # 检查默认提供商
    print(f"\n🎯 默认大模型提供商: {settings.DEFAULT_LLM_PROVIDER}")
    
    # 检查可用的提供商
    available_providers = settings.get_available_providers()
    print(f"\n📋 可用的提供商 ({len(available_providers)}个):")
    
    if not available_providers:
        print("❌ 没有可用的提供商！请检查API密钥配置")
        return False
    
    for i, provider in enumerate(available_providers, 1):
        status = "✅" if provider == settings.DEFAULT_LLM_PROVIDER else "⚪"
        print(f"  {status} {i}. {provider}")
    
    # 详细检查每个提供商
    print(f"\n🔧 详细配置检查:")
    
    providers_config = {
        "deepseek": {
            "key": settings.DEEPSEEK_API_KEY,
            "url": settings.DEEPSEEK_BASE_URL,
            "model": settings.DEEPSEEK_MODEL
        },
        "openai": {
            "key": settings.OPENAI_API_KEY,
            "url": settings.OPENAI_BASE_URL,
            "model": settings.OPENAI_MODEL
        },
        "anthropic": {
            "key": settings.ANTHROPIC_API_KEY,
            "url": settings.ANTHROPIC_BASE_URL,
            "model": settings.ANTHROPIC_MODEL
        },
        "google": {
            "key": settings.GOOGLE_API_KEY,
            "url": settings.GOOGLE_BASE_URL,
            "model": settings.GOOGLE_MODEL
        },
        "azure": {
            "key": settings.AZURE_API_KEY,
            "url": settings.AZURE_BASE_URL,
            "model": settings.AZURE_MODEL
        },
        "local": {
            "key": settings.LOCAL_API_KEY,
            "url": settings.LOCAL_BASE_URL,
            "model": settings.LOCAL_MODEL
        }
    }
    
    for provider, config in providers_config.items():
        if provider in available_providers:
            print(f"\n  ✅ {provider.upper()}:")
            print(f"     🔑 API Key: {'已配置' if config['key'] else '未配置'}")
            print(f"     🌐 Base URL: {config['url']}")
            print(f"     🤖 Model: {config['model']}")
        else:
            print(f"\n  ❌ {provider.upper()}: 未配置")
    
    # 使用建议
    print(f"\n💡 使用建议:")
    if settings.DEFAULT_LLM_PROVIDER in available_providers:
        print(f"  ✅ 默认提供商 '{settings.DEFAULT_LLM_PROVIDER}' 已正确配置")
    else:
        print(f"  ⚠️  默认提供商 '{settings.DEFAULT_LLM_PROVIDER}' 不可用")
        print(f"  💡 建议修改 DEFAULT_LLM_PROVIDER 为: {available_providers[0]}")
    
    print(f"\n🚀 API使用示例:")
    print(f"  # 使用默认提供商")
    print(f"  curl -X POST http://127.0.0.1:8000/api/ai_report/dialogue \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"session_id\":\"test\",\"user_input\":\"你好\",\"dialogue_state\":\"initial\"}}'")
    
    if len(available_providers) > 1:
        print(f"\n  # 指定其他提供商")
        for provider in available_providers[:3]:  # 只显示前3个
            print(f"  curl -X POST http://127.0.0.1:8000/api/ai_report/dialogue \\")
            print(f"    -H 'Content-Type: application/json' \\")
            print(f"    -d '{{\"session_id\":\"test\",\"user_input\":\"你好\",\"dialogue_state\":\"initial\",\"provider\":\"{provider}\"}}'")
    
    return True

if __name__ == "__main__":
    try:
        success = check_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        sys.exit(1)

