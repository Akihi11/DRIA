"""
API module for the AI Report Generation system
Contains all REST API endpoints and routing logic
"""

from .main import app
from .routes import *

__all__ = ["app"]
