# -*- coding: utf-8 -*-
"""
基于 LangChain (LCEL) 的双模智能高能分析引擎 (Dual-Engine High-Energy Analyzer)
支持可配置化自由切换：
1. 经典声文极速模式 (engine_mode = "text" | 默认模型: qwen3.8-flash)
2. 多模态音画全感知模式 (engine_mode = "multimodal" | 默认模型: qwen3.8-omni-flash)
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# 确保控制台 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from vision_sampler import VisionFrameSampler


class HighEnergyAnalysisSchema(BaseModel):
    """高能切片语义分析与多模态视觉感知结构化模型"""
    is_valid_highlight: bool = Field(default=True, description="是否为真正有看点的高能片段（若画面仅在大厅发呆/黑屏挂机无实质内容则为false）")
    highlight_theme: str = Field(description="核心看点主题，如：极限贴弯超车 / 撞墙破防 / 价格反转 / 毒舌金句")
    core_quote: str = Field(description="主播在该片段中最经典、最抓人的一句核心台词或画面名梗")
    visual_action_summary: str = Field(default="", description="多模态画面视觉动作与主播表情特征描述（如：赛车极限贴墙氮气延续反超，右下角主播激动挥拳）")
    layout_recommendation: str = Field(default="split_screen_game", description="竖屏构图运镜推荐：split_screen_game(上游戏下主播双拼) | center_blur(居中竖屏) | closeup_zoom(特写推镜)")
    recommended_cut_start: float = Field(description="推荐精确剪入时间点(秒，浮点数，对齐视觉动作起点或引子句首)")
    recommended_cut_end: float = Field(description="推荐精确剪出时间点(秒，浮点数，对齐视觉结果或包袱句尾)")
    generated_titles: List[str] = Field(description="3个极具好奇心、悬念感或情绪张力的抖音爆款短视频标题")
    trigger_reason: str = Field(description="详述为什么触发了高能录制，融合声量爆发秒数、画面动作与台词反转做出精准归因")
    reason: str = Field(description="专业剪辑断句与音画对齐理由简述")


class LangChainAnalyzer:
    """支持【经典声文 (qwen3.8-flash)】与【多模态音画 (qwen3.8-omni-flash)】可配置切换的分析器"""

    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            config_path = os.path.join(base_dir, "config", "llm_config.json")

        self.config_path = config_path
        self.config = self._load_config()

        # 读取引擎模式与模型配置
        self.engine_mode = self.config.get("engine_mode", "multimodal")
        self.text_model = self.config.get("text_model", "qwen3.8-flash")
        self.multimodal_model = self.config.get("multimodal_model", "qwen3.8-omni-flash")
        self.frame_sample_count = int(self.config.get("frame_sample_count", 6))

        # 根据当前模式自动决定主模型代号
        configured_model = self.config.get("model", "")
        if self.engine_mode == "multimodal":
            self.active_model = configured_model if "omni" in configured_model or "vl" in configured_model else self.multimodal_model
        else:
            self.active_model = configured_model if configured_model and "omni" not in configured_model else self.text_model

        # 1. 初始化主模型客户端
        self.llm = ChatOpenAI(
            model=self.active_model,
            api_key=self.config.get("api_key", ""),
            base_url=self.config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=self.config.get("temperature", 0.3),
            timeout=self.config.get("timeout_seconds", 35),
            max_retries=2
        )

        # 初始化备用纯文本模型客户端（用于多模态降级保护）
        self.fallback_text_llm = ChatOpenAI(
            model=self.text_model,
            api_key=self.config.get("api_key", ""),
            base_url=self.config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            temperature=self.config.get("temperature", 0.3),
            timeout=self.config.get("timeout_seconds", 30),
            max_retries=1
        )

        # 2. 构造 Pydantic 输出解析器
        self.parser = JsonOutputParser(pydantic_object=HighEnergyAnalysisSchema)

        # 3. 构造 System Prompt 与 Human Prompt 模板
        self.system_template = """你是一名抖音顶级短视频爆款切片师、视觉导播兼文案专家。
你的任务是根据直播片段的语音转录台词（带时间戳）、声量爆发点以及（若处于多模态模式下提供的）连续画面关键帧，对该片段进行专业级的切片精修定位与文案包装。

【切片核心原则】：
1. 音画双轴防腰斩：切入点必须覆盖视觉动作起点（如赛车入弯、交战开始）或完整引子句首；切出点必须等到视觉结果落地（如冲线、撞墙后表情反应结束）或包袱句尾。
2. 短视频黄金叙事时长：切片时长建议保持在 15 秒到 35 秒之间，确保前因铺垫、高潮爆发与收口完整。
3. 视觉感知与运镜建议：描述画面关键动作与主播表情（visual_action_summary），并给出竖屏排版建议（layout_recommendation）。
4. 爆款网感标题：生成 3 个极具好奇心、悬念感或画面细节引导的短视频标题。
5. 精准归因披露：在 trigger_reason 中明确指出触发高能的声学、台词与画面动作依据。

