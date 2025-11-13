# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt /app/backend/

# 安装Python依赖
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制应用代码到 /app/backend 目录结构
# 这样导入路径 from backend.xxx 可以正常工作
RUN mkdir -p /app/backend
COPY . /app/backend/

# 创建必要的目录
RUN mkdir -p /app/backend/uploads /app/backend/reports /app/backend/config_sessions

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8000

# 切换到 backend 目录并启动
WORKDIR /app/backend
CMD ["python", "main.py"]
