import numpy as np
from collections import deque
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional

"""
最终滑动窗口验证脚本 (V3.2)

- 使用 V3.2 版的 SlidingWindow 类 (修复了浮点数Bug)
- 加载真实的 'Simulated_Data.csv'
- 找出 '滑油压力' 在 1.0s 窗口下的“历史最大平均值”
- 用这个结果来验证 'turn_179' 的Bug
"""

# ---
# 这是我们要测试的 V3.2 版的 SlidingWindow 类
# ---
class SlidingWindow:
    """滑动窗口计算器"""
    
    def __init__(self, duration: float, statistic_type: str = "平均值"):
        self.duration = duration
        self.statistic_type = statistic_type
        self.window = deque()  # [(timestamp, value), ...]
        self._precision = 2 # 假设 0.01s 的精度

    def _round(self, val):
        """辅助函数：四舍五入到固定精度以避免浮点数Bug"""
        return round(val, self._precision)

    def update(self, timestamp: float, value: float):
        """更新窗口，移除过期数据，添加新数据"""
        # V3.2 修复逻辑：
        # 在做任何比较之前，先把所有东西都 round 一遍！
        cutoff_time_exclusive = self._round(timestamp - self.duration)
        
        while self.window and self._round(self.window[0][0]) <= cutoff_time_exclusive:
            popped_item = self.window.popleft()
            
        self.window.append((timestamp, value))
    
    def calculate_statistic(self) -> Optional[float]:
        """计算窗口内的统计值"""
        if not self.window:
            return None
        
        values = [item[1] for item in self.window]
        
        stat_lower = self.statistic_type.lower() if self.statistic_type else 'average'
        
        if stat_lower in ['average', '平均值', 'mean', 'avg']:
            return float(np.mean(values))
        elif stat_lower in ['max', '最大值', 'maximum']:
            return float(np.max(values))
        elif stat_lower in ['min', '最小值', 'minimum']:
            return float(np.min(values))
        elif stat_lower in ['rms', '有效值', 'rootmeansquare']:
            return float(np.sqrt(np.mean(np.array(values) ** 2)))
        else:
            print(f"未知的统计类型: {self.statistic_type}，使用平均值代替")
            return float(np.mean(values))

# ---
# 验证脚本的执行代码
# ---

if __name__ == "__main__":
    
    # --- 1. 定义我们要测试的参数 ---
    FILE_TO_TEST = 'D:\\PythonCode\\DRIA\\backend\\windows_test\\Simulated_Data.csv'
    CHANNEL_TO_TEST = '滑油压力'
    DURATION_SEC = 10
    STATISTIC_TO_TEST = '平均值'
    ENABLE_DIFF_CALCULATION = True  # 是否启用差值计算
    
    print(f"--- 开始测试 V3.2 SlidingWindow ---")
    print(f"  数据文件: {FILE_TO_TEST}")
    print(f"  测试通道: {CHANNEL_TO_TEST}")
    print(f"  窗口时长: {DURATION_SEC}s")
    print(f"  统计类型: {STATISTIC_TO_TEST}")
    print(f"  差值计算: {'启用' if ENABLE_DIFF_CALCULATION else '禁用'}")
    print("="*40)

    # 2. 实例化我们要测试的窗口
    window = SlidingWindow(duration=DURATION_SEC, statistic_type=STATISTIC_TO_TEST)

    # 3. 加载真实的 CSV
    try:
        df = pd.read_csv(FILE_TO_TEST)
    except FileNotFoundError:
        print(f"错误：未找到 '{FILE_TO_TEST}'。")
        print(f"请将 '{FILE_TO_TEST}' 文件放在此脚本相同的目录下。")
        exit()
    except KeyError:
        print(f"错误：'{FILE_TO_TEST}' 中未找到 '{CHANNEL_TO_TEST}' 或 'time[s]' 列。")
        exit()
        
    print(f"开始遍历 {len(df)} 行数据...")

    # 4. 遍历数据并找出最大平均值
    max_calculated_avg = -float('inf')
    time_of_max = 0.0
    
    # 差值计算相关变量（仅在启用时初始化）
    if ENABLE_DIFF_CALCULATION:
        time_value_map = {}  # 存储时间到值的映射，用于差值计算
        max_diff = -float('inf')
        time_of_max_diff = 0.0
        value_at_max_diff = 0.0
        historical_value_at_max_diff = 0.0
        historical_time_at_max_diff = 0.0  # 实际匹配的历史时间
    
    # 确定时间列
    time_col = 'time[s]' if 'time[s]' in df.columns else 'Time'
    if time_col not in df.columns:
        print(f"错误：CSV中未找到 'time[s]' 或 'Time' 列")
        exit()

    for row in df.to_dict('records'):
        t = row[time_col]
        v = row[CHANNEL_TO_TEST]
        
        # 存储当前时间点的值，用于后续差值计算（仅在启用时）
        if ENABLE_DIFF_CALCULATION:
            time_value_map[t] = v
        
        # 更新窗口
        window.update(t, v)
        
        # 计算统计值
        current_avg = window.calculate_statistic()
        
        if current_avg is not None:
            if current_avg > max_calculated_avg:
                max_calculated_avg = current_avg
                time_of_max = t
        
        # 计算差值：当前值减去窗口时长之前的值（仅在启用时）
        if ENABLE_DIFF_CALCULATION:
            historical_time = round(t - DURATION_SEC, 2)  # 四舍五入到0.01s精度
            # 尝试精确匹配，如果失败则尝试最接近的时间点
            if historical_time in time_value_map:
                historical_value = time_value_map[historical_time]
            else:
                # 查找最接近的时间点（在0.01s范围内）
                closest_time = None
                min_diff = float('inf')
                for stored_time in time_value_map.keys():
                    time_diff = abs(stored_time - historical_time)
                    if time_diff < min_diff and time_diff < 0.01:  # 允许0.01s的误差
                        min_diff = time_diff
                        closest_time = stored_time
                if closest_time is not None:
                    historical_value = time_value_map[closest_time]
                    historical_time = closest_time  # 更新为实际匹配的时间
                else:
                    historical_value = None
            
            if historical_value is not None:
                diff = v - historical_value
                
                # 跟踪最大差值
                if diff > max_diff:
                    max_diff = diff
                    time_of_max_diff = t
                    value_at_max_diff = v
                    historical_value_at_max_diff = historical_value
                    historical_time_at_max_diff = historical_time

    print("\n" + "="*40)
    print("测试完成。")
    print(f'"{CHANNEL_TO_TEST}" 在 {DURATION_SEC}s 窗口下的"历史最大平均值"为:')
    print(f"  {max_calculated_avg}")
    print(f"  (该峰值出现在 t={time_of_max:.2f}s 时刻)")
    
    # 仅在启用差值计算时显示差值结果
    if ENABLE_DIFF_CALCULATION:
        print("\n" + "-"*40)
        print(f"差值计算（当前值 - {DURATION_SEC}s之前的值）:")
        if max_diff != -float('inf'):
            print(f"  最大差值: {max_diff}")
            print(f"  出现在 t={time_of_max_diff:.2f}s 时刻")
            print(f"  当前值: {value_at_max_diff}")
            print(f"  历史值 (t={historical_time_at_max_diff:.2f}s): {historical_value_at_max_diff}")
        else:
            print(f"  未找到有效的差值数据（需要至少 {DURATION_SEC}s 的数据才能计算差值）")