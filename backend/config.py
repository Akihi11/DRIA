"""
Configuration module for the AI Report Generation Backend
"""
import os
from pathlib import Path
from typing import Optional

class Settings:
    """Application settings"""
    
    def __init__(self):
        # API Configuration
        self.API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
        self.API_PORT: int = int(os.getenv("API_PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
        
        # File Upload Configuration
        # 使用 __file__ 的绝对路径来确保总是获取正确的路径
        # resolve() 会返回规范化的绝对路径，不依赖当前工作目录
        backend_dir = Path(__file__).resolve().parent
        
        # 使用 resolve() 确保获取真实的绝对路径
        upload_dir_default = (backend_dir / "uploads").resolve()
        report_dir_default = (backend_dir / "reports").resolve()
        
        # 如果有环境变量，也要 resolve()
        upload_env = os.getenv("UPLOAD_DIR", "")
        if upload_env:
            self.UPLOAD_DIR: Path = Path(upload_env).resolve()
        else:
            self.UPLOAD_DIR: Path = upload_dir_default
            
        self.MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
        self.ALLOWED_EXTENSIONS: set = {".csv", ".xlsx", ".xls"}
        
        # Report Output Configuration
        report_env = os.getenv("REPORT_OUTPUT_DIR", "")
        if report_env:
            self.REPORT_OUTPUT_DIR: Path = Path(report_env).resolve()
        else:
            self.REPORT_OUTPUT_DIR: Path = report_dir_default
        
        # Report Sub-directories
        self.REPORT_SUBDIRS = {
            "api_generated": "api_generated",      # API生成的报表
            "golden_standard": "golden_standard",  # Golden Standard报表
            "test_reports": "test_reports",        # 测试生成的报表
            "manual_reports": "manual_reports",    # 手动生成的报表
            "archived": "archived"                 # 归档报表
        }
        
        # Logging Configuration
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create report sub-directories
        for subdir_name in self.REPORT_SUBDIRS.values():
            subdir_path = self.REPORT_OUTPUT_DIR / subdir_name
            subdir_path.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
