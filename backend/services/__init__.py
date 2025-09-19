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

# Import dialogue services - Phase 3: Use Real Implementation
try:
    from .real_dialogue_service import RealDialogueManager
    from .real_nlu_processor import RealNluProcessor
    from .real_rule_provider import RealRuleProvider

    # Use real dialogue implementations
    DialogueManager = RealDialogueManager
    NluProcessor = RealNluProcessor
    RuleProvider = RealRuleProvider

    DIALOGUE_IMPLEMENTATION_TYPE = "REAL_ENHANCED"

except ImportError as e:
    try:
        # Fallback to basic real implementations
        from .real_dialogue_service import RealDialogueManager, RealNluProcessor, RealRuleProvider

        DialogueManager = RealDialogueManager
        NluProcessor = RealNluProcessor
        RuleProvider = RealRuleProvider

        DIALOGUE_IMPLEMENTATION_TYPE = "REAL_BASIC"

    except ImportError as e2:
        # Final fallback to mock implementations
        from .mock_dialogue_service import MockDialogueManager, MockNluProcessor, MockRuleProvider

        DialogueManager = MockDialogueManager
        NluProcessor = MockNluProcessor
        RuleProvider = MockRuleProvider

        DIALOGUE_IMPLEMENTATION_TYPE = "MOCK"
        print(f"Warning: Using mock dialogue implementations due to: {e2}")

__all__ = [
    # Data Services (Real or Mock)
    "DataReader",
    "ReportWriter",
    
    # Analysis Services (Real or Mock)
    "StableStateAnalyzer",
    "ReportCalculationEngine",
    
    # Dialogue Services (Real or Mock)
    "DialogueManager",
    "NluProcessor", 
    "RuleProvider",
    
    # Implementation info
    "IMPLEMENTATION_TYPE"
]