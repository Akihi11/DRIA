# DRIA Docker 部署说明

> **💡 提示**：如果主项目一致（clone 自同一仓库），请优先参考 [异地部署文档.md](./异地部署文档.md)，该文档针对主项目一致的情况进行了优化。

## 📋 目录

- [前提条件](#前提条件)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [网络连接配置](#网络连接配置)
- [常用命令](#常用命令)
- [故障排查](#故障排查)
- [生产环境建议](#生产环境建议)

## 前提条件

1. ✅ 已安装 Docker（版本 20.10+）
2. ✅ 已安装 Docker Compose（版本 2.0+）
3. ✅ 主项目的 PostgreSQL 和 Ollama 服务已运行
4. ✅ 了解主项目的 Docker 网络配置

## 快速开始

### 1. 准备环境变量

**重要：`.env.docker` 文件必须放在项目根目录（与 `docker-compose.yml` 同级）**

```bash
# 在项目根目录下执行（与 docker-compose.yml 同级）
# 复制环境变量示例文件
cp env.docker.example .env.docker

# 编辑配置文件，填入主项目的实际连接信息
# Windows: notepad .env.docker
# Linux/Mac: nano .env.docker
```

**文件位置示例：**

```
DRIA/
├── docker-compose.yml
├── .env.docker          ← 放在这里（项目根目录）
├── env.docker.example
├── docker-start.sh
├── docker-start.bat
├── backend/
└── frontend/
```

或者直接运行快速启动脚本，用于自动化部署流程：

```bash
# Linux/Mac
chmod +x docker-start.sh
./docker-start.sh

# Windows
docker-start.bat
```

### 2. 配置主项目网络连接

找到主项目的 Docker 网络名称：

```bash
# 查看所有Docker网络
docker network ls

# 或者查看主项目的docker-compose.yml，找到网络名称
```

编辑 `docker-compose.yml`，取消注释并配置主项目网络：

```yaml
networks:
  dria-network:
    driver: bridge
  main-network:
    external: true
    name: 主项目的实际网络名称 # 例如：main-project_default
```

同时取消注释 `backend` 和 `backend-init` 服务中的网络配置。

### 3. 构建和启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看服务状态
docker-compose ps
```

### 4. 验证部署

- 🌐 **前端访问**: http://localhost
- 🔧 **后端 API**: http://localhost:8001（注意：端口是 8001，不是 8000）
- 📚 **API 文档**: http://localhost:8001/api/docs
- ❤️ **健康检查**: http://localhost:8001/api/health

## 配置说明

### 环境变量配置

在 `.env.docker` 文件中配置以下关键参数：

#### 数据库连接

```env
# 方式1: 完整连接字符串（推荐）
DATABASE_URL=postgresql+psycopg2://user:password@main-postgres:5432/main_database

# 方式2: 分离配置（如果方式1不工作）
POSTGRES_HOST=main-postgres
POSTGRES_PORT=5432
POSTGRES_DB=main_database
POSTGRES_USER=user
POSTGRES_PASSWORD=password
```

#### Ollama 连接

```env
# 使用主项目的Ollama服务名称
OLLAMA_URL=http://main-ollama:11434

# 或者如果Ollama在主机上运行
OLLAMA_URL=http://host.docker.internal:11434

# Ollama模型名称
OLLAMA_MODEL=qwen2.5:3b
```

## 网络连接配置

### 方式一：使用外部网络（推荐）

如果主项目也在 Docker 中运行，使用外部网络连接：

1. **找到主项目的网络名称**

   ```bash
   # 方法1: 查看主项目的docker-compose.yml
   # 方法2: 运行以下命令
   docker network ls
   ```

2. **在 docker-compose.yml 中配置**

   ```yaml
   networks:
     main-network:
       external: true
       name: main-project_default # 替换为主项目的实际网络名称
   ```

3. **在服务中启用网络**

   ```yaml
   services:
     backend:
       networks:
         - dria-network
         - main-network # 取消注释
   ```

### 方式二：使用主机网络

如果主项目的服务在主机上运行（不在 Docker 中）：

1. **修改 docker-compose.yml**

   ```yaml
   services:
     backend:
       network_mode: "host"
       # 或者使用extra_hosts
       extra_hosts:
         - "host.docker.internal:host-gateway"
   ```

2. **修改环境变量**

   ```env
   DATABASE_URL=postgresql+psycopg2://user:password@host.docker.internal:5432/main_database
   OLLAMA_URL=http://host.docker.internal:11434
   ```

### 方式三：使用 IP 地址

如果知道主项目服务的 IP 地址：

```yaml
services:
  backend:
    extra_hosts:
      - "main-postgres:192.168.1.100"
      - "main-ollama:192.168.1.101"
```

## 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 停止并删除卷（注意：会删除数据）
docker-compose down -v

# 重新构建并启动
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 容器操作

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入前端容器
docker-compose exec frontend sh

# 重启服务
docker-compose restart backend
docker-compose restart frontend

# 查看容器资源使用
docker stats
```

### 数据库操作

```bash
# 测试PostgreSQL连接
docker-compose exec backend python -c "
from backend.services.db import _engine
if _engine:
    print('Database connection OK')
else:
    print('Database not configured')
"

# 检查数据库表
docker-compose exec backend python -c "
from backend.services.db import init_schema
init_schema()
print('Schema initialized')
"
```

### 清理操作

```bash
# 清理未使用的镜像
docker image prune

# 清理所有未使用的资源
docker system prune -a

# 查看磁盘使用情况
docker system df
```

## 故障排查

### 1. 无法连接到 PostgreSQL

**检查网络连接：**

```bash
# 进入后端容器
docker-compose exec backend bash

# 测试网络连接
ping main-postgres

# 测试PostgreSQL连接
psql -h main-postgres -U user -d main_database
```

**检查环境变量：**

```bash
# 查看环境变量
docker-compose exec backend env | grep DATABASE
```

**解决方案：**

- 确认主项目的 PostgreSQL 服务名称正确
- 确认网络配置正确
- 确认数据库用户权限足够
- 检查防火墙设置

### 2. 无法连接到 Ollama

**检查 Ollama 服务：**

```bash
# 进入后端容器
docker-compose exec backend bash

# 测试Ollama连接
curl http://main-ollama:11434/api/tags

# 或者
curl http://host.docker.internal:11434/api/tags
```

**解决方案：**

- 确认 Ollama 服务正在运行
- 确认服务名称或 IP 地址正确
- 检查端口是否开放（11434）
- 如果 Ollama 在主机上，使用 `host.docker.internal`

### 3. 前端无法访问后端

**检查后端服务：**

```bash
# 查看后端日志
docker-compose logs backend

# 测试后端健康检查
curl http://localhost:8001/api/health
```

**检查 Nginx 配置：**

```bash
# 进入前端容器
docker-compose exec frontend sh

# 测试Nginx配置
nginx -t

# 查看Nginx日志
cat /var/log/nginx/error.log
```

### 4. 容器启动失败

**查看详细日志：**

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务的详细日志
docker-compose logs --tail=100 backend
```

**常见问题：**

- **端口被占用**: 修改 `docker-compose.yml` 中的端口映射
- **依赖安装失败**: 检查网络连接，可能需要代理
- **权限问题**: 确保 Docker 有足够权限

### 5. 数据持久化问题

**检查卷挂载：**

```bash
# 查看卷信息
docker volume ls

# 检查挂载点
docker-compose exec backend ls -la /app/uploads
docker-compose exec backend ls -la /app/reports
```

**解决方案：**

- 确认 `docker-compose.yml` 中的卷配置正确
- 检查主机目录权限
- 确保目录存在

## 生产环境建议

### 1. 安全性配置

- ✅ 使用环境变量文件管理敏感信息（不要提交到版本控制）
- ✅ 配置 Nginx SSL/TLS 证书
- ✅ 限制 API 访问频率
- ✅ 使用 Docker Secrets 管理敏感数据

### 2. 性能优化

```yaml
# 在docker-compose.yml中添加资源限制
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
        reservations:
          cpus: "1"
          memory: 1G
```

### 3. 日志管理

```yaml
# 配置日志轮转
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. 健康检查

健康检查已在 `docker-compose.yml` 中配置，确保服务正常运行。

### 5. 备份策略

定期备份以下目录：

- `backend/uploads/` - 上传的文件
- `backend/reports/` - 生成的报表
- `backend/config_sessions/` - 配置会话

### 6. 监控建议

- 使用 Docker 监控工具（如 Portainer）
- 配置应用监控（如 Prometheus + Grafana）
- 设置告警通知

## 架构说明

```
┌─────────────────────────────────────┐
│  主项目 Docker 网络                  │
│  ┌─────────────┐  ┌──────────────┐ │
│  │ PostgreSQL  │  │   Ollama     │ │
│  │  (已有)     │  │   (已有)     │ │
│  └─────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
           ▲                ▲
           │                │
           │  网络连接       │
           │                │
┌──────────┴────────────────┴──────────┐
│  DRIA Docker 网络                     │
│  ┌─────────────┐  ┌──────────────┐  │
│  │  Backend    │  │  Frontend    │  │
│  │  (FastAPI)  │  │  (Nginx)     │  │
│  │  :8000      │  │  :80         │  │
│  └─────────────┘  └──────────────┘  │
└──────────────────────────────────────┘
```

## 支持

如有问题，请检查：

1. Docker 和 Docker Compose 版本
2. 主项目服务状态
3. 网络连接配置
4. 环境变量配置
5. 日志输出
