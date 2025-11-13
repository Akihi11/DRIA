#!/bin/bash
# DRIA Docker 快速启动脚本

set -e

echo "🚀 DRIA Docker 部署脚本"
echo "========================"

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ 错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: docker-compose 未安装"
    exit 1
fi

# 检查环境变量文件
if [ ! -f ".env.docker" ]; then
    echo "⚠️  警告: .env.docker 文件不存在"
    echo "📝 正在从示例文件创建..."
    if [ -f "env.docker.example" ]; then
        cp env.docker.example .env.docker
        echo "✅ 已创建 .env.docker 文件，请编辑并填入实际配置"
        echo "   编辑命令: nano .env.docker 或 notepad .env.docker"
        exit 1
    else
        echo "❌ 错误: env.docker.example 文件不存在"
        exit 1
    fi
fi

# 构建镜像
echo ""
echo "📦 正在构建 Docker 镜像..."
docker-compose build

# 启动服务
echo ""
echo "🚀 正在启动服务..."
docker-compose --env-file .env.docker up -d

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "📊 服务状态:"
docker-compose ps

# 显示访问信息
echo ""
echo "✅ 部署完成！"
echo ""
echo "🌐 访问地址:"
echo "   - 前端: http://localhost"
echo "   - 后端API: http://localhost:8000"
echo "   - API文档: http://localhost:8000/api/docs"
echo "   - 健康检查: http://localhost:8000/api/health"
echo ""
echo "📝 常用命令:"
echo "   - 查看日志: docker-compose logs -f"
echo "   - 停止服务: docker-compose down"
echo "   - 重启服务: docker-compose restart"
echo ""

