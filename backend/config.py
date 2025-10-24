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
        self.DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
        
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
        self.LOCAL_MODEL: str = os.getenv("LOCAL_MODEL", "llama2")
        
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
        if self.LOCAL_BASE_URL and self.LOCAL_BASE_URL != "http://localhost:11434":
            providers.append("local")
            
        return providers
    
    def is_provider_available(self, provider: str) -> bool:
        """检查指定提供商是否可用"""
        return provider in self.get_available_providers()

# Global settings instance
settings = Settings()
