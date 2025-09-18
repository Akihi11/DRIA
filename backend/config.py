"""
Configuration module for the AI Report Generation Backend
"""
import os
from pathlib import Path
from typing import Optional

class Settings:
    """Application settings"""
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # File Upload Configuration
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: set = {".csv", ".xlsx", ".xls"}
    
    # Report Output Configuration
    REPORT_OUTPUT_DIR: Path = Path(os.getenv("REPORT_OUTPUT_DIR", "./reports"))
    
    # Report Sub-directories
    REPORT_SUBDIRS = {
        "api_generated": "api_generated",      # API生成的报表
        "golden_standard": "golden_standard",  # Golden Standard报表
        "test_reports": "test_reports",        # 测试生成的报表
        "manual_reports": "manual_reports",    # 手动生成的报表
        "archived": "archived"                 # 归档报表
    }
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create report sub-directories
        for subdir_name in self.REPORT_SUBDIRS.values():
            subdir_path = self.REPORT_OUTPUT_DIR / subdir_name
            subdir_path.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
