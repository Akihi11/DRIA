"""
Service layer implementations - Python 3.12 compatible
Contains mock implementations of core services for Phase 1
"""

from .mock_data_service_py312 import MockDataReader, MockReportWriter
from .mock_dialogue_service import MockDialogueManager, MockNluProcessor, MockRuleProvider  
from .mock_analysis_service import MockReportCalculationEngine, MockStableStateAnalyzer

__all__ = [
    # Data Services
    "MockDataReader",
    "MockReportWriter",
    
    # Dialogue Services  
    "MockDialogueManager",
    "MockNluProcessor",
    "MockRuleProvider",
    
    # Analysis Services
    "MockReportCalculationEngine", 
    "MockStableStateAnalyzer"
]
