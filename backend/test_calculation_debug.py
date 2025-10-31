#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试计算模块 - 不写Excel，只打印计算结果
"""

import json
import sys
import os
from pathlib import Path
from collections import deque
from datetime import datetime

# 设置UTF-8编码环境变量（Windows）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目根目录到路径
backend_dir = Path(__file__).parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

try:
    from backend.services.steady_state_service import SteadyStateService
    from backend.services.data_reader import DataReader
    from backend.services.steady_state_calculator import SteadyStateCalculator, StableStateConfig, TriggerConfig
    from backend.services.report_writer import ReportWriter
except ImportError as e:
    print(f"导入错误: {e}")
    print(f"Python路径: {sys.path}")
    raise


def print_separator(text=""):
    """打印分隔线"""
    print("\n" + "=" * 80)
    if text:
        print(f"  {text}")
        print("=" * 80)
    print()


def test_data_reading(config_path: Path, data_file: Path):
    """测试数据读取"""
    print_separator("1. 测试数据读取")
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    report_config = config_data.get('reportConfig', {})
    stable_state = report_config.get('stableState', {})
    display_channels = stable_state.get('displayChannels', [])
    
    print(f"显示通道: {display_channels}")
    
    # 读取数据
    data_reader = DataReader()
    data_stream = data_reader.read_data_stream(str(data_file), display_channels)
    
    print(f"总数据点数: {len(data_stream)}")
    print(f"\n前5个数据点:")
    for i, (timestamp, values) in enumerate(data_stream[:5]):
        print(f"  {i+1}. time={timestamp:.3f}s, Ng={values.get('Ng', 'N/A'):.2f}")
    
    print(f"\n后5个数据点:")
    for i, (timestamp, values) in enumerate(data_stream[-5:]):
        print(f"  {i+1}. time={timestamp:.3f}s, Ng={values.get('Ng', 'N/A'):.2f}")
    
    # 检查Ng值的范围
    ng_values = [values.get('Ng', 0) for _, values in data_stream]
    print(f"\nNg值统计:")
    print(f"  最小值: {min(ng_values):.2f}")
    print(f"  最大值: {max(ng_values):.2f}")
    print(f"  平均值: {sum(ng_values)/len(ng_values):.2f}")
    ng_gt_2000 = sum(1 for v in ng_values if v > 2000)
    print(f"  > 2000的点数: {ng_gt_2000} / {len(ng_values)} ({ng_gt_2000/len(ng_values)*100:.2f}%)")
    
    return data_stream, display_channels


def print_detailed_calculation_first_20(data_stream, config):
    """打印前20条数据点的详细计算过程"""
    print_separator("前20条数据点的详细计算过程")
    
    calculator = SteadyStateCalculator(config)
    
    # 获取条件1配置
    cond1 = config.trigger_logic.condition1
    if not cond1:
        print("[错误] 条件1未配置")
        return
    
    channel = cond1.get('channel')
    statistic = cond1.get('statistic', 'Average')
    duration_sec = cond1.get('duration_sec', 1.0)
    logic = cond1.get('logic', '>')
    threshold = cond1.get('threshold', 0)
    
    print(f"条件1配置:")
    print(f"  通道: {channel}")
    print(f"  统计方法: {statistic}")
    print(f"  窗口时长: {duration_sec}s")
    print(f"  逻辑: {logic}")
    print(f"  阈值: {threshold}")
    print()
    
    # 详细输出前20条
    print("\n" + "=" * 140)
    print(f"{'索引':<6} {'时间(s)':<12} {'当前Ng':<12} {'窗口大小':<10} {'统计值':<12} {'窗口最小值':<12} {'窗口最大值':<12} {'条件':<10}")
    print("=" * 140)
    
    for idx in range(min(20, len(data_stream))):
        current_time, data_point = data_stream[idx]
        current_ng = data_point.get(channel, 0)
        
        # 检查条件1（check_condition1会自动处理窗口初始化）
        cond1_met, current_stat = calculator.check_condition1(current_time, data_point)
        
        # 获取窗口大小
        if calculator.window_cond1 is not None:
            window_size = len(calculator.window_cond1)
        else:
            window_size = 0
        
        # 获取窗口信息
        if window_size > 0:
            window_values = [item[1] for item in calculator.window_cond1]
            window_min = min(window_values)
            window_max = max(window_values)
        else:
            window_min = 0.0
            window_max = 0.0
        
        # 条件状态
        condition_status = "[满足]" if cond1_met else "[不满足]"
        
        print(f"{idx:<6} {current_time:<12.3f} {current_ng:<12.2f} {window_size:<10} "
              f"{current_stat:<12.2f} {window_min:<12.2f} {window_max:<12.2f} {condition_status:<10}")
        
        # 如果是窗口第一次填充或窗口大小达到100，显示窗口详细信息
        if window_size > 0 and (window_size == 1 or window_size == 100 or idx < 5):
            window_values = [item[1] for item in calculator.window_cond1]
            if window_size <= 20:
                window_values_str = ', '.join([f"{v:.2f}" for v in window_values])
            else:
                first_5 = [f"{v:.2f}" for v in window_values[:5]]
                last_5 = [f"{v:.2f}" for v in window_values[-5:]]
                window_values_str = f"{', '.join(first_5)}..., {', '.join(last_5)}"
            
            print(f"      窗口值: [{window_values_str}]")
            print(f"      计算: {statistic}(窗口) = {current_stat:.2f}, 判断: {current_stat:.2f} {logic} {threshold} = {cond1_met}")
            print()
        
        # 更新状态
        if calculator.window_cond1 is not None:
            calculator.cond1_last_state = cond1_met
    
    print()
    print("详细说明:")
    print("  - 统计值：使用配置的统计方法（" + statistic + "）计算窗口内所有值的统计值")
    print("  - 条件：判断 统计值 " + logic + " " + str(threshold) + " 是否成立")
    print("  - 窗口值样本：窗口内数值的样本，用于查看窗口内容")


def test_calculation(config_path: Path, data_stream, display_channels):
    """测试计算过程"""
    print_separator("2. 测试计算过程")
    
    # 加载配置
    service = SteadyStateService()
    config = service._load_config(str(config_path))
    
    print("配置信息:")
    print(f"  显示通道: {config.display_channels}")
    print(f"  组合逻辑: {config.trigger_logic.combination}")
    if config.trigger_logic.condition1:
        cond1 = config.trigger_logic.condition1
        print(f"  条件1:")
        print(f"    enabled: {cond1.get('enabled')}")
        print(f"    channel: {cond1.get('channel')}")
        print(f"    statistic: {cond1.get('statistic')} (这是传递给计算器的值)")
        print(f"    duration: {cond1.get('duration_sec')}s")
        print(f"    logic: {cond1.get('logic')}")
        print(f"    threshold: {cond1.get('threshold')}")
        
        # 检查原始配置
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = json.load(f)
        raw_cond = raw_config.get('reportConfig', {}).get('stableState', {}).get('conditions', [])
        if raw_cond and len(raw_cond) > 0:
            print(f"\n  原始配置文件中的统计方法: {raw_cond[0].get('statistic', '未找到')}")
    
    # 先输出前20条的详细计算过程
    print_detailed_calculation_first_20(data_stream, config)
    
    # 先执行完整计算
    print("\n执行完整计算...")
    calculator = SteadyStateCalculator(config)
    snapshots = calculator.calculate(data_stream)
    
    print(f"\n计算结果:")
    print(f"  总快照数: {len(snapshots)}")
    
    if snapshots:
        print(f"\n前10个快照:")
        for i, snapshot in enumerate(snapshots[:10]):
            print(f"  {i+1}. time={snapshot['timestamp']:.3f}s")
            for channel in snapshot['data']:
                print(f"      {channel}={snapshot['data'][channel]:.2f}")
        
        if len(snapshots) > 10:
            print(f"\n... 还有 {len(snapshots) - 10} 个快照")
    else:
        print("\n[警告] 没有生成任何快照！")
        
        # 详细调试：检查窗口计算
        print("\n开始详细调试...")
        calculator2 = SteadyStateCalculator(config)
        
        cond1_channel = config.trigger_logic.condition1.get('channel') if config.trigger_logic.condition1 else None
        cond1_duration = config.trigger_logic.condition1.get('duration_sec', 1.0) if config.trigger_logic.condition1 else 0
        cond1_threshold = config.trigger_logic.condition1.get('threshold', 0) if config.trigger_logic.condition1 else 0
        cond1_logic = config.trigger_logic.condition1.get('logic', '>') if config.trigger_logic.condition1 else None
        
        print(f"\n条件1详细信息:")
        print(f"  通道: {cond1_channel}")
        print(f"  窗口时长: {cond1_duration}s")
        print(f"  阈值: {cond1_threshold}")
        print(f"  逻辑: {cond1_logic}")
        
        # 检查前100个数据点的窗口计算
        print(f"\n检查前100个数据点的窗口计算:")
        window_values_list = []
        cond1_met_count = 0
        
        for idx, (current_time, data_point) in enumerate(data_stream[:100]):
            if calculator2.window_cond1 and calculator2.config.trigger_logic.condition1:
                cond1_met, current_stat = calculator2.check_condition1(current_time, data_point)
                
                if calculator2.window_cond1:
                    window_size = len(calculator2.window_cond1)
                    if window_size > 0 and idx % 10 == 0:  # 每10个点打印一次
                        window_values = [item[1] for item in calculator2.window_cond1]
                        window_avg = sum(window_values) / len(window_values)
                        print(f"  {idx}. time={current_time:.3f}s, window_size={window_size}, "
                              f"window_avg={window_avg:.2f}, stat={current_stat:.2f}, "
                              f"met={cond1_met}")
                        
                        if cond1_met:
                            cond1_met_count += 1
                
                # 更新状态
                calculator2.cond1_last_state = cond1_met
        
        print(f"\n前100个点中，条件1满足的次数: {cond1_met_count}")
        
        # 检查Ng值的分布
        ng_values = [values.get('Ng', 0) for _, values in data_stream]
        ng_gt_2000_count = sum(1 for v in ng_values if v > 2000)
        print(f"\nNg值统计:")
        print(f"  > 2000的点数: {ng_gt_2000_count} / {len(ng_values)}")
        if ng_gt_2000_count > 0:
            # 找到第一个>2000的点
            first_gt_2000_idx = next((i for i, (_, values) in enumerate(data_stream) if values.get('Ng', 0) > 2000), None)
            if first_gt_2000_idx is not None:
                timestamp, values = data_stream[first_gt_2000_idx]
                print(f"  第一个>2000的点: time={timestamp:.3f}s, Ng={values.get('Ng', 0):.2f}")
                
                # 在第一个>2000的点附近进行详细分析
                print(f"\n在第一个>2000的点附近进行详细分析 (索引 {first_gt_2000_idx}):")
                calculator3 = SteadyStateCalculator(config)
                
                # 分析从 first_gt_2000_idx 前20个点到后20个点
                start_idx = max(0, first_gt_2000_idx - 20)
                end_idx = min(len(data_stream), first_gt_2000_idx + 20)
                
                for idx in range(start_idx, end_idx):
                    current_time, data_point = data_stream[idx]
                    if calculator3.window_cond1:
                        cond1_met, current_stat = calculator3.check_condition1(current_time, data_point)
                        window_size = len(calculator3.window_cond1)
                        if window_size > 0:
                            window_values = [item[1] for item in calculator3.window_cond1]
                            window_avg = sum(window_values) / len(window_values)
                            window_min = min(window_values)
                            window_max = max(window_values)
                            ng_value = data_point.get('Ng', 0)
                            
                            if idx == first_gt_2000_idx or cond1_met or idx % 5 == 0:
                                marker = "***" if idx == first_gt_2000_idx else ("[满足]" if cond1_met else "")
                                print(f"  [{idx}] time={current_time:.3f}s, Ng={ng_value:.2f}, "
                                      f"window_size={window_size}, window_avg={window_avg:.2f}, "
                                      f"window_range=[{window_min:.2f}, {window_max:.2f}], "
                                      f"stat={current_stat:.2f}, met={cond1_met} {marker}")
                        
                        calculator3.cond1_last_state = cond1_met
    
    return snapshots


def print_snapshots_table(snapshots, display_channels):
    """以表格形式打印快照结果"""
    if not snapshots:
        print("\n[警告] 没有快照数据可显示")
        return
    
    print_separator("快照结果表格")
    
    # 准备表头：时间 + 所有通道
    headers = ["时间(s)"] + display_channels
    num_cols = len(headers)
    
    # 计算每列的最大宽度
    col_widths = {}
    for header in headers:
        if header == "时间(s)":
            col_widths[header] = max(len(header), 12)
        else:
            col_widths[header] = max(len(header), 15)
    
    # 遍历快照数据，调整列宽
    for snapshot in snapshots:
        timestamp = snapshot['timestamp']
        timestamp_str = f"{timestamp:.3f}"
        if len(timestamp_str) > col_widths["时间(s)"]:
            col_widths["时间(s)"] = len(timestamp_str)
        
        for channel in display_channels:
            value = snapshot['data'].get(channel, 0)
            value_str = f"{value:.2f}"
            if len(value_str) > col_widths[channel]:
                col_widths[channel] = len(value_str)
    
    # 打印表头
    header_line = " | ".join([f"{header:<{col_widths[header]}}" for header in headers])
    separator_line = "-" * len(header_line)
    print(header_line)
    print(separator_line)
    
    # 打印数据行
    for snapshot in snapshots:
        timestamp = snapshot['timestamp']
        row_data = [f"{timestamp:.3f}"]
        
        for channel in display_channels:
            value = snapshot['data'].get(channel, 0)
            row_data.append(f"{value:.2f}")
        
        row_line = " | ".join([f"{row_data[i]:<{col_widths[headers[i]]}}" for i in range(num_cols)])
        print(row_line)
    
    print(f"\n总计: {len(snapshots)} 个快照")


def generate_excel_report(snapshots, display_channels, reports_dir: Path):
    """生成Excel报表并保存到reports目录"""
    if not snapshots:
        print("\n[警告] 没有快照数据，无法生成Excel文件")
        return None
    
    print_separator("生成Excel报表")
    
    # 确保reports目录存在
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名（包含时间戳）
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"steady_state_report_{timestamp_str}.xlsx"
    excel_path = reports_dir / excel_filename
    
    try:
        # 使用ReportWriter生成Excel文件
        report_writer = ReportWriter()
        report_writer.create_report(snapshots, str(excel_path))
        
        print(f"[成功] Excel报表已生成: {excel_path}")
        print(f"  文件路径: {excel_path.absolute()}")
        print(f"  快照数量: {len(snapshots)}")
        print(f"  显示通道: {', '.join(display_channels)}")
        
        return str(excel_path)
    except Exception as e:
        print(f"[错误] 生成Excel报表失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print_separator("计算模块调试测试")
    
    # 文件路径
    backend_dir = Path(__file__).parent
    config_path = backend_dir / "config_sessions" / "config_test.json"
    data_file = backend_dir / "uploads" / "fa546266-2bd3-4eab-8cdd-d6ae50e838a3.csv"
    
    print(f"配置文件: {config_path}")
    print(f"数据文件: {data_file}")
    
    # 1. 测试数据读取
    data_stream, display_channels = test_data_reading(config_path, data_file)
    
    # 2. 测试计算过程
    snapshots = test_calculation(config_path, data_stream, display_channels)
    
    # 3. 以表格形式显示快照结果
    if snapshots:
        print_snapshots_table(snapshots, display_channels)
    
    # 4. 生成Excel报表
    excel_path = None
    if snapshots:
        reports_dir = backend_dir / "reports"
        excel_path = generate_excel_report(snapshots, display_channels, reports_dir)
    
    # 总结
    print_separator("测试总结")
    if snapshots:
        print(f"[成功] 生成了 {len(snapshots)} 个快照")
        print(f"第一个快照时间: {snapshots[0]['timestamp']:.3f}s")
        print(f"最后一个快照时间: {snapshots[-1]['timestamp']:.3f}s")
        if excel_path:
            print(f"Excel报表路径: {excel_path}")
    else:
        print("[警告] 没有生成任何快照，请检查:")
        print("  1. 配置条件是否正确")
        print("  2. 数据是否满足条件")
        print("  3. 窗口计算逻辑是否正确")
    
    return 0 if snapshots else 1


if __name__ == "__main__":
    exit_code = 1  # 默认失败
    try:
        print("开始测试...")
        sys.stdout.flush()
        
        # 同时将输出写入文件
        backend_dir_local = Path(__file__).parent
        output_file = backend_dir_local / "test_output.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            # 重定向标准输出到文件和控制台
            import io
            from contextlib import redirect_stdout
            
            class TeeOutput:
                def __init__(self, file, console):
                    self.file = file
                    self.console = console
                    
                def write(self, data):
                    self.file.write(data)
                    self.console.write(data)
                    self.file.flush()
                    self.console.flush()
                    
                def flush(self):
                    self.file.flush()
                    self.console.flush()
            
            tee = TeeOutput(f, sys.stdout)
            old_stdout = sys.stdout
            sys.stdout = tee
            
            try:
                exit_code = main()
            finally:
                sys.stdout = old_stdout
                f.write(f"\n\n测试完成，退出代码: {exit_code}\n")
        
        print(f"\n输出已保存到: {output_file}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n[警告] 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

