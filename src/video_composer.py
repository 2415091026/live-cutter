# -*- coding: utf-8 -*-
"""
直发级短视频全自动合成包装引擎 (Video Composer Pro)
特性：
1. 9:16 (1080x1920) 竖屏自适应构图 + 动态高斯虚化背景
2. 顶部爆款黄金吸睛标题条压制
3. 底部抖音同频高对比花字字幕烧录 (1080P清晰大字加粗描边)
4. NVIDIA NVENC 硬件加速极速编码 (秒级渲染成片，自动回退 CPU)
"""

import os
import sys
import subprocess
import json
import re
from typing import List, Dict, Any, Optional

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class VideoComposer:
    """直发级自动化短视频合成器"""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            self.output_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "output")
            )
        else:
            self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.has_nvenc = self._check_nvenc()

    def _check_nvenc(self) -> bool:
        """检测系统是否支持 NVIDIA NVENC 硬件加速"""
        try:
            cmd = ["ffmpeg", "-encoders"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
            return "h264_nvenc" in res.stdout
        except Exception:
            return False

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频的分辨率、帧率与时长信息"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            video_path
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        try:
            data = json.loads(res.stdout)
            video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
            return {
                "width": int(video_stream["width"]),
                "height": int(video_stream["height"]),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "is_vertical": int(video_stream["height"]) > int(video_stream["width"])
            }
        except Exception:
            return {"width": 1080, "height": 1920, "duration": 0, "is_vertical": True}

    def trim_fast(self, input_video: str, start_sec: float, end_sec: float, output_path: str) -> bool:
        """极速无损剪切"""
        duration = max(0.5, end_sec - start_sec)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", input_video,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0

    def _generate_ass_subtitles(self, srt_content: str, ass_path: str, title: str = "") -> bool:
        """
        生成高质量 ASS 动态花字字幕文件
        包含：
        1. TitleBanner 样式：顶部爆款大标题 (白字黄底描边，黄金吸睛位)
        2. Dialogue 样式：底部短视频爆款大字幕 (亮黄加粗高光，黑边阴影，字号42)
        """
        # 头部样式配置
        ass_header = (
            "[Script Info]\n"
            "Title: LiveCutter Auto Packaging\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n"
            "YCbCr Matrix: TV.601\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Microsoft YaHei,46,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3.5,1.5,2,40,40,160,1\n"
            "Style: TitleHeader,Microsoft YaHei,50,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,4.0,2.0,8,40,40,140,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        events = []

        # 1. 顶部爆款标题 (贯穿全片，位置置顶居中)
        if title:
            clean_title = re.sub(r'[\r\n]', ' ', title).strip()
            # 顶部标题添加醒目修饰
            formatted_title = f"{{\\b1\\c&H00F5FF\\3c&H000000\\shad2}}「 {clean_title} 」"
            events.append(f"Dialogue: 1,0:00:00.00,9:59:59.00,TitleHeader,,0,0,0,,{formatted_title}")

        # 2. 解析 SRT 转换为 ASS 底部高能花字
        if srt_content:
            srt_blocks = srt_content.strip().split("\n\n")
            for block in srt_blocks:
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                if len(lines) >= 3 and "-->" in lines[1]:
                    time_line = lines[1]
                    text = "".join(lines[2:])
                    # 转换时间 00:01:23,456 -> 0:01:23.45
                    m = re.match(r'(\d+):(\d+):(\d+)[,\.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,\.](\d+)', time_line)
                    if m:
                        sh, sm, ss, sms = m.group(1), m.group(2), m.group(3), m.group(4)[:2]
                        eh, em, es, ems = m.group(5), m.group(6), m.group(7), m.group(8)[:2]
                        start_ass = f"{int(sh)}:{sm}:{ss}.{sms}"
                        end_ass = f"{int(eh)}:{em}:{es}.{ems}"
                        # 底部花字：黄字黑边 + 柔和阴影
                        styled_text = f"{{\\b1\\c&H00D7FF\\3c&H000000\\shad2}}{text}"
                        events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{styled_text}")

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(events) + "\n")

        return True

    def compose_short(
        self,
        input_video: str,
        start_sec: float,
        end_sec: float,
        title: str = "",
        srt_content: str = "",
        output_filename: Optional[str] = None
    ) -> Optional[str]:
        """
        全自动直发级成片渲染：
        - 9:16 (1080x1920) 竖屏画幅自适应
        - 动态高斯模糊背景铺满
        - 顶部爆款标题条压制
        - 底部抖音黄色同频大花字压制
        - NVENC 极速硬件编码加速
        """
        if not os.path.exists(input_video):
            raise FileNotFoundError(f"输入视频不存在: {input_video}")

        duration = max(1.0, end_sec - start_sec)
        info = self.get_video_info(input_video)
        is_vertical = info["is_vertical"]

        if not output_filename:
            output_filename = f"short_{int(start_sec)}_{int(end_sec)}.mp4"
        final_output = os.path.join(self.output_dir, output_filename)

        # 生成 ASS 花字字幕文件 (支持 Windows 特殊转义)
        temp_ass = os.path.join(self.output_dir, f"temp_{int(start_sec)}.ass")
        self._generate_ass_subtitles(srt_content, temp_ass, title=title)

        escaped_ass_path = temp_ass.replace("\\", "/").replace(":", "\\:")
        sub_filter = f"ass='{escaped_ass_path}'"

        print(f"[直发渲染引擎] 准备成片: 时长 {duration:.2f}s | 原画幅: {'竖屏 9:16' if is_vertical else '横屏'} | NVENC加速: {self.has_nvenc}")

        # 滤镜链：保证横屏自动转 9:16 居中并加动态高斯虚化背景
        if is_vertical:
            filter_complex = f"[0:v]scale=1080:1920,{sub_filter}[v]"
        else:
            # [bg]: 铺满 1080x1920，加高斯虚化 boxblur=25:5
            # [fg]: 居中等比缩放至 1080 宽
            # [overlay]: 合成前景与背景并烧录顶底花字
            filter_complex = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,boxblur=24:4[bg];"
                "[0:v]scale=1080:-1[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{sub_filter}[v]"
            )

        # 编码器选择：优先 NVIDIA NVENC 硬件加速
        if self.has_nvenc:
            vcodec_params = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "6M"]
        else:
            vcodec_params = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            *vcodec_params,
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            final_output
        ]

        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(final_output) and os.path.getsize(final_output) > 0:
                mb = os.path.getsize(final_output) / (1024 * 1024)
                print(f"[渲染成功] 直发级 9:16 成品短视频已就绪: {final_output} (大小: {mb:.2f} MB)")
                return final_output
            else:
                err_msg = p.stderr.decode('utf-8', errors='ignore')
                print(f"[硬件渲染警告] 发生回退重试: {err_msg[:200]}")
                # 若硬件编码器异常，降级回 CPU 纯 libx264 兜底
                cmd_cpu = [
                    "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration),
                    "-i", input_video, "-filter_complex", filter_complex,
                    "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                    final_output
                ]
                subprocess.run(cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(final_output) and os.path.getsize(final_output) > 0:
                    return final_output
                # 极端情况无损快剪兜底
                if self.trim_fast(input_video, start_sec, end_sec, final_output):
                    return final_output
                return None
        finally:
            if os.path.exists(temp_ass):
                try:
                    os.remove(temp_ass)
                except Exception:
                    pass
