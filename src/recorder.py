# -*- coding: utf-8 -*-
"""
直播流录制引擎 (Stream Recorder Pipeline)
基于 FFmpeg 的高可靠直播流转存器，支持按时长自动切片、断线重连与无损封装
"""

import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from typing import Optional
from resolver import DouyinLiveResolver


class StreamRecorder:
    """直播录制器"""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            # 默认保存在项目的 recordings 目录下
            self.output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "recordings"))
        else:
            self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        self.resolver = DouyinLiveResolver()
        self._current_process: Optional[subprocess.Popen] = None
        self._stop_requested = False

        # 仅在主线程中注册平滑退出信号，避免在 Web 工作线程中抛出 ValueError
        import threading
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self._handle_exit)
                signal.signal(signal.SIGTERM, self._handle_exit)
            except Exception:
                pass

    def _handle_exit(self, signum, frame):
        print("\n[系统通知] 收到中断信号，正在安全结束录制...")
        self._stop_requested = True
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=5)
            except Exception:
                self._current_process.kill()
        sys.exit(0)

    def record_once(self, target: str, duration_seconds: int = 10, filename: Optional[str] = None) -> Optional[str]:
        """
        单次定长录制（用于测试验证或指定短片段截取）
        :param target: 房间号或直播间链接
        :param duration_seconds: 录制时长 (秒)
        :param filename: 输出文件名（可选）
        :return: 录制完成的本地文件路径
        """
        meta = self.resolver.resolve(target)
        if not meta or not meta.get("best_flv"):
            print(f"[错误] 无法获取直播间 {target} 的有效推流地址")
            return None

        if not meta["is_living"]:
            print(f"[提示] 直播间当前处于关播状态（状态码: {meta['status']}）")
            return None

        stream_url = meta["best_flv"]
        time_hms = datetime.now().strftime("%H-%M-%S")
        anchor = meta.get('anchor_name', '直播').replace('/', '_').replace('\\', '_').replace(' ', '')
        if not filename:
            filename = f"{time_hms}_{anchor}_{duration_seconds}s.mp4"
        output_path = os.path.join(self.output_dir, filename)

        print(f"[录制开始] 主播: {meta['anchor_name']} | 标题: {meta['title']}")
        print(f"[画质选择] 原画/高清 FLV: {stream_url[:65]}...")
        print(f"[保存路径] {output_path} (时长: {duration_seconds}秒)")

        cmd = [
            "ffmpeg",
            "-y",
            "-headers", f"User-Agent: {self.resolver.headers['User-Agent']}\r\nReferer: https://live.douyin.com/\r\n",
            "-i", stream_url,
            "-t", str(duration_seconds),
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_path
        ]

        try:
            self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = self._current_process.communicate()
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"[录制成功] 文件生成完毕: {output_path} (体积: {size_mb:.2f} MB)")
                return output_path
            else:
                print(f"[录制异常] 文件未成功生成，FFmpeg 输出日志:\n{stderr.decode('utf-8', errors='ignore')}")
                return None
        except Exception as e:
            print(f"[异常] 录制过程发生错误: {e}")
            return None
        finally:
            self._current_process = None

    def record_continuous_segmented(self, target: str, segment_duration_seconds: int = 300):
        """
        持续录制并按时间分片（工业流水线模式：如每5分钟存一个切片，支持边录边分析）
        :param target: 房间号或直播间链接
        :param segment_duration_seconds: 每个分片的时长 (默认 300 秒 / 5 分钟)
        """
        print(f"=== 启动持续录制分片模式（分片时长: {segment_duration_seconds} 秒）===")
        print("按 Ctrl+C 可随时安全退出录制。\n")

        part_index = 1
        while not self._stop_requested:
            # 每一轮录制前，重新解析获取新鲜的 Token 链接
            meta = self.resolver.resolve(target)
            if not meta or not meta.get("best_flv"):
                print("[重试] 无法获取直播源或主播可能已下播，15 秒后重试...")
                time.sleep(15)
                continue

            if not meta["is_living"]:
                print(f"[提示] 主播已关播，等待 30 秒重新检测...")
                time.sleep(30)
                continue

            time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"seg_{meta['web_rid']}_{time_tag}_part{part_index:03d}.mp4"
            print(f"\n--- [分片 #{part_index}] 开始录制: {filename} ---")

            saved_file = self.record_once(target, duration_seconds=segment_duration_seconds, filename=filename)
            if saved_file:
                part_index += 1
                print(f"--- [分片 #{part_index-1}] 录制已就绪，可立即触发流水线分析！---")
            else:
                print("[警告] 本轮分片录制未正常退出，等待 5 秒重试...")
                time.sleep(5)
