# 📊 报表管理系统使用说明

## 🎯 概述

本系统实现了报表文件的自动分类管理，所有生成的报表都会保存在 `reports/` 文件夹下的相应子文件夹中。

## 📁 文件夹结构

```
reports/
├── api_generated/     # API生成的报表
├── golden_standard/   # Golden Standard基准报表
├── test_reports/      # 测试生成的报表
├── manual_reports/    # 手动生成的报表
└── archived/          # 归档的旧报表
```

## 🔧 使用方法

### 1. 自动分类保存

**API 生成报表**：

```json
{
  "session_id": "your_session",
  "file_id": "your_file_id",
  "report_type": "api_generated",  // 可选：指定报表类型
  "config": { ... }
}
```

**测试报表**：

```python
# 在test_api.py中
report_config = {
    "report_type": "test_reports",  # 自动保存到test_reports/
    ...
}
```

**Golden Standard 报表**：

```bash
python tests/create_golden_standard.py
# 自动保存到 reports/golden_standard/
```

### 2. 报表管理命令

**查看统计信息**：

```bash
python manage_reports.py stats
```

**列出所有报表**：

```bash
python manage_reports.py list
```

**列出特定类型报表**：

```bash
python manage_reports.py list --type api_generated
```

**移动报表**：

```bash
python manage_reports.py move --filename "report_xxx.xlsx" --from-type "api_generated" --to-type "archived"
```

**复制报表**：

```bash
python manage_reports.py copy --filename "report_xxx.xlsx" --from-type "api_generated" --to-type "manual_reports" --new-name "manual_report.xlsx"
```

**删除报表**：

```bash
python manage_reports.py delete --filename "report_xxx.xlsx" --type "test_reports"
```

**归档旧报表**：

```bash
python manage_reports.py archive --days 30  # 归档30天前的报表
```

**清理空文件夹**：

```bash
python manage_reports.py clean
```

## 🎨 报表类型说明

### api_generated

- **用途**：通过 API 接口生成的报表
- **来源**：`POST /api/reports/generate`
- **特点**：用户通过 Web 界面或 API 调用生成

### golden_standard

- **用途**：标准基准报表，用于验证和对比
- **来源**：`python tests/create_golden_standard.py`
- **特点**：使用标准配置和数据生成，作为质量基准

### test_reports

- **用途**：自动化测试生成的报表
- **来源**：`python test_api.py` 和其他测试脚本
- **特点**：用于验证系统功能，可定期清理

### manual_reports

- **用途**：手动生成或特殊用途的报表
- **来源**：手动移动或复制的报表
- **特点**：重要报表，需要长期保存

### archived

- **用途**：归档的旧报表
- **来源**：通过 `archive` 命令自动归档
- **特点**：长期保存，文件名带日期前缀

## 🔄 自动化工作流

### 日常维护

```bash
# 1. 查看当前状态
python manage_reports.py stats

# 2. 归档30天前的报表
python manage_reports.py archive --days 30

# 3. 清理空文件夹
python manage_reports.py clean
```

### 报表整理

```bash
# 将测试报表移动到归档
python manage_reports.py move --filename "old_test_report.xlsx" --from-type "test_reports" --to-type "archived"

# 将重要的API报表复制到手动报表
python manage_reports.py copy --filename "important_report.xlsx" --from-type "api_generated" --to-type "manual_reports"
```

## 📋 最佳实践

1. **定期归档**：每月运行一次归档命令，清理旧的测试报表
2. **重要报表备份**：将重要的 API 报表复制到 `manual_reports` 长期保存
3. **测试报表清理**：测试完成后及时清理 `test_reports` 文件夹
4. **监控磁盘空间**：定期检查 `stats` 了解存储使用情况
5. **命名规范**：重要报表建议重命名为有意义的名称

## 🛠️ 配置自定义

在 `config.py` 中可以修改：

```python
# 报表子目录配置
REPORT_SUBDIRS = {
    "api_generated": "api_generated",
    "golden_standard": "golden_standard",
    "test_reports": "test_reports",
    "manual_reports": "manual_reports",
    "archived": "archived"
}
```

## 🔍 故障排除

**问题 1：报表没有保存到正确的子文件夹**

- 检查 `report_type` 参数是否正确
- 确认子文件夹已创建

**问题 2：管理命令报错**

- 确认文件名和路径正确
- 检查文件是否存在

**问题 3：权限错误**

- 确认对 `reports/` 文件夹有写权限
- Windows 下可能需要管理员权限

## 📈 扩展功能

可以通过修改 `manage_reports.py` 添加更多功能：

- 报表内容分析
- 自动报告生成
- 邮件通知
- 云存储同步

---

💡 **提示**：使用 `python manage_reports.py --help` 查看完整的命令选项。
