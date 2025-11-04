"""
功能计算模块测试文件 (V2 - 手动加载版)
直接测试 FunctionalCalculator，绕过 FunctionalService
"""
import sys
import logging
from pathlib import Path
import json
import pandas as pd

# --- 强制日志配置 [开始] ---

# 1. 把这里从 DEBUG 改回 INFO
logging.getLogger().setLevel(logging.INFO) 

# (可选) 清理掉所有旧的、可能在捣乱的处理器
for handler in logging.getLogger().handlers[:]:
    logging.getLogger().removeHandler(handler)

# 添加一个新的、干净的处理器
handler = logging.StreamHandler(sys.stdout)

# 2. 这里也从 DEBUG 改回 INFO
handler.setLevel(logging.INFO) 
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)
# --- 强制日志配置 [结束] ---

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent  # 回到DRIA目录
sys.path.insert(0, str(project_root))

# 现在再导入我们自己的模块
# (假设 functional_calculator.py 在 backend/services/ 目录下)
try:
    from backend.services.functional_calculator import FunctionalCalculator, FunctionalCalcConfig
except ImportError:
    logging.error("="*60)
    logging.error("导入失败！")
    logging.error(f"请确保 functional_calculator.py 文件位于: {project_root / 'backend' / 'services'}")
    logging.error("="*60)
    sys.exit(1)


# 测试文件路径
TEST_DATA_DIR = project_root / "backend" / "tests" / "test_data"
DEFAULT_TEST_DATA_CSV = TEST_DATA_DIR / "test.csv"
DEFAULT_TEST_CONFIG_JSON = TEST_DATA_DIR / "test001.json"
DEFAULT_TEST_OUTPUT_EXCEL = TEST_DATA_DIR / "test.xlsx"


def run_test(config_path=None, data_path=None, output_path=None):
    """
    运行功能计算测试
    """
    print("\n" + "="*60)
    print("功能计算模块测试 (V2 - 手动加载版)")
    print("="*60)
    
    logger = logging.getLogger(__name__) # 获取 logger
    
    test_config_path = Path(config_path) if config_path else DEFAULT_TEST_CONFIG_JSON
    test_data_path = Path(data_path) if data_path else DEFAULT_TEST_DATA_CSV
    test_output_path = Path(output_path) if output_path else DEFAULT_TEST_OUTPUT_EXCEL
    
    # 1. 检查文件
    if not test_config_path.exists():
        logger.error(f"[错误] 配置文件不存在: {test_config_path}")
        return False
    if not test_data_path.exists():
        logger.error(f"[错误] 数据文件不存在: {test_data_path}")
        return False
    
    print(f"\n使用配置文件: {test_config_path}")
    print(f"使用数据文件: {test_data_path}")
    print(f"输出文件: {test_output_path}")
    
    print("\n开始运行功能计算...")
    
    try:
        # --- 2. 手动加载JSON ---
        logger.debug(f"正在加载 JSON 配置文件: {test_config_path}")
        with open(test_config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        # 3. 实例化配置类 (从 "functionalCalc" 键)
        calc_config_data = config_dict.get('functionalCalc')
        if not calc_config_data:
            logger.error(f"JSON 格式错误: 未找到 'functionalCalc' 键")
            return False
            
        config = FunctionalCalcConfig(
            time_base=calc_config_data.get('time_base'),
            startup_time=calc_config_data.get('startup_time'),
            ignition_time=calc_config_data.get('ignition_time'),
            rundown_ng=calc_config_data.get('rundown_ng'),
            rundown_np=calc_config_data.get('rundown_np')
        )
        logger.debug("配置对象创建成功")

        # 4. 实例化计算器
        calculator = FunctionalCalculator(config)
        
        # --- 5. 手动加载CSV并转换 ---
        logger.debug(f"正在加载 CSV 数据文件: {test_data_path}")
        df = pd.read_csv(test_data_path)
        
        # 确定时间列 (假设叫 'time[s]')
        time_col = 'time[s]'
        if time_col not in df.columns:
            logger.error(f"CSV中未找到时间列: '{time_col}'")
            return False
        
        logger.debug(f"CSV 加载成功，总行数: {len(df)}")
        
        # 6. 转换数据流
        data_stream = []
        for row in df.to_dict('records'):
            timestamp = row.pop(time_col)
            data_stream.append((timestamp, row))
        
        logger.debug(f"数据流转换完成，总点数: {len(data_stream)}")

        # --- 7. 运行计算 ---
        calculator.process_data_stream(data_stream)

        # --- 8. 导出Excel ---
        calculator.export_to_excel(str(test_output_path))
        
        print(f"\n功能计算完成！")
        print(f"输出文件: {test_output_path}")
        
        # --- 9. 验证结果 (这部分不变) ---
        print("\n验证计算结果...")
        results = calculator.results
        
        print(f"\n识别到 {len(results)} 个循环:")
        for i, row in enumerate(results, 1):
            print(f"\n循环 {i}:")
            print(f"  启动次数: {row['startup_count']}")
            print(f"  时间（基准）: {row['time_base']:.2f} 秒" if row['time_base'] else "  时间（基准）: 未计算")
            print(f"  启动时间: {row['startup_time']:.2f} 秒" if row['startup_time'] else "  启动时间: 未计算")
            print(f"  点火时间: {row['ignition_time']:.2f} 秒" if row['ignition_time'] else "  点火时间: 未计算")
            print(f"  Ng余转时间: {row['ng_rundown']:.2f} 秒" if row['ng_rundown'] else "  Ng余转时间: 未计算")
            print(f"  Np余转时间: {row['np_rundown']:.2f} 秒" if row['np_rundown'] else "  Np余转时间: 未计算")
        
        print("\n" + "="*60)
        print("测试验证:")
        print("="*60)
        
        if len(results) >= 1:
            print(f"[OK] 成功识别到 {len(results)} 个循环")
        else:
            print(f"[FAIL] 未识别到任何循环")
        
        if results:
            first_cycle = results[0]
            checks = []
            if first_cycle['time_base'] is not None:
                checks.append(("[OK] 第一个循环: 时间（基准）已计算", True))
            else:
                checks.append(("[FAIL] 第一个循环: 时间（基准）未计算", False))
            if first_cycle['startup_time'] is not None:
                checks.append(("[OK] 第一个循环: 启动时间已计算", True))
            else:
                checks.append(("[FAIL] 第一个循环: 启动时间未计算", False))
            
            # ... (其他检查) ...
            
            for msg, passed in checks:
                print(msg)
        
        print("\n" + "="*60)
        print("测试完成！")
        print(f"详细结果请查看: {test_output_path}")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 你可以修改这些路径
    success = run_test(
        config_path=DEFAULT_TEST_CONFIG_JSON,
        data_path=DEFAULT_TEST_DATA_CSV,
        output_path=DEFAULT_TEST_OUTPUT_EXCEL
    )
    sys.exit(0 if success else 1)