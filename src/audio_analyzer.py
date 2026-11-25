# -*- coding: utf-8 -*-
"""
音频能量分析引擎 (Audio Energy Analyzer)
用于从直播录像中快速提取波形分贝（RMS能量）并自动定位主播情绪爆发、大笑、大叫等高能时间点
"""

import os
import subprocess
import struct
import math
from typing import List, Dict, Any, Tuple
import numpy as np


class AudioEnergyAnalyzer:
    """音频短时能量与波峰分析器"""

    def __init__(self, sample_rate: int = 16000, window_sec: float = 0.5):
        """
        :param sample_rate: 采样率，默认 16kHz（适合语音分析）
        :param window_sec: 分析窗口时长（秒），默认每 0.5 秒计算一次平均能量
        """
        self.sample_rate = sample_rate
        self.window_sec = window_sec
        self.chunk_size = int(sample_rate * window_sec)

    def extract_pcm_from_video(self, video_path: str, pcm_path: str) -> bool:
        """调用 FFmpeg 从视频中快速提取单声道 PCM 音频裸数据"""
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", str(self.sample_rate),
            "-f", "s16le",
            pcm_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0 and os.path.exists(pcm_path) and os.path.getsize(pcm_path) > 0

    def analyze_peaks(
        self,
        video_path: str,
        threshold_multiplier: float = 1.35,
        min_duration_sec: float = 2.0
    ) -> Dict[str, Any]:
        """
        分析视频中音频能量波峰
        :param video_path: 视频文件路径
        :param threshold_multiplier: 能量突增阈值系数（均值 + 系数 * 标准差）
        :param min_duration_sec: 认定为高潮区间的最小持续时长
        :return: 包含波峰时间区间与统计特征的字典
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        temp_pcm = video_path + ".temp.pcm"
        try:
            success = self.extract_pcm_from_video(video_path, temp_pcm)
            if not success:
                print(f"[警告] 提取音频失败，视频可能无音轨: {video_path}")
                return {"peaks": [], "avg_energy": 0, "max_energy": 0}

            # 读取 PCM 数据并计算 RMS (均方根) 能量
            with open(temp_pcm, "rb") as f:
                raw_bytes = f.read()

            num_samples = len(raw_bytes) // 2
            if num_samples == 0:
                return {"peaks": [], "avg_energy": 0, "max_energy": 0}

            # 转换为 16 位有符号整数序列
            audio_data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)

            # 窗口分段计算 RMS 能量
            energies = []
            timestamps = []
            total_windows = len(audio_data) // self.chunk_size

            for i in range(total_windows):
                chunk = audio_data[i * self.chunk_size : (i + 1) * self.chunk_size]
                # RMS 计算: sqrt(mean(chunk^2))
                rms = np.sqrt(np.mean(chunk**2)) + 1e-6
                # 换算为分贝 dBFS
                db = 20 * np.log10(rms / 32768.0)
                energies.append(rms)
                timestamps.append(i * self.window_sec)

            if not energies:
                return {"peaks": [], "avg_energy": 0, "max_energy": 0}

            energies = np.array(energies)
            avg_energy = float(np.mean(energies))
            std_energy = float(np.std(energies))
            max_energy = float(np.max(energies))

            # 动态能量阈值：高于平均值 + N倍标准差 视为情绪高潮/大叫
            peak_threshold = avg_energy + threshold_multiplier * std_energy

            # 寻找连续超过阈值的能量区间
            peaks: List[Dict[str, Any]] = []
            in_peak = False
            start_time = 0.0
            peak_max_rms = 0.0

            for idx, (t, e) in enumerate(zip(timestamps, energies)):
                if e >= peak_threshold:
                    if not in_peak:
                        in_peak = True
                        start_time = t
                        peak_max_rms = e
                    else:
                        peak_max_rms = max(peak_max_rms, e)
                else:
                    if in_peak:
                        in_peak = False
                        end_time = t
                        duration = end_time - start_time
                        if duration >= min_duration_sec:
                            peaks.append({
                                "start_time": round(start_time, 2),
                                "end_time": round(end_time, 2),
                                "duration": round(duration, 2),
                                "peak_intensity": round(float(peak_max_rms / (avg_energy + 1e-5)), 2),
                                "type": "audio_burst"  # 音量爆发型
                            })

            # 如果末尾还在波峰内
            if in_peak:
                end_time = timestamps[-1] + self.window_sec
                duration = end_time - start_time
                if duration >= min_duration_sec:
                    peaks.append({
                        "start_time": round(start_time, 2),
                        "end_time": round(end_time, 2),
                        "duration": round(duration, 2),
                        "peak_intensity": round(float(peak_max_rms / (avg_energy + 1e-5)), 2),
                        "type": "audio_burst"
                    })

            return {
                "peaks": peaks,
                "total_duration": round(total_windows * self.window_sec, 2),
                "avg_energy": round(avg_energy, 2),
                "max_energy": round(max_energy, 2),
                "threshold": round(peak_threshold, 2)
            }

        finally:
            if os.path.exists(temp_pcm):
                try:
                    os.remove(temp_pcm)
                except Exception:
                    pass


if __name__ == "__main__":
    import sys
    # 测试对已有录像进行能量波峰分析
    analyzer = AudioEnergyAnalyzer()
    test_video = sys.argv[1] if len(sys.argv) > 1 else "../recordings/live_80017709309_20261102_171325_5s.mp4"
    if os.path.exists(test_video):
        print(f"=== 正在分析音频能量波峰: {test_video} ===")
        res = analyzer.analyze_peaks(test_video, min_duration_sec=0.5)
        print(f"总时长: {res['total_duration']} 秒")
        print(f"平均能量: {res['avg_energy']} | 峰值能量: {res['max_energy']} | 爆发阈值: {res['threshold']}")
        print(f"检测到的波峰区间数量: {len(res['peaks'])}")
        for idx, p in enumerate(res["peaks"], 1):
            print(f"  [波峰 #{idx}] {p['start_time']}s -> {p['end_time']}s (持续: {p['duration']}s, 强度系数: {p['peak_intensity']}x)")
    else:
        print(f"测试视频不存在: {test_video}")
