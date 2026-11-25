# -*- coding: utf-8 -*-
"""
智能直播切片系统 - 现代可视化工作台一键启动器 (GUI Launcher)
运行该脚本将自动启动后台服务并在浏览器中打开现代化切片工作台
"""

import os
import sys
import webbrowser
import threading
import time
import uvicorn

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOST = "127.0.0.1"
PORT = 8765


def open_browser():
    """延迟 1.5 秒自动在默认浏览器中打开工作台"""
    time.sleep(1.5)
    url = f"http://{HOST}:{PORT}/"
    print(f"\n[启动器] 正在自动打开可视化工作台: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[提示] 请手动在浏览器中访问: {url}")


def main():
    print("=" * 65)
    print("   🚀 LIVE-CUTTER 智能直播切片系统 - 现代可视化工作台启动中")
    print("=" * 65)
    print(f"  • 服务地址: http://{HOST}:{PORT}/")
    print("  • 正在加载 AI 核心引擎 (推流/Whisper/Qwen/FFmpeg/剪映直通)...")
    print("  • 按 Ctrl+C 可随时停止服务\n")

    # 异步开启浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 uvicorn 服务（设置 2 秒优雅退出超时，防止 SSE/直播流长连接阻塞 Ctrl+C）
    uvicorn.run(
        "api_server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False,
        timeout_graceful_shutdown=2
    )


if __name__ == "__main__":
    main()
