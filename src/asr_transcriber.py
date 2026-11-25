# -*- coding: utf-8 -*-
"""
ASR 语音转录引擎 (Whisper Transcriber)
基于 Faster-Whisper 实现毫秒级语音转文字，并输出带精确时间戳的字幕分段与 SRT 文本
"""

import os
import sys
import subprocess
from typing import List, Dict, Any, Optional
from faster_whisper import WhisperModel

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class ASRTranscriber:
    """语音识别转录器"""

    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
        """
        :param model_size: 模型规格 ('tiny', 'base', 'small', 'medium', 'large-v3')，tiny/base 极快且轻量
        :param device: 'cpu' 或 'cuda'
        :param compute_type: 'int8' 或 'float16'
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[WhisperModel] = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            print(f"[ASR引擎] 正在加载 Whisper 模型 ({self.model_size}, 设备: {self.device})...")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self._model

    def extract_segment_audio(self, video_path: str, start_sec: float, end_sec: float, output_wav: str) -> bool:
        """从指定视频切出候选区间的独立 16kHz WAV 音频用于高精识别"""
        duration = end_sec - start_sec
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            output_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0 and os.path.exists(output_wav) and os.path.getsize(output_wav) > 0

    def transcribe(self, audio_or_video_path: str, language: str = "zh") -> List[Dict[str, Any]]:
        """
        执行语音识别 (采用原生 wave+numpy 读取，彻底规避 PyAV 版本兼容问题)
        :param audio_or_video_path: 视频或音频文件路径
        :param language: 语种，默认中文 'zh'
        :return: 句子列表，每项包含 start, end, text
        """
        import wave
        import numpy as np

        model = self._get_model()

        # 确保输入是标准的 16kHz WAV 单声道
        temp_wav = None
        target_wav = audio_or_video_path

        if not audio_or_video_path.endswith(".wav"):
            temp_wav = audio_or_video_path + ".asr_temp.wav"
            cmd = [
                "ffmpeg", "-y", "-i", audio_or_video_path,
                "-vn", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
                temp_wav
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            target_wav = temp_wav

        try:
            # 直接使用 wave 读取，规避 av.open 的 metadata_errors 传参问题
            with wave.open(target_wav, "rb") as wf:
                raw_frames = wf.readframes(wf.getnframes())
                audio_np = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0

            segments_raw, info = model.transcribe(
                audio_np,
                language=language,
                vad_filter=True,
                beam_size=5
            )

            results = []
            for seg in segments_raw:
                text = seg.text.strip()
                if text:
                    results.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": text
                    })
            return results
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    @staticmethod
    def generate_srt(segments: List[Dict[str, Any]], offset_sec: float = 0.0) -> str:
        """
        将分段字幕转为标准 SRT 格式
        :param segments: 分段列表
        :param offset_sec: 时间轴偏移基准（秒）
        """
        def format_time(seconds: float) -> str:
            millis = int((seconds % 1) * 1000)
            seconds = int(seconds)
            mins, secs = divmod(seconds, 60)
            hours, mins = divmod(mins, 60)
            return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

        srt_lines = []
        for idx, seg in enumerate(segments, 1):
            s_time = format_time(seg["start"] + offset_sec)
            e_time = format_time(seg["end"] + offset_sec)
            srt_lines.append(str(idx))
            srt_lines.append(f"{s_time} --> {e_time}")
            srt_lines.append(seg["text"])
            srt_lines.append("")

        return "\n".join(srt_lines)


if __name__ == "__main__":
    test_video = "../recordings/live_80017709309_20261102_171325_5s.mp4"
    if os.path.exists(test_video):
        print("=== 测试 ASR 语音识别 ===")
        transcriber = ASRTranscriber(model_size="tiny")
        segs = transcriber.transcribe(test_video)
        print(f"识别结果分段数量: {len(segs)}")
        for s in segs:
            print(f"[{s['start']}s -> {s['end']}s] {s['text']}")
        print("\n=== SRT 格式预览 ===")
        print(transcriber.generate_srt(segs))
