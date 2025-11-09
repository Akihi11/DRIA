"""
状态评估计算模块测试文件
测试 StatusEvaluationCalculator 和 StatusEvaluationService
从外部配置文件和数据文件加载测试数据
"""
import sys
import logging
from pathlib import Path
import json
import pandas as pd

# --- 强制日志配置 [开始] ---
logging.getLogger().setLevel(logging.INFO)

# 清理掉所有旧的处理器
for handler in logging.getLogger().handlers[:]:
    logging.getLogger().removeHandler(handler)

# 添加一个新的、干净的处理器
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)
# --- 强制日志配置 [结束] ---

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent  # 回到DRIA目录
sys.path.insert(0, str(project_root))

# 导入状态评估模块
try:
    from backend.services.status_evaluation_calculator import (
        StatusEvaluationCalculator,
        StatusEvalConfig,
        EvaluationItem,
        EvaluationCondition
    )
    from backend.services.status_evaluation_service import StatusEvaluationService
    from backend.services.data_reader import DataReader
except ImportError as e:
    logging.error("="*60)
    logging.error("导入失败！")
    logging.error(f"错误信息: {str(e)}")
    logging.error(f"请确保相关模块文件位于正确位置")
    logging.error("="*60)
    sys.exit(1)

# 测试文件路径
TEST_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TEST_CONFIG_JSON = TEST_DATA_DIR / "config_session.json"
DEFAULT_TEST_DATA_CSV = TEST_DATA_DIR / "test_data.csv"
DEFAULT_TEST_OUTPUT_EXCEL = TEST_DATA_DIR / "test_output.xlsx"


