# -*- coding: utf-8 -*-
"""
AI 语义精筛与多模态智能断句定位引擎 (Semantic Filter & Multimodal Smart Trimmer)
支持可配置化切换：
- 经典声文极速方案 (qwen3.8-flash)
- 多模态音画全感知方案 (qwen3.8-omni-flash)
"""

import os
import sys
from typing import Dict, Any, List, Optional

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_analyzer import LangChainAnalyzer


class SemanticFilter:
    """基于 LangChain 的可配置双模（声文/多模态）精修与断句器"""

    def __init__(self, llm_client: Optional[Any] = None):
        self.analyzer = LangChainAnalyzer()

    @property
    def engine_mode(self) -> str:
        return self.analyzer.engine_mode

    @property
    def active_model(self) -> str:
        return self.analyzer.active_model

    def refine_candidate(
        self,
        candidate_info: Dict[str, Any],
        transcript_segments: List[Dict[str, Any]],
        anchor_profile: Optional[Dict[str, Any]] = None,
        video_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        精修单个候选切片（支持注入主播专属档案、切片词库与多模态视频路径）
        """
        return self.analyzer.analyze(
            candidate_info,
            transcript_segments,
            anchor_profile=anchor_profile,
            video_path=video_path
        )

    def stream_refine_candidate(
        self,
        candidate_info: Dict[str, Any],
        transcript_segments: List[Dict[str, Any]],
        anchor_profile: Optional[Dict[str, Any]] = None,
        video_path: Optional[str] = None
    ):
        """流式生成器接口，供 SSE 实时推送"""
        return self.analyzer.stream_analyze(
            candidate_info,
            transcript_segments,
            anchor_profile=anchor_profile,
            video_path=video_path
        )
