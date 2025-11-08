# 状态评估计算模块测试

本目录包含状态评估计算模块的测试代码和测试数据。

## 目录结构

```
tests1/
├── test_status_evaluation.py    # 测试主文件
├── README.md                     # 本说明文件
└── data/                        # 测试数据目录
    ├── status_eval_config.json  # 状态评估配置文件
    ├── test_data.csv            # 测试数据文件（CSV格式）
    └── test_output.xlsx         # 测试输出文件（运行后生成）
```

## 使用方法

### 1. 运行测试

直接运行测试文件：

```bash
cd backend/tests1
python test_status_evaluation.py
```

### 2. 使用自定义配置文件和数据文件

修改 `test_status_evaluation.py` 中的路径，或直接传入参数：

```python
from test_status_evaluation import run_test

run_test(
    config_path="path/to/your/config.json",
    data_path="path/to/your/data.csv",
    output_path="path/to/output.xlsx"
)
```

## 配置文件格式

配置文件应为 JSON 格式，包含 `reportConfig.statusEval` 结构：

```json
{
  "reportConfig": {
    "statusEval": {
      "type": "continuous_check",
      "conditionLogic": "AND",
      "evaluations": [
        {
          "item": "评估项ID",
          "assessmentName": "评估项目名称",
          "type": "continuous_check",
          "conditionLogic": "AND",
          "conditions": [
            {
              "channel": "通道名称",
              "statistic": "平均值|最大值|最小值|有效值|瞬时值|difference",
              "duration": 1.0,
              "logic": ">|<|>=|<=",
              "threshold": 100.0
            }
          ]
        }
      ]
    }
  }
}
```

### 支持的统计方法

- `平均值` / `average` / `mean` / `avg`
- `最大值` / `max` / `maximum`
- `最小值` / `min` / `minimum`
- `有效值` / `rms` / `rootmeansquare`
- `瞬时值` / `instant` / `instantaneous`
- `difference` / `差值` / `diff` - 当前值减去 duration 秒前的值

### 支持的逻辑操作

- `>` - 大于
- `<` - 小于
- `>=` - 大于等于
- `<=` - 小于等于
- `==` - 等于

## 数据文件格式

数据文件应为 CSV 格式，包含：

1. **时间列**：列名可以是 `time[s]`, `time`, `Time`, `timestamp` 等
2. **通道数据列**：与配置文件中 `channel` 字段对应的列名

示例：

```csv
time[s],Pressure(kPa),Temperature(°C),Ng,Np
0.0,200.5,300.2,5000.0,4000.0
0.01,201.2,301.5,5010.0,4010.0
...
```

## 测试说明

### 测试内容

1. **配置加载**：从 JSON 文件加载状态评估配置
2. **数据读取**：从 CSV 文件读取时序数据
3. **计算执行**：执行状态评估计算（一票否决机制）
4. **结果验证**：验证计算结果并输出
5. **报表生成**：可选生成 Excel 报表

### 一票否决机制

状态评估采用"一票否决"机制：

- 所有评估项初始结论为"是"（通过）
- 逐点扫描数据流，检查失败条件
- 一旦任何时刻触发失败条件，该评估项结论永久翻转为"否"（不通过）
- 一旦翻转为"否"，后续数据点不再检查该评估项

### 评估项类型

- `continuous_check`：连续检查类型（已实现）
- `functional_result`：功能结果类型（测试中跳过）

## 输出结果

测试运行后会输出：

1. **控制台输出**：

   - 每个评估项的结论（"是"或"否"）
   - 评估项的配置信息
   - 测试验证结果

2. **Excel 报表**（如果 ReportWriter 可用）：
   - 包含三列：评估项目、评估内容、评估结论
   - 按照配置文件中评估项的顺序生成

## 注意事项

1. 确保配置文件和数据文件路径正确
2. 数据文件中的通道名称必须与配置文件中的 `channel` 字段完全匹配
3. 时间列必须是递增的数值序列
4. 如果通道在数据文件中不存在，会使用默认值 0.0 并发出警告

## 示例

运行测试后，你会看到类似以下的输出：

```
============================================================
状态评估计算模块测试
============================================================

使用配置文件: D:\PythonCode\DRIA\backend\tests1\data\status_eval_config.json
使用数据文件: D:\PythonCode\DRIA\backend\tests1\data\test_data.csv
输出文件: D:\PythonCode\DRIA\backend\tests1\data\test_output.xlsx

开始运行状态评估计算...

============================================================
状态评估计算结果:
============================================================

评估项: 压力传感器状态评估
  结论: 是
  类型: continuous_check
  条件逻辑: AND
  条件数量: 1
    条件1: Pressure(kPa) 平均值 (1.0s) > 100.0

...

============================================================
测试验证:
============================================================
[OK] 成功计算 5 个评估项
[INFO] 所有评估项均通过（结论为'是'）

[OK] 报表已生成: D:\PythonCode\DRIA\backend\tests1\data\test_output.xlsx

============================================================
测试完成！
============================================================
```
