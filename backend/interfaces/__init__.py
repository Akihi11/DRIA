"""
Core interfaces and abstract base classes for the AI Report Generation system
"""

from .data_interfaces import DataReader, ReportWriter
from .analysis_interfaces import Analyzer, ReportCalculationEngine
from .dialogue_interfaces import DialogueManager, NluProcessor, RuleProvider

__all__ = [
    # Data Service Interfaces
    "DataReader",
    "ReportWriter",
    
    # Analysis Engine Interfaces
    "Analyzer", 
    "ReportCalculationEngine",
    
    # Dialogue Management Interfaces
    "DialogueManager",
    "NluProcessor", 
    "RuleProvider"
]
