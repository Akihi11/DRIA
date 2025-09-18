"""
Script to create golden standard test report for Phase 2 validation
This script generates a reference report that will be used for validation
"""
import json
import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.real_data_service import RealDataReader, RealReportWriter
from services.real_analysis_service import RealReportCalculationEngine
from models.report_config import ReportConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_golden_standard_report():
    """Create golden standard report using sample data and configuration"""
    
    # Paths
    project_root = Path(__file__).parent.parent.parent
    sample_data_path = project_root / "samples" / "Simulated_Data.csv"
    sample_config_path = project_root / "samples" / "config_full.json"
    golden_report_path = project_root / "tests" / "golden_standard_report.xlsx"
    golden_metadata_path = project_root / "tests" / "golden_standard_metadata.json"
    
    logger.info("Creating golden standard report...")
    logger.info(f"Sample data: {sample_data_path}")
    logger.info(f"Sample config: {sample_config_path}")
    logger.info(f"Output report: {golden_report_path}")
    
    try:
        # Step 1: Load configuration
        if not sample_config_path.exists():
            raise FileNotFoundError(f"Sample configuration not found: {sample_config_path}")
        
        with open(sample_config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        # Update source file ID to match actual file
        config_dict["sourceFileId"] = str(sample_data_path)
        
        config = ReportConfig(**config_dict)
        logger.info(f"Loaded configuration with sections: {config.report_config.sections}")
        
        # Step 2: Read data
        if not sample_data_path.exists():
            raise FileNotFoundError(f"Sample data file not found: {sample_data_path}")
        
        data_reader = RealDataReader()
        
        # Get file metadata
        file_metadata = data_reader.get_file_metadata(str(sample_data_path))
        logger.info(f"Data file metadata: {file_metadata['total_samples']} samples, "
                   f"{file_metadata['duration_seconds']:.2f}s duration")
        
        # Get available channels
        available_channels = data_reader.get_available_channels(str(sample_data_path))
        logger.info(f"Available channels: {available_channels}")
        
        # Determine required channels based on configuration
        required_channels = set()
        
        if config.report_config.stable_state:
            required_channels.update(config.report_config.stable_state.display_channels)
            # Handle both single condition and multiple conditions
            if hasattr(config.report_config.stable_state, 'conditions') and config.report_config.stable_state.conditions:
                for condition in config.report_config.stable_state.conditions:
                    required_channels.add(condition.channel)
            elif hasattr(config.report_config.stable_state, 'condition') and config.report_config.stable_state.condition:
                required_channels.add(config.report_config.stable_state.condition.channel)
        
        if config.report_config.functional_calc:
            for metric_config in config.report_config.functional_calc.model_dump().values():
                if isinstance(metric_config, dict) and 'channel' in metric_config:
                    required_channels.add(metric_config['channel'])
        
        if config.report_config.status_eval:
            for evaluation in config.report_config.status_eval.evaluations:
                if hasattr(evaluation, 'channel') and evaluation.channel:
                    required_channels.add(evaluation.channel)
        
        # Map configuration channels to available channels
        channel_mapping = {}
        for req_channel in required_channels:
            if req_channel in available_channels:
                channel_mapping[req_channel] = req_channel
            else:
                # Try to find similar channel names
                base_name = req_channel.split('(')[0]  # Extract "Ng" from "Ng(rpm)"
                for avail_channel in available_channels:
                    if base_name in avail_channel or avail_channel in base_name:
                        channel_mapping[req_channel] = avail_channel
                        break
                else:
                    # Try mapping based on common patterns
                    if 'temperature' in req_channel.lower() or '温度' in req_channel.lower():
                        for avail_channel in available_channels:
                            if '排气温度' in avail_channel or 'temperature' in avail_channel.lower():
                                channel_mapping[req_channel] = avail_channel
                                break
                    elif 'pressure' in req_channel.lower() or '压力' in req_channel.lower():
                        for avail_channel in available_channels:
                            if '滑油压力' in avail_channel or 'pressure' in avail_channel.lower():
                                channel_mapping[req_channel] = avail_channel
                                break
                    else:
                        # Try to find similar channel by keywords
                        for avail_channel in available_channels:
                            if any(keyword in avail_channel.lower() for keyword in req_channel.lower().split('(')):
                                channel_mapping[req_channel] = avail_channel
                                break
        
        logger.info(f"Channel mapping: {channel_mapping}")
        
        # Create a modified configuration with actual channel names
        import copy
        config_dict_copy = copy.deepcopy(config_dict)
        
        # Update stable state channel names
        if 'stableState' in config_dict_copy['reportConfig']:
            stable_config = config_dict_copy['reportConfig']['stableState']
            if 'displayChannels' in stable_config:
                stable_config['displayChannels'] = [
                    channel_mapping.get(ch, ch) for ch in stable_config['displayChannels']
                ]
            if 'conditions' in stable_config:
                for condition in stable_config['conditions']:
                    if 'channel' in condition:
                        condition['channel'] = channel_mapping.get(condition['channel'], condition['channel'])
        
        # Update functional calc channel names
        if 'functionalCalc' in config_dict_copy['reportConfig']:
            func_config = config_dict_copy['reportConfig']['functionalCalc']
            for metric_name, metric_config in func_config.items():
                if isinstance(metric_config, dict) and 'channel' in metric_config:
                    metric_config['channel'] = channel_mapping.get(metric_config['channel'], metric_config['channel'])
        
        # Update status eval channel names  
        if 'statusEval' in config_dict_copy['reportConfig']:
            status_config = config_dict_copy['reportConfig']['statusEval']
            if 'evaluations' in status_config:
                for evaluation in status_config['evaluations']:
                    if 'channel' in evaluation:
                        evaluation['channel'] = channel_mapping.get(evaluation['channel'], evaluation['channel'])
                    if 'conditions' in evaluation:
                        for condition in evaluation['conditions']:
                            if 'channel' in condition:
                                condition['channel'] = channel_mapping.get(condition['channel'], condition['channel'])
                    if 'condition' in evaluation and 'channel' in evaluation['condition']:
                        evaluation['condition']['channel'] = channel_mapping.get(evaluation['condition']['channel'], evaluation['condition']['channel'])
        
        # Create new config with mapped channel names
        config = ReportConfig(**config_dict_copy)
        
        # Read actual channels
        channels_to_read = list(channel_mapping.values())
        channels_to_read = [ch for ch in channels_to_read if ch]  # Remove None values
        channel_data = data_reader.read(str(sample_data_path), channels_to_read)
        
        logger.info(f"Successfully read {len(channel_data)} channels")
        for channel in channel_data:
            logger.info(f"  {channel.channel_name}: {len(channel.data_points)} points")
        
        # Step 3: Generate report
        calculation_engine = RealReportCalculationEngine()
        
        # Generate report directly (skip validation since we've mapped channels)
        report_data = calculation_engine.generate(channel_data, config)
        
        logger.info(f"Generated report: {report_data.report_id}")
        
        # Log results summary
        if report_data.stable_state_result:
            logger.info(f"Stable state: {len(report_data.stable_state_result.stable_periods)} periods, "
                       f"total time {report_data.stable_state_result.total_stable_time:.2f}s")
        
        if report_data.functional_calc_result:
            func_results = []
            if report_data.functional_calc_result.time_base:
                func_results.append(f"time_base={report_data.functional_calc_result.time_base:.2f}s")
            if report_data.functional_calc_result.startup_time:
                func_results.append(f"startup_time={report_data.functional_calc_result.startup_time:.2f}s")
            if report_data.functional_calc_result.ignition_time:
                func_results.append(f"ignition_time={report_data.functional_calc_result.ignition_time:.2f}s")
            if report_data.functional_calc_result.rundown_ng:
                func_results.append(f"rundown_ng={report_data.functional_calc_result.rundown_ng:.2f}s")
            
            logger.info(f"Functional calc: {', '.join(func_results)}")
        
        if report_data.status_eval_result:
            logger.info(f"Status evaluation: {report_data.status_eval_result.overall_status}, "
                       f"{len(report_data.status_eval_result.warnings)} warnings")
        
        # Step 4: Write Excel report to golden_standard subdirectory
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from config import settings
        
        # Create golden standard subdirectory path
        golden_subdir = settings.REPORT_OUTPUT_DIR / settings.REPORT_SUBDIRS["golden_standard"]
        golden_subdir.mkdir(parents=True, exist_ok=True)
        
        # Update output path to golden standard subdirectory
        golden_report_path = golden_subdir / "golden_standard_report.xlsx"
        
        report_writer = RealReportWriter()
        success = report_writer.write(str(golden_report_path), report_data)
        
        if success:
            logger.info(f"Golden standard report created: {golden_report_path}")
            logger.info(f"File size: {golden_report_path.stat().st_size} bytes")
        else:
            raise RuntimeError("Failed to create golden standard report")
        
        # Step 5: Save metadata for validation
        golden_metadata = {
            "report_id": report_data.report_id,
            "source_file_id": report_data.source_file_id,
            "generation_time": report_data.generation_time.isoformat(),
            "file_metadata": file_metadata,
            "channel_mapping": channel_mapping,
            "available_channels": available_channels,
            "channels_read": [ch.channel_name for ch in channel_data],
            "data_points_per_channel": {ch.channel_name: len(ch.data_points) for ch in channel_data},
            "results_summary": {
                "stable_state": {
                    "total_stable_time": report_data.stable_state_result.total_stable_time if report_data.stable_state_result else None,
                    "stable_periods_count": len(report_data.stable_state_result.stable_periods) if report_data.stable_state_result else 0
                } if report_data.stable_state_result else None,
                "functional_calc": {
                    "time_base": report_data.functional_calc_result.time_base,
                    "startup_time": report_data.functional_calc_result.startup_time,
                    "ignition_time": report_data.functional_calc_result.ignition_time,
                    "rundown_ng": report_data.functional_calc_result.rundown_ng
                } if report_data.functional_calc_result else None,
                "status_eval": {
                    "overall_status": report_data.status_eval_result.overall_status,
                    "evaluations_count": len(report_data.status_eval_result.evaluations),
                    "warnings_count": len(report_data.status_eval_result.warnings)
                } if report_data.status_eval_result else None
            }
        }
        
        with open(golden_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(golden_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Golden standard metadata saved: {golden_metadata_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating golden standard report: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_golden_standard():
    """Validate the created golden standard report"""
    
    project_root = Path(__file__).parent.parent.parent
    golden_report_path = project_root / "tests" / "golden_standard_report.xlsx"
    golden_metadata_path = project_root / "tests" / "golden_standard_metadata.json"
    
    logger.info("Validating golden standard report...")
    
    try:
        # Check files exist
        if not golden_report_path.exists():
            raise FileNotFoundError(f"Golden standard report not found: {golden_report_path}")
        
        if not golden_metadata_path.exists():
            raise FileNotFoundError(f"Golden standard metadata not found: {golden_metadata_path}")
        
        # Load and validate metadata
        with open(golden_metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        required_fields = [
            "report_id", "source_file_id", "generation_time",
            "file_metadata", "channel_mapping", "results_summary"
        ]
        
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field in metadata: {field}")
        
        # Validate report file
        file_size = golden_report_path.stat().st_size
        if file_size == 0:
            raise ValueError("Golden standard report file is empty")
        
        logger.info(f"Golden standard validation passed:")
        logger.info(f"  Report file: {file_size} bytes")
        logger.info(f"  Channels processed: {len(metadata['channels_read'])}")
        logger.info(f"  Total data points: {sum(metadata['data_points_per_channel'].values())}")
        
        # Log results summary
        results = metadata['results_summary']
        if results['stable_state']:
            logger.info(f"  Stable state: {results['stable_state']['stable_periods_count']} periods")
        if results['functional_calc']:
            func_metrics = [k for k, v in results['functional_calc'].items() if v is not None]
            logger.info(f"  Functional calc: {len(func_metrics)} metrics calculated")
        if results['status_eval']:
            logger.info(f"  Status eval: {results['status_eval']['overall_status']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Golden standard validation failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Golden Standard Report Generator")
    print("=" * 60)
    print()
    
    # Create golden standard
    success = create_golden_standard_report()
    
    if success:
        print("\n" + "=" * 60)
        print("Validating Golden Standard")
        print("=" * 60)
        
        # Validate golden standard
        validation_success = validate_golden_standard()
        
        if validation_success:
            print("\nGolden standard report created and validated successfully!")
            print("\nFiles created:")
            print("  - tests/golden_standard_report.xlsx")
            print("  - tests/golden_standard_metadata.json")
            print("\nThis golden standard can now be used for Phase 2 validation.")
        else:
            print("\nGolden standard validation failed!")
            sys.exit(1)
    else:
        print("\nFailed to create golden standard report!")
        sys.exit(1)
