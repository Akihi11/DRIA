"""最简单的启动脚本 - 用于调试"""
import uvicorn

if __name__ == "__main__":
    print("启动服务器...")
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )

