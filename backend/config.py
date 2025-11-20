"""
Configuration module for the AI Dialogue Backend
"""
import os
from pathlib import Path

# 尝试加载.env文件
def load_env_file():
    """加载.env文件"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# 加载环境变量
load_env_file()

class Settings:
    """Application settings"""
    
    def __init__(self):
        # API Configuration
        self.API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
        self.API_PORT: int = int(os.getenv("API_PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
        
        # Logging Configuration
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Default LLM Provider Configuration
        self.DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "").lower()
        # 若未显式指定，则根据实际可用供应商自动选择（优先本地）
        if not self.DEFAULT_LLM_PROVIDER:
            providers = self.get_available_providers()
            if "local" in providers:
                self.DEFAULT_LLM_PROVIDER = "local"
            elif providers:
                self.DEFAULT_LLM_PROVIDER = providers[0]
            else:
                # 理论上不会发生（本地有默认 BASE_URL），兜底为 local
                self.DEFAULT_LLM_PROVIDER = "local"
        
        # DeepSeek API Configuration
        self.DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        
        # OpenAI API Configuration
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
        self.OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
        
        # Anthropic (Claude) API Configuration
        self.ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        self.ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
        
        # Google (Gemini) API Configuration
        self.GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
        self.GOOGLE_BASE_URL: str = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com")
        self.GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-pro")
        
        # Azure OpenAI Configuration
        self.AZURE_API_KEY: str = os.getenv("AZURE_API_KEY", "")
        self.AZURE_BASE_URL: str = os.getenv("AZURE_BASE_URL", "")
        self.AZURE_MODEL: str = os.getenv("AZURE_MODEL", "gpt-4")
        self.AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")
        
        # Local Model Configuration (如Ollama)
        self.LOCAL_API_KEY: str = os.getenv("LOCAL_API_KEY", "")
        self.LOCAL_BASE_URL: str = os.getenv("LOCAL_BASE_URL", "http://localhost:11434")
        self.LOCAL_MODEL: str = os.getenv("LOCAL_MODEL")
        
        # QWEN API Configuration
        self.QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
        self.QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com")
        self.QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-plus")
        
        # Kimi (月之暗面) API Configuration
        self.KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "")
        self.KIMI_BASE_URL: str = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn")
        self.KIMI_MODEL: str = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
        
        # File Upload Configuration
        self.MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "104857600"))  # 100MB
        self.ALLOWED_EXTENSIONS: str = os.getenv("ALLOWED_EXTENSIONS", ".csv,.xlsx,.xls")
        self.REPORT_OUTPUT_DIR: str = os.getenv("REPORT_OUTPUT_DIR", "reports")
        self.UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    
    def get_available_providers(self):
        """获取可用的LLM提供商列表"""
        providers = []
        
        # 检查API密钥是否有效（不是占位符）
        if self.DEEPSEEK_API_KEY and self.DEEPSEEK_API_KEY != "your_deepseek_api_key_here":
            providers.append("deepseek")
        if self.OPENAI_API_KEY and self.OPENAI_API_KEY != "your_openai_api_key_here":
            providers.append("openai")
        if self.ANTHROPIC_API_KEY and self.ANTHROPIC_API_KEY != "your_anthropic_api_key_here":
            providers.append("anthropic")
        if self.GOOGLE_API_KEY and self.GOOGLE_API_KEY != "your_google_api_key_here":
            providers.append("google")
        if (self.AZURE_API_KEY and self.AZURE_API_KEY != "your_azure_api_key_here" and 
            self.AZURE_BASE_URL and self.AZURE_BASE_URL != "https://your-resource.openai.azure.com"):
            providers.append("azure")
        if self.QWEN_API_KEY and self.QWEN_API_KEY != "your_qwen_api_key_here":
            providers.append("qwen")
        if self.KIMI_API_KEY and self.KIMI_API_KEY != "your_kimi_api_key_here":
            providers.append("kimi")
        # 本地提供商：只要配置了 BASE_URL 即认为可用（默认端口也算）
        if self.LOCAL_BASE_URL:
            providers.append("local")
            
        return providers
    
    def is_provider_available(self, provider: str) -> bool:
        """检查指定提供商是否可用"""
        return provider in self.get_available_providers()
    
    def get_llm_config(self, provider: str = None):
        """从settings创建LLMConfig对象"""
        from backend.llm import LLMConfig, ModelProvider
        
        provider = provider or self.DEFAULT_LLM_PROVIDER
        provider = provider.lower()
        
        # 从环境变量读取通用参数，如果没有则使用默认值
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
        
        if provider == "openai":
            return LLMConfig(
                provider=ModelProvider.OPENAI,
                model_name=self.OPENAI_MODEL,
                api_key=self.OPENAI_API_KEY,
                base_url=self.OPENAI_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "deepseek":
            return LLMConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name=self.DEEPSEEK_MODEL,
                api_key=self.DEEPSEEK_API_KEY,
                base_url=self.DEEPSEEK_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "kimi":
            return LLMConfig(
                provider=ModelProvider.KIMI,
                model_name=self.KIMI_MODEL,
                api_key=self.KIMI_API_KEY,
                base_url=self.KIMI_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "qwen":
            return LLMConfig(
                provider=ModelProvider.QWEN,
                model_name=self.QWEN_MODEL,
                api_key=self.QWEN_API_KEY,
                base_url=self.QWEN_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "anthropic":
            return LLMConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name=self.ANTHROPIC_MODEL,
                api_key=self.ANTHROPIC_API_KEY,
                base_url=self.ANTHROPIC_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "google":
            return LLMConfig(
                provider=ModelProvider.GOOGLE,
                model_name=self.GOOGLE_MODEL,
                api_key=self.GOOGLE_API_KEY,
                base_url=self.GOOGLE_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "azure":
            return LLMConfig(
                provider=ModelProvider.AZURE,
                model_name=self.AZURE_MODEL,
                api_key=self.AZURE_API_KEY,
                base_url=self.AZURE_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )
        elif provider == "local":
            return LLMConfig(
                provider=ModelProvider.LOCAL,
                model_name=self.LOCAL_MODEL,
                api_key=self.LOCAL_API_KEY,
                base_url=self.LOCAL_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=60.0,
                # max_retries=2,
                # request_delay=0.0
            )
        else:
            # 兜底使用本地提供商
            return LLMConfig(
                provider=ModelProvider.LOCAL,
                model_name=self.LOCAL_MODEL,
                api_key=self.LOCAL_API_KEY,
                base_url=self.LOCAL_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0
            )

# Global settings instance
settings = Settings()
