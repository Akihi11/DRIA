# DRIA

AI 报表生成与对话助手（FastAPI + React/Vite）。

## 目录与文件说明（本项目）

- 根目录

  - `README.md`：项目说明（你正在看的文档）
  - `部署说明.md`：如何在本地/服务器部署与启动前后端
  - `环境配置指南.md`：`.env` 环境变量与 LLM/API 配置说明
  - `.gitignore`：Git 忽略规则

- `backend/`（后端 FastAPI 服务）

  - `main.py`：后端启动入口（等价于 `uvicorn.run`）；读取 `.env`，注册路由与中间件
  - `start.bat`：Windows 下一键启动后端脚本（激活虚拟环境并运行 `main.py`）
  - `requirements.txt`：后端 Python 依赖列表
  - `config.py`：后端配置加载（读取环境变量，含上传/输出目录、调试开关等）
  - `api/`：API 层（应用与路由）
    - `main.py`：FastAPI 应用创建与全局路由注册（挂载 `/api` 前缀、CORS、异常处理等）
    - `routes/`：各业务路由模块（文件上传、报表生成、会话配置、健康检查等）
  - `models/`：Pydantic 数据模型（请求/响应/内部传输对象）
  - `services/`：业务逻辑与报表生成实现（字段映射、过滤、分组聚合、模板装配、文件写出）
  - `uploads/`：上传的源数据文件存放目录（CSV/Excel）
  - `reports/`：生成的报表输出目录（可供下载/归档）
  - `config_sessions/`：对话确认后的配置快照与会话记录（便于复用与审计）

- `frontend/`（前端 React + Vite 应用）

  - `src/`：页面、组件与请求封装（包含上传、对话、配置确认、下载等 UI）
  - `vite.config.ts`：Vite 配置；开发时将 `/api` 代理到 `http://127.0.0.1:8000/api`
  - `package.json`：前端依赖与脚本（`dev`、`build`、`preview`）
  - `start-frontend.bat`：Windows 下一键启动前端脚本

- `docs/`：补充文档或规范

## 关键端口与入口

- 前端：`http://localhost:5173`（Vite 开发服务器）
- API 文档：`http://127.0.0.1:8000/api/docs`（Swagger UI）
- 健康检查：`http://127.0.0.1:8000/api/health`
- 代理：前端对 `/api` 的请求转发到 `http://127.0.0.1:8000/api`

## 项目做什么（一句话）

- 上传 CSV/Excel → 对话确定字段/过滤/分组与指标口径 → 生成报表到 `backend/reports/` 并提供下载；配置会话留痕于 `backend/config_sessions/`。

## 边界

- 聚焦结构化报表产出与下载；不替代 BI/数据仓库，不做重可视化编辑。

## 相关文档

- 部署与使用：`部署说明.md`
- 环境配置：`环境配置指南.md`