【排版格式硬性要求】：
输出必须是标准的、带换行和 2 空格缩进的格式化 JSON（Pretty-printed JSON）。严禁使用 Markdown 代码块包裹以外的多余解释文字。

{format_instructions}"""

        self.human_template = """【当前认知引擎模式】：{engine_mode_label}
【直播候选区间信息】：
- 粗筛区间范围: {start_time}秒 ~ {end_time}秒
- 核心声量爆发秒数: 第 {peak_time} 秒
- 粗筛触发特征: {raw_reason}

【当前主播专属人设与专属切片词库】：
- 主播昵称: {anchor_name}
- 专属切片关键词: {exclusive_keywords}
- 主播人设与看点定位指导: {persona_prompt}

【该区间完整的带时间戳语音转录台词】：
{dialogue_text}

【专属定制剪辑任务要求】：
1. 重点审查台词与画面中是否命中上述主播专属切片关键词、极限操作或破防名场面。
2. 剪辑起止点必须完整覆盖动作/情绪爆发前因、高潮过程与收口，建议保持 15~35 秒黄金叙事区间。
3. 3 个短视频爆款标题必须贴合该主播人设风格，带有强烈的悬念感、画面细节引导或冲突感。
4. 在 trigger_reason 中明确披露触发归因（含画面动作、专属词命中或声学爆发特征）。"""

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_template),
            ("human", self.human_template)
        ])

        self.chain = self.prompt | self.llm | self.parser
        print(f"[LangChain] 认知引擎已就绪 | 模式: {self.engine_mode} | 主模型: {self.active_model}")

    def _load_config(self) -> Dict[str, Any]:
        """加载大模型配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[LangChain警告] 读取大模型配置失败: {e}")
        return {}

    def _build_multimodal_messages(
        self,
        chain_input: Dict[str, Any],
        sampled_frames: List[Dict[str, Any]]
    ) -> List[Any]:
        """构造包含关键帧序列的多模态消息列表"""
        sys_text = self.system_template.format(format_instructions=chain_input["format_instructions"])
        human_text = self.human_template.format(**chain_input)

        frame_timestamps = ", ".join([f"{f['timestamp']}s" for f in sampled_frames])
        vision_intro = (
            f"\n\n【多模态视觉关键帧序列 ({len(sampled_frames)}张，对应秒数: {frame_timestamps})】：\n"
            "请结合以下按时间顺序排列的直播画面截图，观察游戏操作状态、赛况UI、主播面部表情变化与肢体动作，"
            "校准最佳切入/切出秒数并填写 visual_action_summary 与 layout_recommendation："
        )

        content_blocks: List[Dict[str, Any]] = [
            {"type": "text", "text": human_text + vision_intro}
        ]
        for frame in sampled_frames:
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": frame["data_url"]}
            })

        return [
            SystemMessage(content=sys_text),
            HumanMessage(content=content_blocks)
        ]

    def analyze(
        self,
        candidate_info: Dict[str, Any],
        transcript_segments: List[Dict[str, Any]],
        anchor_profile: Optional[Dict[str, Any]] = None,
        video_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行语义分析与高能归因（自动根据 engine_mode 路由纯文本或多模态音画引擎）
        """
        anchor_name = anchor_profile.get("anchor_name", "通用主播") if anchor_profile else "通用主播"
        kw_list = anchor_profile.get("exclusive_keywords", []) if anchor_profile else []
        exclusive_keywords = ", ".join(kw_list) if kw_list else "高光操作, 爆笑破防, 核心金句"
        persona_prompt = anchor_profile.get("persona_prompt", "关注主播的高能瞬间与精彩表达。") if anchor_profile else "关注主播的高能瞬间与精彩表达。"

        start_t = float(candidate_info.get("start_time", 0.0))
        end_t = float(candidate_info.get("end_time", 10.0))

        # 多模态模式下，即使没有语音台词（例如静音操作或沉默破防），只要有视频画面也能分析！
        sampled_frames: List[Dict[str, Any]] = []
        if self.engine_mode == "multimodal" and video_path and os.path.exists(video_path):
            sampled_frames = VisionFrameSampler.sample_frames_base64(
                video_path=video_path,
                start_time=start_t,
                end_time=end_t,
                num_frames=self.frame_sample_count
            )

        if not transcript_segments and not sampled_frames:
            return {
                "is_valid_highlight": True,
                "highlight_theme": candidate_info.get("trigger_type", f"{anchor_name}高能时刻"),
                "core_quote": f"{anchor_name}高能爆发时刻",
                "visual_action_summary": "基于声学波峰自动锁定画面区间",
                "layout_recommendation": anchor_profile.get("layout_template", "split_screen_game") if anchor_profile else "center_blur",
                "recommended_cut_start": round(start_t, 2),
                "recommended_cut_end": round(end_t, 2),
                "duration": round(end_t - start_t, 2),
                "generated_titles": [
                    f"【{anchor_name}名场面】主播情绪瞬间拉满的一刻！",
                    f"{anchor_name}全网热议高能现场，建议戴耳机看！",
                    f"这也太真实了！{anchor_name}直接破防！"
                ],
                "trigger_reason": candidate_info.get("reason", "声学能量爆发突破阈值"),
                "reason": "基于声学能量波峰自动对齐剪辑区间。",
                "engine_mode": self.engine_mode,
                "model_used": self.active_model
            }

        dialogue_lines = [
            f"[{s['start']}s -> {s['end']}s] {s['text']}"
            for s in transcript_segments
        ] if transcript_segments else ["(当前片段主播沉默或专注操作，请重点依据多模态画面关键帧分析视觉看点)"]
        dialogue_text = "\n".join(dialogue_lines)

        mode_label = (
            f"多模态音画全感知模式 ({self.active_model}, 已注入 {len(sampled_frames)} 帧画面)"
            if (self.engine_mode == "multimodal" and sampled_frames)
            else f"经典声文极速模式 ({self.text_model})"
        )

        chain_input = {
            "engine_mode_label": mode_label,
            "start_time": start_t,
            "end_time": end_t,
            "peak_time": candidate_info.get("peak_time", start_t),
            "raw_reason": candidate_info.get("reason", "声量激增"),
            "anchor_name": anchor_name,
            "exclusive_keywords": exclusive_keywords,
            "persona_prompt": persona_prompt,
            "dialogue_text": dialogue_text,
            "format_instructions": self.parser.get_format_instructions()
        }

        try:
            if self.engine_mode == "multimodal" and sampled_frames:
                mm_messages = self._build_multimodal_messages(chain_input, sampled_frames)
                raw_resp = self.llm.invoke(mm_messages)
                result = self.parser.parse(raw_resp.content)
            else:
                result = self.chain.invoke(chain_input)

            cut_start = float(result.get("recommended_cut_start", start_t))
            cut_end = float(result.get("recommended_cut_end", end_t))

            if cut_start >= cut_end or cut_end - cut_start < 2.0:
                if transcript_segments:
                    cut_start = transcript_segments[0]["start"]
                    cut_end = transcript_segments[-1]["end"]
                else:
                    cut_start, cut_end = start_t, end_t

            result["recommended_cut_start"] = round(cut_start, 2)
            result["recommended_cut_end"] = round(cut_end, 2)
            result["duration"] = round(cut_end - cut_start, 2)
            result["engine_mode"] = self.engine_mode
            result["model_used"] = self.active_model
            result["frames_analyzed"] = len(sampled_frames)

            if not result.get("trigger_reason"):
                result["trigger_reason"] = candidate_info.get("reason", "主播声量与画面动作爆发")

            return result

        except Exception as e:
            print(f"[LangChain异常] 模式({self.engine_mode}/{self.active_model})执行异常: {e}，自动切换降级保护")
            # 若多模态调用报错，自动尝试用纯文本模型兜底
            if self.engine_mode == "multimodal":
                try:
                    fallback_chain = self.prompt | self.fallback_text_llm | self.parser
                    res = fallback_chain.invoke(chain_input)
                    c_start = float(res.get("recommended_cut_start", start_t))
                    c_end = float(res.get("recommended_cut_end", end_t))
                    res["recommended_cut_start"] = round(c_start, 2)
                    res["recommended_cut_end"] = round(c_end, 2)
                    res["duration"] = round(c_end - c_start, 2)
                    res["engine_mode"] = "text_fallback"
                    res["model_used"] = self.text_model
                    return res
                except Exception:
                    pass

            start_s = transcript_segments[0]["start"] if transcript_segments else start_t
            end_s = transcript_segments[-1]["end"] if transcript_segments else end_t
            return {
                "is_valid_highlight": True,
                "highlight_theme": "精彩直播名场面",
                "core_quote": transcript_segments[0]["text"] if transcript_segments else f"{anchor_name}高能时刻",
                "visual_action_summary": "声画同步高潮区间",
                "layout_recommendation": "split_screen_game",
                "recommended_cut_start": round(start_s, 2),
                "recommended_cut_end": round(end_s, 2),
                "duration": round(end_s - start_s, 2),
                "generated_titles": [
                    f"【{anchor_name}名场面】这段操作与反应太真实了！",
                    "神级反转！这一段建议反复观看！",
                    "这波操作直接封神！全场观众沸腾！"
                ],
                "trigger_reason": candidate_info.get("reason", "声能与台词密集爆发"),
                "reason": "容错保护机制按自然起止对齐。",
                "engine_mode": self.engine_mode,
                "model_used": self.active_model
            }

    def stream_analyze(
        self,
        candidate_info: Dict[str, Any],
        transcript_segments: List[Dict[str, Any]],
        anchor_profile: Optional[Dict[str, Any]] = None,
        video_path: Optional[str] = None
    ):
        """
        支持双模式的流式生成器（SSE 实时推送）
        """
        anchor_name = anchor_profile.get("anchor_name", "通用主播") if anchor_profile else "通用主播"
        kw_list = anchor_profile.get("exclusive_keywords", []) if anchor_profile else []
        exclusive_keywords = ", ".join(kw_list) if kw_list else "高光操作, 爆笑破防, 核心金句"
        persona_prompt = anchor_profile.get("persona_prompt", "关注主播的高能瞬间与精彩表达。") if anchor_profile else "关注主播的高能瞬间与精彩表达。"

        start_t = float(candidate_info.get("start_time", 0.0))
        end_t = float(candidate_info.get("end_time", 10.0))

        sampled_frames: List[Dict[str, Any]] = []
        if self.engine_mode == "multimodal" and video_path and os.path.exists(video_path):
            sampled_frames = VisionFrameSampler.sample_frames_base64(
                video_path=video_path,
                start_time=start_t,
                end_time=end_t,
                num_frames=self.frame_sample_count
            )

        dialogue_lines = [
            f"[{s['start']}s -> {s['end']}s] {s['text']}"
            for s in transcript_segments
        ] if transcript_segments else ["(未检测到连续语音，依赖多模态视觉帧与声学波峰)"]
        dialogue_text = "\n".join(dialogue_lines)

        mode_label = (
            f"多模态音画全感知模式 ({self.active_model}, 已采样 {len(sampled_frames)} 帧关键画面)"
            if (self.engine_mode == "multimodal" and sampled_frames)
            else f"经典声文极速模式 ({self.text_model})"
        )

        chain_input = {
            "engine_mode_label": mode_label,
            "start_time": start_t,
            "end_time": end_t,
            "peak_time": candidate_info.get("peak_time", start_t),
            "raw_reason": candidate_info.get("reason", "声量突增"),
            "anchor_name": anchor_name,
            "exclusive_keywords": exclusive_keywords,
            "persona_prompt": persona_prompt,
            "dialogue_text": dialogue_text,
            "format_instructions": self.parser.get_format_instructions()
        }

        formatted = self.prompt.format_prompt(**chain_input)
        text_messages = formatted.to_messages()

        # 1. 产出 HumanMessage 预览文本（供前端面板展示上下文）
        human_preview = text_messages[1].content if len(text_messages) > 1 else ""
        if sampled_frames:
            ts_list = ", ".join([f"{f['timestamp']}s" for f in sampled_frames])
            human_preview += f"\n\n[👁️ 多模态视觉通道] 已注入 {len(sampled_frames)} 张视频关键帧 ({ts_list}) 至 {self.active_model}"
        yield {"event": "human_message", "content": human_preview}

        # 2. 实时 Token 流式输出
        full_text = ""
        try:
            active_messages = (
                self._build_multimodal_messages(chain_input, sampled_frames)
                if (self.engine_mode == "multimodal" and sampled_frames)
                else text_messages
            )

            for chunk in self.llm.stream(active_messages):
                token = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                full_text += token
                yield {"event": "token", "content": token}

            result = self.parser.parse(full_text)
            cut_start = float(result.get("recommended_cut_start", start_t))
            cut_end = float(result.get("recommended_cut_end", end_t))
            if cut_start >= cut_end or cut_end - cut_start < 2.0:
                if transcript_segments:
                    cut_start = transcript_segments[0]["start"]
                    cut_end = transcript_segments[-1]["end"]
                else:
                    cut_start, cut_end = start_t, end_t

            result["recommended_cut_start"] = round(cut_start, 2)
            result["recommended_cut_end"] = round(cut_end, 2)
            result["duration"] = round(cut_end - cut_start, 2)
            result["engine_mode"] = self.engine_mode
            result["model_used"] = self.active_model
            result["frames_analyzed"] = len(sampled_frames)
            if not result.get("trigger_reason"):
                result["trigger_reason"] = candidate_info.get("reason", "声画高能爆发")

            yield {"event": "result", "data": result}

        except Exception as e:
            print(f"[LangChain流式解析降级保护] {e}")
            fallback_res = self.analyze(candidate_info, transcript_segments, anchor_profile=anchor_profile, video_path=video_path)
            yield {"event": "result", "data": fallback_res}
