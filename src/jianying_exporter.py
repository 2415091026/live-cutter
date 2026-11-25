# -*- coding: utf-8 -*-
"""
剪映专业版草稿导出引擎 (JianYing Draft Exporter)
基于剪映工程协议标准，自动生成原生的 draft_content.json 与 draft_meta_info.json 工程，
让切片师能在剪映客户端一键打开排布好视频轨与字幕花字轨的项目，实现 10 秒无缝微调与导出！
"""

import os
import sys
import json
import time
import uuid
import shutil
from typing import List, Dict, Any, Optional

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class JianYingDraftExporter:
    """剪映草稿工程导出器"""

    def __init__(self, custom_drafts_dir: Optional[str] = None):
        """
        :param custom_drafts_dir: 自定义剪映工程目录（若不指定则自动探测系统默认路径）
        """
        self.drafts_dir = self._detect_jianying_dir(custom_drafts_dir)

    def _detect_jianying_dir(self, custom_dir: Optional[str]) -> str:
        """探测剪映工程目录"""
        if custom_dir and os.path.exists(custom_dir):
            return os.path.abspath(custom_dir)

        # 1. 尝试常见的 Windows 剪映默认路径
        local_app_data = os.getenv("LOCALAPPDATA", "")
        possible_paths = [
            os.path.join(local_app_data, "JianyingPro", "User Data", "Projects", "com.lveditor.draft"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "JianyingPro", "User Data", "Projects", "com.lveditor.draft"),
            "D:\\JianyingPro Drafts\\com.lveditor.draft",
            "E:\\JianyingPro Drafts\\com.lveditor.draft"
        ]

        for p in possible_paths:
            if os.path.exists(p):
                print(f"[剪映引擎] 成功识别到系统剪映专业版工程目录: {p}")
                return p

        # 2. 本地备用目录
        fallback_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "drafts")
        )
        os.makedirs(fallback_dir, exist_ok=True)
        print(f"[剪映引擎] 未在系统盘找到默认剪映安装，将导出至独立工程目录: {fallback_dir}")
        return fallback_dir

    def export_draft(
        self,
        draft_title: str,
        video_path: str,
        start_sec: float,
        end_sec: float,
        subtitles: List[Dict[str, Any]],
        fps: int = 30
    ) -> str:
        """
        生成标准的剪映专业版工程草稿
        :param draft_title: 工程名称
        :param video_path: 视频素材绝对路径
        :param start_sec: 剪入起始秒数
        :param end_sec: 剪出结束秒数
        :param subtitles: 句级字幕列表 [{"start": 1.0, "end": 3.0, "text": "xxx"}]
        :param fps: 帧率
        :return: 生成的剪映草稿文件夹绝对路径
        """
        abs_video_path = os.path.abspath(video_path).replace("/", "\\")
        if not os.path.exists(abs_video_path):
            raise FileNotFoundError(f"视频素材不存在: {abs_video_path}")

        # 计算时长（微秒单位: 1秒 = 1,000,000 微秒）
        duration_sec = max(0.5, end_sec - start_sec)
        duration_us = int(duration_sec * 1_000_000)
        source_start_us = int(start_sec * 1_000_000)

        # 规范化工程文件夹名称
        project_uuid = str(uuid.uuid4()).upper()
        clean_title = "".join([c for c in draft_title if c.isalnum() or c in ("_", "-")]) or "直播切片"
        folder_name = f"{clean_title}_{project_uuid[:8]}"
        project_dir = os.path.join(self.drafts_dir, folder_name)
        os.makedirs(project_dir, exist_ok=True)

        now_time_us = int(time.time() * 1_000_000)
        video_material_id = str(uuid.uuid4())
        video_segment_id = str(uuid.uuid4())

        # 1. 构造 materials.videos
        materials_videos = [{
            "id": video_material_id,
            "path": abs_video_path,
            "type": "video",
            "duration": int(3600 * 1_000_000), # 原始全长或富余值
            "width": 1080,
            "height": 1920
        }]

        # 2. 构造 materials.texts (字幕材料) 与 text track segments
        materials_texts = []
        text_track_segments = []

        for sub in subtitles:
            sub_id = str(uuid.uuid4())
            sub_seg_id = str(uuid.uuid4())
            # 相对于切片起点的偏移
            rel_start = max(0.0, sub["start"] - start_sec)
            rel_end = min(duration_sec, sub["end"] - start_sec)
            if rel_start >= rel_end:
                continue

            sub_start_us = int(rel_start * 1_000_000)
            sub_duration_us = int((rel_end - rel_start) * 1_000_000)

            # 剪映文本材质对象
            text_item = {
                "id": sub_id,
                "content": json.dumps({"text": sub["text"]}, ensure_ascii=False),
                "font_size": 8.0,
                "text_color": "#FFD700", # 抖音经典高亮醒目黄
                "border_color": "#000000",
                "border_width": 2.0,
                "type": "subtitle"
            }
            materials_texts.append(text_item)

            text_track_segments.append({
                "id": sub_seg_id,
                "material_id": sub_id,
                "target_timerange": {
                    "start": sub_start_us,
                    "duration": sub_duration_us
                }
            })

        # 3. 构造 tracks
        tracks = [
            # 视频轨道
            {
                "id": str(uuid.uuid4()),
                "type": "video",
                "segments": [
                    {
                        "id": video_segment_id,
                        "material_id": video_material_id,
                        "source_timerange": {
                            "start": source_start_us,
                            "duration": duration_us
                        },
                        "target_timerange": {
                            "start": 0,
                            "duration": duration_us
                        }
                    }
                ]
            },
            # 字幕轨道
            {
                "id": str(uuid.uuid4()),
                "type": "text",
                "segments": text_track_segments
            }
        ]

        # 4. 组装 draft_content.json
        draft_content = {
            "canvas_config": {
                "width": 1080,
                "height": 1920,
                "ratio": "9:16"
            },
            "duration": duration_us,
            "fps": fps,
            "materials": {
                "videos": materials_videos,
                "texts": materials_texts,
                "speeds": [],
                "transitions": []
            },
            "tracks": tracks,
            "version": 3000000
        }

        content_path = os.path.join(project_dir, "draft_content.json")
        with open(content_path, "w", encoding="utf-8") as f:
            json.dump(draft_content, f, ensure_ascii=False, indent=2)

        # 5. 组装 draft_meta_info.json
        draft_meta = {
            "draft_id": project_uuid,
            "draft_name": draft_title,
            "draft_removable_storage_device": False,
            "tm_draft_create": now_time_us,
            "tm_draft_modified": now_time_us,
            "tm_duration": duration_us
        }
        meta_path = os.path.join(project_dir, "draft_meta_info.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(draft_meta, f, ensure_ascii=False, indent=2)

        print(f"[剪映引擎] ✨ 成功导出剪映专业版工程草稿: {project_dir}")
        print(f"         • 剪入剪出: {start_sec}s -> {end_sec}s (时长: {duration_sec:.2f}s)")
        print(f"         • 导入字幕: {len(subtitles)} 句已自动打轴入轨")
        return project_dir


if __name__ == "__main__":
    test_video = "../recordings/live_80017709309_20261102_171325_5s.mp4"
    if os.path.exists(test_video):
        exporter = JianYingDraftExporter()
        mock_subs = [
            {"start": 0.5, "end": 2.0, "text": "主播进场三秒钟"},
            {"start": 2.2, "end": 4.2, "text": "直接当场破防退钱！"}
        ]
        res = exporter.export_draft(
            draft_title="测试导出东方甄选名场面",
            video_path=test_video,
            start_sec=0.0,
            end_sec=4.5,
            subtitles=mock_subs
        )
        print("工程目录:", res)
