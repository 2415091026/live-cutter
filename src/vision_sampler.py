# -*- coding: utf-8 -*-
"""
多模态视觉关键帧采样器 (Vision Frame Sampler)
用于从候选视频区间内按时间轴均匀抽取关键帧，压缩编码为 Base64 Data URL，
供 qwen3.8-omni-flash 等多模态大模型进行画面动作识别、表情破防捕捉与视觉起止点对齐。
"""

import os
import base64
import tempfile
import subprocess
from typing import List, Dict, Any


class VisionFrameSampler:
    """基于 FFmpeg 的极速视频关键帧采样器"""

    @staticmethod
    def sample_frames_base64(
        video_path: str,
        start_time: float,
        end_time: float,
        num_frames: int = 6,
        max_width: int = 640
    ) -> List[Dict[str, Any]]:
        """
        在指定视频的 [start_time, end_time] 区间内均匀抽取 num_frames 张关键帧
        :return: [{"timestamp": 12.5, "data_url": "data:image/jpeg;base64,..."}, ...]
        """
        if not video_path or not os.path.exists(video_path):
            return []

        duration = max(1.0, end_time - start_time)
        num_frames = max(2, min(num_frames, 9))
        step = duration / (num_frames + 1)

        sampled: List[Dict[str, Any]] = []
        for idx in range(1, num_frames + 1):
            ts = round(start_time + step * idx, 2)
            tmp_jpg = os.path.join(
                tempfile.gettempdir(),
                f"lc_frame_{os.getpid()}_{idx}_{int(ts * 100)}.jpg"
            )
            try:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss", str(ts),
                    "-i", video_path,
                    "-vframes", "1",
                    "-vf", f"scale={max_width}:-1",
                    "-q:v", "5",
                    tmp_jpg
                ]
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=6
                )
                if os.path.exists(tmp_jpg) and os.path.getsize(tmp_jpg) > 200:
                    with open(tmp_jpg, "rb") as f:
                        b64_str = base64.b64encode(f.read()).decode("utf-8")
                    sampled.append({
                        "timestamp": ts,
                        "data_url": f"data:image/jpeg;base64,{b64_str}"
                    })
            except Exception as e:
                print(f"[视觉抽帧警告] 抽取 {ts}s 关键帧失败: {e}")
            finally:
                if os.path.exists(tmp_jpg):
                    try:
                        os.remove(tmp_jpg)
                    except Exception:
                        pass

        return sampled

