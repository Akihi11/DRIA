"""
配置管理API路由
提供配置检查和提供商信息查询功能
"""

from fastapi import APIRouter, HTTPException
from config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["配置管理"])

@router.get("/providers")
async def get_available_providers():
    """
    获取可用的LLM提供商列表
    
    Returns:
        dict: 包含可用提供商列表和默认提供商信息
    """
    try:
        available_providers = settings.get_available_providers()
        
        return {
            "success": True,
            "data": {
                "default_provider": settings.DEFAULT_LLM_PROVIDER,
                "available_providers": available_providers,
                "total_count": len(available_providers),
                "is_default_available": settings.is_provider_available(settings.DEFAULT_LLM_PROVIDER)
            },
            "message": f"找到 {len(available_providers)} 个可用的提供商"
        }
    except Exception as e:
        logger.error(f"获取提供商列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取提供商列表失败: {str(e)}")

@router.get("/providers/{provider}")
async def get_provider_info(provider: str):
    """
    获取指定提供商的详细信息
    
    Args:
        provider: 提供商名称 (deepseek, openai, anthropic, google, azure, local)
    
    Returns:
        dict: 提供商详细信息
    """
    try:
        if not settings.is_provider_available(provider):
            raise HTTPException(
                status_code=404, 
                detail=f"提供商 '{provider}' 不可用，请检查配置"
            )
        
        # 获取提供商配置信息
        provider_configs = {
            "deepseek": {
                "api_key": "已配置" if settings.DEEPSEEK_API_KEY else "未配置",
                "base_url": settings.DEEPSEEK_BASE_URL,
                "model": settings.DEEPSEEK_MODEL
            },
            "openai": {
                "api_key": "已配置" if settings.OPENAI_API_KEY else "未配置",
                "base_url": settings.OPENAI_BASE_URL,
                "model": settings.OPENAI_MODEL
            },
            "anthropic": {
                "api_key": "已配置" if settings.ANTHROPIC_API_KEY else "未配置",
                "base_url": settings.ANTHROPIC_BASE_URL,
                "model": settings.ANTHROPIC_MODEL
            },
            "google": {
                "api_key": "已配置" if settings.GOOGLE_API_KEY else "未配置",
                "base_url": settings.GOOGLE_BASE_URL,
                "model": settings.GOOGLE_MODEL
            },
            "azure": {
                "api_key": "已配置" if settings.AZURE_API_KEY else "未配置",
                "base_url": settings.AZURE_BASE_URL,
                "model": settings.AZURE_MODEL,
                "api_version": settings.AZURE_API_VERSION
            },
            "local": {
                "api_key": "已配置" if settings.LOCAL_API_KEY else "未配置",
                "base_url": settings.LOCAL_BASE_URL,
                "model": settings.LOCAL_MODEL
            },
            "qwen": {
                "api_key": "已配置" if settings.QWEN_API_KEY else "未配置",
                "base_url": settings.QWEN_BASE_URL,
                "model": settings.QWEN_MODEL
            },
            "kimi": {
                "api_key": "已配置" if settings.KIMI_API_KEY else "未配置",
                "base_url": settings.KIMI_BASE_URL,
                "model": settings.KIMI_MODEL
            }
        }
        
        config = provider_configs.get(provider, {})
        
        return {
            "success": True,
            "data": {
                "provider": provider,
                "is_default": provider == settings.DEFAULT_LLM_PROVIDER,
                "config": config
            },
            "message": f"提供商 '{provider}' 配置信息"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取提供商信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取提供商信息失败: {str(e)}")

@router.get("/status")
async def get_config_status():
    """
    获取整体配置状态
    
    Returns:
        dict: 配置状态信息
    """
    try:
        available_providers = settings.get_available_providers()
        
        status = {
            "is_configured": len(available_providers) > 0,
            "default_provider": settings.DEFAULT_LLM_PROVIDER,
            "default_available": settings.is_provider_available(settings.DEFAULT_LLM_PROVIDER),
            "available_count": len(available_providers),
            "available_providers": available_providers,
            "recommendations": []
        }
        
        # 添加建议
        if not status["is_configured"]:
            status["recommendations"].append("请至少配置一个大模型的API密钥")
        elif not status["default_available"]:
            status["recommendations"].append(f"默认提供商 '{settings.DEFAULT_LLM_PROVIDER}' 不可用，建议修改为: {available_providers[0]}")
        
        return {
            "success": True,
            "data": status,
            "message": "配置状态检查完成"
        }
    except Exception as e:
        logger.error(f"获取配置状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置状态失败: {str(e)}")