def run_test(config_path=None, data_path=None, output_path=None):
    """
    运行状态评估计算测试
    
    Args:
        config_path: 配置文件路径（可选）
        data_path: 数据文件路径（可选）
        output_path: 输出文件路径（可选）
    """
    print("\n" + "="*60)
    print("状态评估计算模块测试")
    print("="*60)
    
    logger = logging.getLogger(__name__)
    
    # 确保数据目录存在
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    test_config_path = Path(config_path) if config_path else DEFAULT_TEST_CONFIG_JSON
    test_data_path = Path(data_path) if data_path else DEFAULT_TEST_DATA_CSV
    test_output_path = Path(output_path) if output_path else DEFAULT_TEST_OUTPUT_EXCEL
    
    # 1. 检查文件
    if not test_config_path.exists():
        logger.error(f"[错误] 配置文件不存在: {test_config_path}")
        logger.info(f"请创建配置文件: {test_config_path}")
        logger.info("配置文件格式请参考 samples/config_full.json 中的 statusEval 部分")
        return False
    if not test_data_path.exists():
        logger.error(f"[错误] 数据文件不存在: {test_data_path}")
        logger.info(f"请创建数据文件: {test_data_path}")
        logger.info("数据文件应为CSV格式，包含时间列（如 time[s]）和通道数据列")
        return False
    
    print(f"\n使用配置文件: {test_config_path}")
    print(f"使用数据文件: {test_data_path}")
    print(f"输出文件: {test_output_path}")
    
    print("\n开始运行状态评估计算...")
    
    try:
        # --- 2. 手动加载JSON配置 ---
        logger.info(f"正在加载 JSON 配置文件: {test_config_path}")
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        # 3. 解析配置（从 "reportConfig.statusEval" 键）
        report_config = config_dict.get('reportConfig', {})
        status_eval = report_config.get('statusEval', {})
        evaluations_config = status_eval.get('evaluations', [])
        
        if not evaluations_config:
            logger.error("JSON 格式错误: 未找到 'reportConfig.statusEval.evaluations' 键")
            return False
        
        # 获取评估内容描述映射
        assessment_content_map = status_eval.get('assessment_content_map', {})
        
        # 获取全局默认值
        default_type = status_eval.get('type', 'continuous_check')
        default_condition_logic = status_eval.get('conditionLogic', 'AND')
        
        # 解析评估项
        evaluations = []
        for eval_config in evaluations_config:
            # 跳过functional_result类型
            eval_type = eval_config.get('type', default_type)
            if eval_type == 'functional_result':
                logger.info(f"跳过functional_result类型评估项: {eval_config.get('item', 'unknown')}")
                continue
            
            condition_logic = eval_config.get('conditionLogic', default_condition_logic)
            
            # 兼容event_check类型（将其转换为continuous_check）
            if eval_type == 'event_check':
                condition_config = eval_config.get('condition', {})
                if condition_config:
                    conditions_config = [condition_config]
                eval_type = 'continuous_check'
            else:
                conditions_config = eval_config.get('conditions', [])
            
            # 解析条件
            conditions = []
            for cond_config in conditions_config:
                # 兼容event_check格式：使用type字段作为statistic
                statistic = cond_config.get('statistic') or cond_config.get('type', '平均值')
                
                # 标准化统计方法名称
                stat_lower = statistic.lower()
                if stat_lower in ['average', '平均值', 'mean', 'avg']:
                    normalized_stat = "平均值"
                elif stat_lower in ['max', '最大值', 'maximum']:
                    normalized_stat = "最大值"
                elif stat_lower in ['min', '最小值', 'minimum']:
                    normalized_stat = "最小值"
                elif stat_lower in ['rms', '有效值', 'rootmeansquare']:
                    normalized_stat = "有效值"
                elif stat_lower in ['instant', '瞬时值', 'instantaneous']:
                    normalized_stat = "瞬时值"
                elif stat_lower in ['difference', '差值', 'diff', '差值计算']:
                    normalized_stat = "difference"
                else:
                    logger.warning(f"未知的统计类型: {statistic}，使用平均值代替")
                    normalized_stat = "平均值"
                
                condition = EvaluationCondition(
                    channel=cond_config.get('channel', ''),
                    statistic=normalized_stat,
                    duration=cond_config.get('duration', 1.0),
                    logic=cond_config.get('logic', '>'),
                    threshold=cond_config.get('threshold', 0.0)
                )
                conditions.append(condition)
            
            # 构建评估项
            evaluation = EvaluationItem(
                item=eval_config.get('item', ''),
                assessment_name=eval_config.get('assessmentName', eval_config.get('item', '')),
                type=eval_type,
                condition_logic=condition_logic,
                conditions=conditions
            )
            evaluations.append(evaluation)
        
        # 创建配置对象
        config = StatusEvalConfig(evaluations=evaluations)
        logger.info(f"配置对象创建成功，评估项数量: {len(evaluations)}")
        
        # 4. 实例化计算器
        calculator = StatusEvaluationCalculator(config)
        
        # --- 5. 手动加载CSV并转换 ---
        logger.info(f"正在加载 CSV 数据文件: {test_data_path}")
        data_reader = DataReader()
        df = data_reader.read_file(str(test_data_path))
        
        # 查找时间列
        time_col = data_reader.find_time_column(df)
        if not time_col:
            logger.error("CSV中未找到时间列")
            return False
        
        logger.info(f"CSV 加载成功，总行数: {len(df)}, 时间列: {time_col}")
        
        # 提取需要的通道列表
        channels = set()
        for eval_item in config.evaluations:
            for condition in eval_item.conditions:
                if condition.channel:
                    channels.add(condition.channel)
        channels = list(channels)
        
        logger.info(f"需要读取的通道: {channels}")
        
        # 6. 转换数据流
        data_stream = data_reader.read_data_stream(str(test_data_path), channels)
        logger.info(f"数据流转换完成，总点数: {len(data_stream)}")
        
        # --- 7. 运行计算 ---
        logger.info("开始执行状态评估计算...")
        results = calculator.calculate(data_stream)
        
        # --- 8. 输出结果 ---
        print("\n" + "="*60)
        print("状态评估计算结果:")
        print("="*60)
        
        for eval_item in config.evaluations:
            item_id = eval_item.item
            result = results.get(item_id, "未知")
            print(f"\n评估项: {eval_item.assessment_name}")
            print(f"  结论: {result}")
            print(f"  类型: {eval_item.type}")
            print(f"  条件逻辑: {eval_item.condition_logic}")
            print(f"  条件数量: {len(eval_item.conditions)}")
            for idx, condition in enumerate(eval_item.conditions, 1):
                # 格式化duration显示
                if condition.duration is None:
                    duration_str = "瞬时"
                else:
                    duration_str = f"{condition.duration}s"
                print(f"    条件{idx}: {condition.channel} {condition.statistic} "
                      f"({duration_str}) {condition.logic} {condition.threshold}")
        
        # --- 9. 验证结果 ---
        print("\n" + "="*60)
        print("测试验证:")
        print("="*60)
        
        if len(results) > 0:
            print(f"[OK] 成功计算 {len(results)} 个评估项")
        else:
            print(f"[FAIL] 未计算任何评估项")
        
        # 检查是否有"否"的结果（表示触发了失败条件）
        failed_items = [item for item, result in results.items() if result == "否"]
        if failed_items:
            print(f"[INFO] 发现 {len(failed_items)} 个评估项触发失败条件:")
            for item in failed_items:
                print(f"      - {item}")
        else:
            print(f"[INFO] 所有评估项均通过（结论为'是'）")
        
        # --- 10. 可选：生成报表（如果ReportWriter可用）---
        try:
            from backend.services.report_writer import ReportWriter
            report_writer = ReportWriter()
            report_writer.create_status_eval_report(
                results,
                config.evaluations,
                str(test_output_path),
                assessment_content_map
            )
            print(f"\n[OK] 报表已生成: {test_output_path}")
        except Exception as e:
            logger.warning(f"生成报表失败（可选功能）: {str(e)}")
        
        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 可以修改这些路径
    success = run_test(
        config_path=DEFAULT_TEST_CONFIG_JSON,
        data_path=DEFAULT_TEST_DATA_CSV,
        output_path=DEFAULT_TEST_OUTPUT_EXCEL
    )
    sys.exit(0 if success else 1)

