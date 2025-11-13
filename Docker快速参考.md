# DRIA Docker 快速参考

## 📁 已创建的文件

### Docker 配置文件

- ✅ `docker-compose.yml` - Docker Compose 编排文件
- ✅ `backend/Dockerfile` - 后端服务镜像构建文件
- ✅ `frontend/Dockerfile` - 前端服务镜像构建文件
- ✅ `frontend/nginx.conf` - Nginx 配置文件

### 配置文件

- ✅ `env.docker.example` - 环境变量配置示例
- ✅ `backend/.dockerignore` - 后端构建忽略文件
- ✅ `frontend/.dockerignore` - 前端构建忽略文件

### 启动脚本

- ✅ `docker-start.sh` - Linux/Mac 快速启动脚本
- ✅ `docker-start.bat` - Windows 快速启动脚本

### 文档

- ✅ `Docker部署说明.md` - 详细部署文档

## 🚀 快速开始（3 步）

### 1. 配置环境变量

**重要：`.env.docker` 文件必须放在项目根目录（与 `docker-compose.yml` 同级）**

```bash
# 在项目根目录下执行（与 docker-compose.yml 同级）
# 复制示例文件
cp env.docker.example .env.docker

# 编辑配置文件，填入主项目的连接信息
# Windows: notepad .env.docker
# Linux/Mac: nano .env.docker
```

**必须配置的项：**

- `DATABASE_URL` - 主项目 PostgreSQL 连接
- `OLLAMA_URL` - 主项目 Ollama 服务地址

### 2. 配置网络连接

编辑 `docker-compose.yml`，找到主项目的网络名称：

```yaml
networks:
  main-network:
    external: true
    name: 主项目的实际网络名称 # 修改这里
```

取消注释 `backend` 和 `backend-init` 服务中的网络配置。

### 3. 启动服务

**方式一：使用启动脚本（推荐）**

```bash
# Linux/Mac
chmod +x docker-start.sh
./docker-start.sh

# Windows
docker-start.bat
```

**方式二：手动启动**

```bash
docker-compose build
docker-compose up -d
```

## 🌐 访问地址

- **前端**: http://localhost
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/api/health

## 📝 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 重新构建
docker-compose up -d --build
```

## ⚠️ 重要提示

1. **Ollama 和 PostgreSQL 不包含在 DRIA 的 Docker 中**

   - 它们应该连接到主项目的服务
   - 通过 Docker 网络或主机网络连接

2. **数据持久化**

   - `backend/uploads/` - 上传的文件
   - `backend/reports/` - 生成的报表
   - `backend/config_sessions/` - 配置会话

3. **网络配置**
   - 确保主项目的网络名称正确
   - 确保服务名称（如 `main-postgres`、`main-ollama`）正确

## 🔧 故障排查

### 无法连接数据库

```bash
docker-compose exec backend ping main-postgres
```

### 无法连接 Ollama

```bash
docker-compose exec backend curl http://main-ollama:11434/api/tags
```

### 查看详细日志

```bash
docker-compose logs backend
docker-compose logs frontend
```

## 📚 更多信息

详细文档请参考：`Docker部署说明.md`
