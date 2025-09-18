"""
Service layer implementations
Phase 2: Real implementations with fallback to mock for compatibility
"""

# Try to import real implementations first
try:
    from .real_data_service import RealDataReader, RealReportWriter
    from .real_analysis_service import (
        RealStableStateAnalyzer, RealFunctionalAnalyzer, 
        RealStatusEvaluator, RealReportCalculationEngine
    )
    
    # Use real implementations as primary
    DataReader = RealDataReader
    ReportWriter = RealReportWriter
    StableStateAnalyzer = RealStableStateAnalyzer
    FunctionalAnalyzer = RealFunctionalAnalyzer
    StatusEvaluator = RealStatusEvaluator
    ReportCalculationEngine = RealReportCalculationEngine
    
    IMPLEMENTATION_TYPE = "REAL"
    
except ImportError as e:
    # Fallback to mock implementations if dependencies missing
    from .mock_data_service import MockDataReader, MockReportWriter
    from .mock_analysis_service import (
        MockStableStateAnalyzer, MockReportCalculationEngine
    )
    
    # Use mock implementations as fallback
    DataReader = MockDataReader
    ReportWriter = MockReportWriter
    StableStateAnalyzer = MockStableStateAnalyzer
    ReportCalculationEngine = MockReportCalculationEngine
    
    IMPLEMENTATION_TYPE = "MOCK"
    print(f"Warning: Using mock implementations due to missing dependencies: {e}")

# Import dialogue services (always use mock for now)
from .mock_dialogue_service import MockDialogueManager, MockNluProcessor, MockRuleProvider

__all__ = [
    # Data Services (Real or Mock)
    "DataReader",
    "ReportWriter",
    
    # Analysis Services (Real or Mock)
    "StableStateAnalyzer",
    "ReportCalculationEngine",
    
    # Dialogue Services (Mock)
    "MockDialogueManager",
    "MockNluProcessor", 
    "MockRuleProvider",
    
    # Implementation info
    "IMPLEMENTATION_TYPE"
]