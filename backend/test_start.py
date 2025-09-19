"""临时测试启动脚本"""
import sys
import os
from pathlib import Path

print("=== 测试步骤 1: 编码设置 ===")
try:
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    print("[OK] 编码设置成功")
except Exception as e:
    print(f"[ERROR] 编码设置失败: {e}")
    sys.exit(1)

print("\n=== 测试步骤 2: 路径设置 ===")
try:
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    print(f"[OK] 当前目录: {current_dir}")
except Exception as e:
    print(f"[ERROR] 路径设置失败: {e}")
    sys.exit(1)

print("\n=== 测试步骤 3: 导入配置 ===")
try:
    from config import settings
    print(f"[OK] API_HOST: {settings.API_HOST}")
    print(f"[OK] API_PORT: {settings.API_PORT}")
except Exception as e:
    print(f"[ERROR] 配置导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== 测试步骤 4: 导入API ===")
try:
    from api.main import app
    print("[OK] API模块导入成功")
except Exception as e:
    print(f"[ERROR] API导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== 测试步骤 5: 导入uvicorn ===")
try:
    import uvicorn
    print("[OK] uvicorn导入成功")
except Exception as e:
    print(f"[ERROR] uvicorn导入失败: {e}")
    sys.exit(1)

print("\n=== 所有测试通过，准备启动服务器 ===")
print(f"将在 http://{settings.API_HOST}:{settings.API_PORT} 启动服务器")
print("\n按 Ctrl+C 取消，或等待3秒自动启动...")

import time
time.sleep(3)

print("\n=== 启动服务器 ===")
try:
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower()
    )
except Exception as e:
    print(f"[ERROR] 服务器启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

