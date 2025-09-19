# DRIA Frontend

DRIA AI 报表生成系统的前端应用，基于 React + TypeScript + Vite 构建。

## 功能特性

- 🤖 **AI 智能对话**: 通过自然语言对话配置和生成报表
- 📊 **多维度分析**: 支持稳态分析、功能计算、状态评估
- 📋 **报表管理**: 查看、下载和管理生成的报表
- 🎨 **现代 UI**: 基于 Ant Design 的专业界面设计
- 📱 **响应式布局**: 支持桌面和移动设备
- ⚡ **高性能**: Vite 构建工具，快速开发和构建

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Ant Design** - UI 组件库
- **Zustand** - 状态管理
- **React Router** - 路由管理
- **Axios** - HTTP 客户端

## 目录结构

```
src/
├── components/          # 可复用组件
│   ├── Chat/           # 聊天相关组件
│   └── Layout/         # 布局组件
├── pages/              # 页面组件
│   ├── HomePage.tsx    # 首页
│   ├── ChatPage.tsx    # 对话页面
│   └── ReportsPage.tsx # 报表管理页面
├── services/           # API服务
│   └── api.ts         # API客户端
├── store/              # 状态管理
│   └── useStore.ts    # Zustand store
├── types/              # 类型定义
│   ├── api.ts         # API类型
│   └── store.ts       # Store类型
├── utils/              # 工具函数
│   ├── constants.ts   # 常量定义
│   └── helpers.ts     # 辅助函数
└── assets/             # 静态资源
```

## 开发指南

### 环境要求

- Node.js >= 16
- npm >= 8

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## API 集成

前端通过 `/api` 路径代理到后端服务器（默认端口 8000）。主要 API 端点：

- `GET /api/health` - 健康检查
- `POST /api/ai_report/upload` - 文件上传
- `POST /api/ai_report/dialogue` - AI 对话
- `POST /api/ai_report/generate` - 报表生成
- `GET /api/reports/download/:id` - 报表下载

## 组件说明

### ChatContainer

主要的聊天界面组件，包含消息显示、输入框和文件上传功能。

### MessageBubble

单个消息气泡组件，支持不同类型的消息显示和交互。

### MainLayout

主布局组件，包含导航栏和内容区域。

## 状态管理

使用 Zustand 进行状态管理，分为以下几个 store：

- **UIStore**: UI 状态（加载、错误等）
- **DialogueStore**: 对话状态和消息历史
- **FileStore**: 文件上传状态
- **ReportsStore**: 报表管理状态

## 开发规范

### 代码风格

- 使用 TypeScript 严格模式
- 遵循 React Hooks 最佳实践
- 组件使用函数式组件
- 使用 ES6+ 语法

### 文件命名

- 组件文件使用 PascalCase：`ComponentName.tsx`
- 普通文件使用 camelCase：`fileName.ts`
- 常量文件使用 kebab-case：`constants.ts`

### 导入顺序

1. React 相关
2. 第三方库
3. 本地组件
4. 类型定义
5. 样式文件

## 构建配置

### Vite 配置

- 开发服务器端口：3000
- API 代理：`/api` -> `http://localhost:8000`
- 构建输出：`dist/`
- 支持 TypeScript 路径映射

### TypeScript 配置

- 严格模式启用
- 路径映射配置
- React JSX 支持

## 部署

### 构建

```bash
npm run build
```

### 静态文件服务

构建后的文件可以通过任何静态文件服务器部署，如 Nginx、Apache 或 CDN。

### 环境变量

可通过`.env`文件配置环境变量：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=DRIA AI报表生成系统
```

## 故障排除

- **API 请求失败**: 检查后端服务是否启动，确认代理配置正确
- **依赖安装失败**: 清除 node_modules 重新安装
- **类型错误**: 检查 TypeScript 配置和类型定义

> 更多详细信息请参考项目根目录的 `README.md` 和 `项目进展.md`
