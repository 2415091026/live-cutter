# -*- coding: utf-8 -*-
"""
多模态热度融合打分引擎 (Heat Scorer & Fusion Engine)
将音频能量突变、弹幕密度激增与情绪关键词在统一时间轴上对齐融合，
自动输出具有起承转合上下文的【高价值候选切片区间】
"""

import os
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# 保证 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class CandidateSegment:
    """高价值候选切片结构体"""
    segment_id: str             # 切片唯一标识
    start_time: float           # 推荐开始时间戳 (秒)
    end_time: float             # 推荐结束时间戳 (秒)
    duration: float             # 总时长 (秒)
    peak_time: float            # 高潮核心时间点 (秒)
    heat_score: int             # 综合热度评分 (0-100)
    trigger_type: str           # 触发类型 (audio_burst / danmu_surge / fusion)
    reason: str                 # 推荐理由简述
    keywords: List[str]         # 命中的高频词


class HeatScorer:
    """多模态热度打分器"""

    def __init__(
        self,
        lead_in_sec: float = 6.0,
        tail_sec: float = 6.0,
        min_duration_sec: float = 12.0,
        max_duration_sec: float = 120.0
    ):
        """
        :param lead_in_sec: 爆点前预留秒数（交代前因）
        :param tail_sec: 爆点后延展秒数（交代结局）
        :param min_duration_sec: 切片最短时长
        :param max_duration_sec: 切片最长时长
        """
        self.lead_in = lead_in_sec
        self.tail = tail_sec
        self.min_duration = min_duration_sec
        self.max_duration = max_duration_sec

    def fuse(
        self,
        audio_peaks: List[Dict[str, Any]],
        danmu_peaks: Optional[List[Dict[str, Any]]] = None,
        total_video_duration: float = 0.0
    ) -> List[CandidateSegment]:
        """
        融合音频波峰与弹幕峰值，聚类生成高价值切片候选
        :param audio_peaks: AudioEnergyAnalyzer 产出的波峰列表
        :param danmu_peaks: 弹幕时间窗口峰值列表
        :param total_video_duration: 视频总时长 (秒)
        :return: 候选切片列表，按热度评分降序排列
        """
        events = []

        # 1. 转换音频波峰事件
        for idx, ap in enumerate(audio_peaks):
            p_time = (ap["start_time"] + ap["end_time"]) / 2.0
            intensity = ap.get("peak_intensity", 1.0)
            score = min(100, int(50 + intensity * 20))
            events.append({
                "source": "audio",
                "peak_time": p_time,
                "start": ap["start_time"],
                "end": ap["end_time"],
                "score": score,
                "intensity": intensity,
                "keywords": []
            })

        # 2. 转换弹幕峰值事件 (如有)
        if danmu_peaks:
            for dp in danmu_peaks:
                events.append({
                    "source": "danmu",
                    "peak_time": dp["time"],
                    "start": dp["time"] - 2.0,
                    "end": dp["time"] + 2.0,
                    "score": dp.get("score", 60),
                    "intensity": dp.get("density", 1.0),
                    "keywords": dp.get("keywords", [])
                })

        if not events:
            return []

        # 按峰值时间排序
        events.sort(key=lambda x: x["peak_time"])

        # 3. 时间邻近聚类（容差 5 秒内的事件视为同一场高潮）
        clusters = []
        current_cluster = [events[0]]

        for ev in events[1:]:
            last_ev = current_cluster[-1]
            if ev["peak_time"] - last_ev["peak_time"] <= 5.0:
                current_cluster.append(ev)
            else:
                clusters.append(current_cluster)
                current_cluster = [ev]
        clusters.append(current_cluster)

        # 4. 为每个聚类生成 CandidateSegment
        candidate_list: List[CandidateSegment] = []
        for c_idx, cluster in enumerate(clusters, 1):
            sources = set(e["source"] for e in cluster)
            peak_time = sum(e["peak_time"] for e in cluster) / len(cluster)
            
            # 双模态交叉触发则享受热度加权！
            has_audio = "audio" in sources
            has_danmu = "danmu" in sources

            max_score = max(e["score"] for e in cluster)
            if has_audio and has_danmu:
                trigger_type = "fusion (音画双爆)"
                final_score = min(100, max_score + 20)
                reason = "主播情绪爆发同时引发弹幕刷屏，观众与主播产生强烈共鸣"
            elif has_audio:
                trigger_type = "audio_burst (情绪高涨)"
                final_score = max_score
                reason = "主播声量显著激增，疑似产生爆梗、激烈争辩或大笑破防"
            else:
                trigger_type = "danmu_surge (互动高潮)"
                final_score = max_score
                reason = "弹幕发送频率剧烈攀升，观众反响热烈"

            # 汇总关键词
            all_keywords = []
            for e in cluster:
                all_keywords.extend(e.get("keywords", []))
            all_keywords = list(set(all_keywords))

            # 计算上下文边界
            raw_start = min(e["start"] for e in cluster)
            raw_end = max(e["end"] for e in cluster)

            cand_start = max(0.0, raw_start - self.lead_in)
            cand_end = raw_end + self.tail
            if total_video_duration > 0:
                cand_end = min(total_video_duration, cand_end)

            duration = cand_end - cand_start
            # 补足最小限制
            if duration < self.min_duration:
                deficit = self.min_duration - duration
                cand_start = max(0.0, cand_start - deficit / 2)
                cand_end = cand_end + deficit / 2
                if total_video_duration > 0:
                    cand_end = min(total_video_duration, cand_end)
                duration = cand_end - cand_start

            candidate_list.append(CandidateSegment(
                segment_id=f"seg_{int(peak_time):04d}",
                start_time=round(cand_start, 2),
                end_time=round(cand_end, 2),
                duration=round(duration, 2),
                peak_time=round(peak_time, 2),
                heat_score=final_score,
                trigger_type=trigger_type,
                reason=reason,
                keywords=all_keywords
            ))

        # 按热度得分从高到低排序
        candidate_list.sort(key=lambda x: x.heat_score, reverse=True)
        return candidate_list
