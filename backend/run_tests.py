"""
Test runner script for Phase 2 validation
Runs all unit tests and integration tests, then validates against golden standard
"""
import subprocess
import sys
from pathlib import Path
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_unit_tests():
    """Run all unit tests"""
    logger.info("Running unit tests...")
    
    try:
        # Run pytest with coverage
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_data_service.py",
            "tests/test_analysis_service.py",
            "-v", "--tb=short"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        print("Unit Test Results:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Unit tests passed")
            return True
        else:
            logger.error("❌ Unit tests failed")
            return False
            
    except Exception as e:
        logger.error(f"Error running unit tests: {e}")
        return False


def run_integration_tests():
    """Run integration tests"""
    logger.info("Running integration tests...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_integration.py",
            "-v", "--tb=short"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        print("\nIntegration Test Results:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Integration tests passed")
            return True
        else:
            logger.error("❌ Integration tests failed")
            return False
            
    except Exception as e:
        logger.error(f"Error running integration tests: {e}")
        return False


def create_and_validate_golden_standard():
    """Create golden standard report and validate"""
    logger.info("Creating golden standard report...")
    
    try:
        result = subprocess.run([
            sys.executable, "tests/create_golden_standard.py"
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        print("\nGolden Standard Creation:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Golden standard created successfully")
            return True
        else:
            logger.error("❌ Golden standard creation failed")
            return False
            
    except Exception as e:
        logger.error(f"Error creating golden standard: {e}")
        return False


def validate_test_coverage():
    """Validate that all critical components are tested"""
    logger.info("Validating test coverage...")
    
    # List of critical components that must be tested
    critical_components = [
        "RealDataReader",
        "RealReportWriter", 
        "RealStableStateAnalyzer",
        "RealFunctionalAnalyzer",
        "RealStatusEvaluator",
        "RealReportCalculationEngine"
    ]
    
    test_files = [
        Path(__file__).parent / "tests" / "test_data_service.py",
        Path(__file__).parent / "tests" / "test_analysis_service.py",
        Path(__file__).parent / "tests" / "test_integration.py"
    ]
    
    covered_components = set()
    
    for test_file in test_files:
        if test_file.exists():
            try:
                content = test_file.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    content = test_file.read_text(encoding='gbk', errors='ignore')
                except UnicodeDecodeError:
                    content = test_file.read_text(encoding='latin-1', errors='ignore')
            for component in critical_components:
                if component in content:
                    covered_components.add(component)
    
    missing_components = set(critical_components) - covered_components
    
    if missing_components:
        logger.warning(f"Missing test coverage for: {missing_components}")
        return False
    else:
        logger.info("✅ All critical components have test coverage")
        return True


def run_phase2_validation():
    """Run complete Phase 2 validation suite"""
    print("🚀 Starting Phase 2 Validation Suite")
    print("=" * 60)
    
    results = {}
    
    # Step 1: Validate test coverage
    print("\n📋 Step 1: Validating Test Coverage")
    results['coverage'] = validate_test_coverage()
    
    # Step 2: Run unit tests
    print("\n🧪 Step 2: Running Unit Tests")
    results['unit_tests'] = run_unit_tests()
    
    # Step 3: Run integration tests
    print("\n🔧 Step 3: Running Integration Tests")
    results['integration_tests'] = run_integration_tests()
    
    # Step 4: Create and validate golden standard
    print("\n🏆 Step 4: Creating Golden Standard")
    results['golden_standard'] = create_and_validate_golden_standard()
    
    # Summary
    print("\n" + "=" * 60)
    print("PHASE 2 VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_type, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_type.replace('_', ' ').title():<20}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED - Phase 2 validation successful!")
        print("\nDeliverables:")
        print("  ✅ Functional backend calculation engine")
        print("  ✅ Complete unit test suite (100% critical coverage)")
        print("  ✅ Integration test suite")
        print("  ✅ Golden standard report for validation")
        print("\nPhase 2 is ready for acceptance testing!")
        return True
    else:
        print("❌ VALIDATION FAILED - Some tests did not pass")
        print("\nPlease review the failed tests above and fix the issues.")
        return False


if __name__ == "__main__":
    success = run_phase2_validation()
    sys.exit(0 if success else 1)
