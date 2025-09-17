# AI Report Generation Backend - Phase 1

## 项目概述

这是AI对话式报表生成系统的后端实现，第一阶段主要提供项目骨架、核心接口定义和Mock API服务。

## 项目结构

```
backend/
├── api/                    # API层
│   ├── main.py            # FastAPI主应用
│   └── routes/            # API路由定义
│       ├── health.py      # 健康检查端点
│       ├── file_upload.py # 文件上传端点
│       ├── dialogue.py    # 对话管理端点
│       └── report_generation.py # 报表生成端点
├── models/                # 数据模型
│   ├── api_models.py      # API请求/响应模型
│   ├── data_models.py     # 数据处理模型
│   └── report_config.py   # 报表配置模型
├── interfaces/            # 核心接口定义
│   ├── data_interfaces.py      # 数据服务接口
│   ├── analysis_interfaces.py  # 分析引擎接口
│   └── dialogue_interfaces.py  # 对话管理接口
├── services/              # 服务层实现
│   ├── mock_data_service.py     # Mock数据服务
│   ├── mock_dialogue_service.py # Mock对话服务
│   └── mock_analysis_service.py # Mock分析服务
├── config.py              # 配置管理
├── requirements.txt       # 项目依赖
└── main.py               # 启动入口
```

## 核心功能

### 1. API端点

- **健康检查**: `GET /api/health`
- **文件上传**: `POST /api/upload`
- **AI对话**: `POST /api/ai_report/dialogue`
- **报表生成**: `POST /api/reports/generate`
- **报表下载**: `GET /api/reports/download/{report_id}`

### 2. 核心接口

- **DataReader**: 数据读取器抽象基类
- **ReportWriter**: 报表写入器抽象基类
- **Analyzer**: 分析器抽象基类
- **DialogueManager**: 对话管理器抽象基类
- **ReportCalculationEngine**: 报表计算引擎抽象基类

### 3. Mock服务

所有核心服务都提供了Mock实现，支持完整的API测试和前端开发。

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动开发服务器

```bash
python main.py
```

### 3. 访问API文档

打开浏览器访问: http://127.0.0.1:8000/api/docs

## API使用示例

### 1. 健康检查

```bash
curl -X GET "http://127.0.0.1:8000/api/health"
```

### 2. 文件上传

```bash
curl -X POST "http://127.0.0.1:8000/api/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_data.csv"
```

### 3. 开始对话

```bash
curl -X POST "http://127.0.0.1:8000/api/ai_report/dialogue" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_123",
    "file_id": "uploaded_file_id",
    "user_input": "我想生成稳定状态报表",
    "dialogue_state": "file_uploaded"
  }'
```

### 4. 生成报表

```bash
curl -X POST "http://127.0.0.1:8000/api/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_123",
    "file_id": "uploaded_file_id",
    "config": {
      "sourceFileId": "uploaded_file_id",
      "reportConfig": {
        "sections": ["stableState"],
        "stableState": {
          "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
          "condition": {
            "channel": "Ng(rpm)",
            "statistic": "平均值",
            "duration": 1,
            "logic": ">",
            "threshold": 15000
          }
        }
      }
    }
  }'
```

## 配置说明

主要配置项在 `config.py` 中定义：

- `API_HOST`: API服务器地址 (默认: 127.0.0.1)
- `API_PORT`: API服务器端口 (默认: 8000)
- `DEBUG`: 调试模式 (默认: True)
- `UPLOAD_DIR`: 文件上传目录 (默认: ./uploads)
- `REPORT_OUTPUT_DIR`: 报表输出目录 (默认: ./reports)

## 数据模型

### 报表配置JSON结构

```json
{
  "sourceFileId": "file_id_123",
  "reportConfig": {
    "sections": ["stableState", "functionalCalc", "statusEval"],
    "stableState": {
      "displayChannels": ["Ng(rpm)", "Temperature(°C)"],
      "condition": {
        "channel": "Ng(rpm)",
        "statistic": "平均值",
        "duration": 1,
        "logic": ">",
        "threshold": 15000
      }
    },
    "functionalCalc": {
      "time_base": {
        "channel": "Pressure(kPa)",
        "statistic": "平均值",
        "duration": 1,
        "logic": ">",
        "threshold": 500
      }
    },
    "statusEval": {
      "evaluations": [
        {
          "item": "超温",
          "channel": "Temperature(°C)",
          "logic": "<",
          "threshold": 850
        }
      ]
    }
  }
}
```

## 开发注意事项

1. **第一阶段目标**: 本阶段主要提供项目骨架和Mock服务，所有的数据分析和报表生成都是模拟实现。

2. **接口契约**: 所有的接口定义已经完成，后续阶段只需要替换Mock实现为真实实现。

3. **数据模型**: 使用Pydantic进行数据验证和序列化，确保API接口的类型安全。

4. **错误处理**: 实现了全局异常处理和标准化的错误响应格式。

5. **API文档**: 使用FastAPI自动生成Swagger文档，支持在线测试。

## 下一阶段计划

第二阶段将实现：
- 真实的数据读取和处理逻辑
- 完整的报表计算引擎
- 实际的Excel文件生成
- 完整的单元测试套件

## 技术栈

- **Web框架**: FastAPI 0.104.1
- **数据处理**: Pandas, NumPy
- **Excel处理**: openpyxl
- **API文档**: Swagger/OpenAPI 3.0
- **数据验证**: Pydantic
- **异步支持**: uvicorn + asyncio
