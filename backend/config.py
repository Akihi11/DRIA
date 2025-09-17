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
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
