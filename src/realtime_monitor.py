# -*- coding: utf-8 -*-
"""
实时高能监听与自动录制引擎 (Real-time High-Energy Monitor)
功能：
1. 用户主动开启对指定直播间的长效监听；
2. 保持低开销持续拉流并维护滚动环形缓存（保留最近 60 秒内容，前因不丢失）；
3. 毫秒级分析实时音频能量，一旦突发高能，自动判定触发归因并截取出完整高能切片；
4. 自动送入 Whisper + Qwen 提炼金句与爆款标题，直推前端看板与剪映！
"""

import os
import sys
import time
import math
import subprocess
import threading
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from resolver import DouyinLiveResolver
from video_composer import VideoComposer
from jianying_exporter import JianYingDraftExporter
from asr_transcriber import ASRTranscriber
from semantic_filter import SemanticFilter
from anchor_profile import AnchorProfileManager


class RealtimeHighEnergyMonitor:
    """实时高能监控与自动捕获器"""

    def __init__(self, output_dir: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.output_dir = output_dir or os.path.join(base_dir, "recordings")
        self.highlights_dir = os.path.join(base_dir, "output")
        self.cache_dir = os.path.join(base_dir, "temp_rolling_cache")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.highlights_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.resolver = DouyinLiveResolver()
        self.composer = VideoComposer(output_dir=self.highlights_dir)
        self.jianying_exporter = JianYingDraftExporter()
        self.transcriber = ASRTranscriber(model_size="tiny")
        self.semantic_filter = SemanticFilter()
        self.profile_mgr = AnchorProfileManager()

        self.is_monitoring = False
        self.current_target = ""
        self.current_anchor = "-"
        self.start_timestamp = 0
        self.captured_highlights: List[Dict[str, Any]] = []

        self._monitor_thread: Optional[threading.Thread] = None
        self._active_ffmpeg: Optional[subprocess.Popen] = None
        self._current_ffmpeg: Optional[subprocess.Popen] = None
        self._current_seg_path: Optional[str] = None
        self._session_id = 0
        self._lock = threading.Lock()

        # 实时指标
        self.current_db = -60.0
        self.avg_db = -30.0

        # 系统运行与切片配置
        self.config_path = os.path.join(base_dir, "config", "system_config.json")
        self.history_path = os.path.join(base_dir, "config", "highlights_history.json")
        self.seg_duration = 25  # 录制采样分片时长(秒)
        self.target_slice_min = 15
        self.target_slice_max = 35
        self.intensity_threshold = 1.3
        self.min_energy = 180
        self.auto_short_enabled = True
        self.auto_draft_enabled = True
        self.load_system_config()
        self.load_history()

    def load_history(self):
        """加载历史捕获的高能切片记录"""
        if os.path.exists(self.history_path):
            try:
                import json
                with open(self.history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.captured_highlights = data
            except Exception as e:
                print(f"[警告] 读取历史切片记录失败: {e}")

    def save_history(self):
        """持久化高能切片记录到磁盘"""
        try:
            import json
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.captured_highlights[-50:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[警告] 保存历史切片记录失败: {e}")

    def load_system_config(self):
        """读取系统运行配置"""
        if os.path.exists(self.config_path):
            try:
                import json
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.seg_duration = int(cfg.get("segment_duration", 25))
                    self.target_slice_min = int(cfg.get("target_slice_min", 15))
                    self.target_slice_max = int(cfg.get("target_slice_max", 35))
                    self.intensity_threshold = float(cfg.get("intensity_threshold", 1.3))
                    self.min_energy = float(cfg.get("min_energy", 180))
                    self.auto_short_enabled = bool(cfg.get("auto_short_enabled", True))
                    self.auto_draft_enabled = bool(cfg.get("auto_draft_enabled", True))
            except Exception as e:
                print(f"[警告] 读取系统配置文件失败: {e}")

    def update_config(self, cfg: Dict[str, Any]):
        """热更新运行配置"""
        with self._lock:
            self.seg_duration = int(cfg.get("segment_duration", self.seg_duration))
            self.target_slice_min = int(cfg.get("target_slice_min", self.target_slice_min))
            self.target_slice_max = int(cfg.get("target_slice_max", self.target_slice_max))
            self.intensity_threshold = float(cfg.get("intensity_threshold", self.intensity_threshold))
            self.min_energy = float(cfg.get("min_energy", self.min_energy))
            self.auto_short_enabled = bool(cfg.get("auto_short_enabled", self.auto_short_enabled))
            self.auto_draft_enabled = bool(cfg.get("auto_draft_enabled", self.auto_draft_enabled))

    def start_monitoring(self, target: str) -> Dict[str, Any]:
        """开启或平滑切换实时监控（会话代际隔离，彻底消除旧线程与旧直播间串流）"""
        target_str = str(target).strip()
        with self._lock:
            # 若正在监听同一个目标，直接返回已在运行
            if self.is_monitoring and target_str == str(self.current_target).strip():
                return {
                    "status": "already_running",
                    "target": self.current_target,
                    "anchor_name": self.current_anchor
                }

            # 1. 递增会话代际 Token，向旧线程发送不可逆熔断信号
            self._session_id += 1
            current_session = self._session_id
            self.is_monitoring = False

            if self._active_ffmpeg and self._active_ffmpeg.poll() is None:
                try:
                    self._active_ffmpeg.kill()
                except Exception:
                    pass

        # 2. 在锁外安全解析新直播间（防止网络阻塞锁）
        print(f"[直播间切换] 会话代际 #{current_session} 启动，正在解析新房间: {target_str}")
        meta = self.resolver.resolve(target_str)
        if not meta or not meta.get("best_flv"):
            raise ValueError(f"无法获取直播间 {target_str} 的有效推流，主播可能未开播或房间号有误")

        with self._lock:
            # 若在解析期间用户又发起了新的切换请求，则放弃当前过期代际
            if current_session != self._session_id:
                print(f"[直播间切换] 代际 #{current_session} 已过期，取消该线程启动")
                return {"status": "cancelled"}

            self.is_monitoring = True
            self.current_target = target_str
            self.current_anchor = meta["anchor_name"]
            self.start_timestamp = time.time()
            # 清空上一位主播的高能看板切片，保证切片池与当前监听主播 100% 对应
            self.captured_highlights = []

            # 3. 异步启动带有专属 Session 代际标记的长效监控线程
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(meta["best_flv"], meta, current_session),
                daemon=True
            )
            self._monitor_thread.start()

            return {
                "status": "started",
                "is_switch": True,
                "target": self.current_target,
                "anchor_name": self.current_anchor,
                "title": meta["title"],
                "room_id": meta["room_id"]
            }

    def _kill_proc(self, proc: Optional[subprocess.Popen]):
        """强力终止子进程树 (Windows 平台深度彻底杀灭)"""
        if proc and proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    proc.kill()
            except Exception:
                pass

    def stop_monitoring(self) -> Dict[str, Any]:
        """停止实时监控（强力熔断：彻底终止拉流与切片子进程并清除未完成录像）"""
        with self._lock:
            self._session_id += 1  # 递增代际，向正在执行的 ASR / LLM / 合成发出熔断
            self.is_monitoring = False
            self._kill_proc(self._active_ffmpeg)
            self._kill_proc(self._current_ffmpeg)
            self._active_ffmpeg = None
            self._current_ffmpeg = None
            
            # 立即清理当前录到一半的残缺分片，绝不让其存盘进入资产库
            if self._current_seg_path and os.path.exists(self._current_seg_path):
                try:
                    os.remove(self._current_seg_path)
                    print(f"[清理残留] 已成功移除停止时未完成的瞬时录像分片: {self._current_seg_path}")
                except Exception:
                    pass
                self._current_seg_path = None

            print("[实时监控停止] 已向后台下发全量熔断信号，彻底终止拉流与切片任务")
            return {"status": "stopped", "captured_count": len(self.captured_highlights)}

    def start_monitor(self, target: str) -> Dict[str, Any]:
        """兼容别名方法"""
        return self.start_monitoring(target)

    def start(self, target: str) -> Dict[str, Any]:
        """兼容别名方法"""
        return self.start_monitoring(target)

    def stop(self) -> Dict[str, Any]:
        """兼容别名方法"""
        return self.stop_monitoring()

    def get_status(self) -> Dict[str, Any]:
        """获取监控器当前运行状态"""
        elapsed_sec = int(time.time() - self.start_timestamp) if self.is_monitoring else 0
        return {
            "is_monitoring": self.is_monitoring,
            "target": self.current_target,
            "anchor_name": self.current_anchor,
            "elapsed_seconds": elapsed_sec,
            "current_db": round(self.current_db, 1),
            "captured_count": len(self.captured_highlights),
            "recent_highlights": self.captured_highlights[-5:] # 最新5条
        }

    def _monitor_loop(self, stream_url: str, meta: Dict[str, Any], session_id: int):
        """后台拉流分段与高能特征检测主循环 (严格绑定 session_id 代际熔断机制)"""
        anchor_name = meta.get('anchor_name', '直播')
        target_rid = meta.get("web_rid") or self.current_target
        print(f"\n[实时高能监听] 启动长效流式挂机 (会话 #{session_id}): 主播【{anchor_name}】({target_rid}) ...")

        part_idx = 1
        silent_count = 0  # 连续未触发计数器

        while self.is_monitoring and self._session_id == session_id:
            time_hms = datetime.now().strftime("%H-%M-%S")
            anchor_clean = anchor_name.replace('/', '_').replace('\\', '_').replace(' ', '')
            seg_filename = f"{time_hms}_{anchor_clean}_p{part_idx:03d}.mp4"
            seg_path = os.path.join(self.output_dir, seg_filename)
            self._current_seg_path = seg_path

            # 采用配置的动态微切片时长 (默认 25 秒，支持 15~60 秒灵活配置)
            dur_str = str(self.seg_duration)
            cmd = [
                "ffmpeg",
                "-y",
                "-headers", f"User-Agent: {self.resolver.headers['User-Agent']}\r\nReferer: https://live.douyin.com/\r\n",
                "-i", stream_url,
                "-t", dur_str,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                seg_path
            ]

            try:
                # 动态计算超时时间: seg_duration + 8秒
                timeout_sec = self.seg_duration + 8
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self._active_ffmpeg = proc
                self._current_ffmpeg = proc

                try:
                    _, _ = proc.communicate(timeout=timeout_sec)
                except subprocess.TimeoutExpired:
                    if proc:
                        proc.kill()
                        proc.communicate()

                # 阶段性熔断检查：如果在录制期间代际已变，立即清理坏文件并退出
                if not self.is_monitoring or self._session_id != session_id:
                    print(f"[会话 #{session_id} 熔断] 检测到直播间已切换，舍弃当前分片并自毁旧线程")
                    if os.path.exists(seg_path):
                        try:
                            os.remove(seg_path)
                        except Exception:
                            pass
                    break

                # 校验文件是否真实写入且大于 100KB（避免坏损头文件）
                if os.path.exists(seg_path) and os.path.getsize(seg_path) > 102400:
                    captured = self._detect_and_process_highlight(seg_path, meta, part_idx, silent_count, session_id)
                    if captured:
                        silent_count = 0
                    else:
                        silent_count += 1
                    part_idx += 1
                else:
                    # 分片拉取异常或未写出，清理坏文件并刷新推流
                    if os.path.exists(seg_path):
                        try:
                            os.remove(seg_path)
                        except Exception:
                            pass
                    if not self.is_monitoring or self._session_id != session_id:
                        break
                    print(f"[实时监控 #{session_id}] 主播【{anchor_name}】推流波动，正在自动重连解析...")
                    new_meta = self.resolver.resolve(target_rid)
                    if new_meta and new_meta.get("best_flv"):
                        stream_url = new_meta["best_flv"]
                    time.sleep(2)

            except Exception as e:
                if not self.is_monitoring or self._session_id != session_id:
                    break
                print(f"[实时监控异常 #{session_id}] {e}")
                time.sleep(2)

        print(f"[会话 #{session_id} 结束] 主播【{anchor_name}】监控线程已彻底安全退出")

    def _detect_and_process_highlight(self, seg_path: str, meta: Dict[str, Any], part_idx: int, silent_count: int, session_id: int) -> bool:
        """分析微切片并根据多维声学、台词语义与主播专属关键词自适应触发切片生成 (带代际熔断)"""
        if not self.is_monitoring or self._session_id != session_id:
            return False

        # 1. 匹配当前主播专属档案与切片词库
        anchor_profile = self.profile_mgr.match_profile(
            target=meta.get("web_rid", self.current_target),
            anchor_name=meta.get("anchor_name", "")
        )
        exclusive_kws = anchor_profile.get("exclusive_keywords", []) if anchor_profile else []

        from audio_analyzer import AudioEnergyAnalyzer
        from danmu_monitor import danmu_service
        analyzer = AudioEnergyAnalyzer()
        audio_res = analyzer.analyze_peaks(seg_path, threshold_multiplier=1.1, min_duration_sec=0.3)
        danmu_heat = danmu_service.get_window_heat_metrics(window_sec=self.seg_duration)

        avg_energy = audio_res.get("avg_energy", 0)
        peaks = audio_res.get("peaks", [])
        total_d = audio_res.get("total_duration", 12.0)

        # 触发归因判定逻辑 (Trigger Reason Engine - 融合声学、弹幕密度与高价值礼物)
        trigger_reason = ""
        trigger_tag = ""
        top_peak = max(peaks, key=lambda p: p.get("peak_intensity", 1.0)) if peaks else None
        intensity = top_peak.get("peak_intensity", 1.0) if top_peak else 1.0

        has_acoustic_trigger = False
        if danmu_heat.get("is_active") and danmu_heat.get("window_diamonds", 0) >= 99:
            trigger_tag = "高光打赏"
            trigger_reason = f"直播间收到高价值礼物（{danmu_heat['top_gift_desc']}，窗口热度 {danmu_heat['window_diamonds']} 钻）"
            has_acoustic_trigger = True
        elif danmu_heat.get("is_active") and danmu_heat.get("danmu_count", 0) >= 12:
            kw_hint = f"，热词「{'/'.join(danmu_heat['hot_keywords'])}」刷屏" if danmu_heat.get("hot_keywords") else ""
            trigger_tag = "弹幕沸腾"
            trigger_reason = f"弹幕互动激增（近 {self.seg_duration}s 涌入 {danmu_heat['danmu_count']} 条弹幕{kw_hint}）"
            has_acoustic_trigger = True
        elif top_peak and intensity >= self.intensity_threshold:
            trigger_tag = "声量爆发"
            trigger_reason = f"主播声量激增 {intensity:.1f}x (爆发点第 {top_peak['start_time']}s)，情绪激昂掀起氛围看点"
            has_acoustic_trigger = True
        elif top_peak and top_peak.get("duration", 0) >= 1.5:
            trigger_tag = "精彩连珠"
            trigger_reason = f"连续 {top_peak['duration']} 秒密集语言输出，重点讲解核心看点"
            has_acoustic_trigger = True
        elif avg_energy >= self.min_energy:
            trigger_tag = "连麦互动"
            trigger_reason = f"整体环境声场能量达 {avg_energy:.0f}，现场互动连贯饱满"
            has_acoustic_trigger = True
        elif silent_count >= 2:
            trigger_tag = "实时看点"
            trigger_reason = f"实时直播流高质画面捕捉 (平均能量: {avg_energy:.0f})，提炼当下核心内容"
            has_acoustic_trigger = True

        # 代际检查
        if not self.is_monitoring or self._session_id != session_id:
            return False

        try:
            # 2. 语音转文字识别
            subtitles = self.transcriber.transcribe(seg_path)

            # 3. 扫描字幕中是否命中主播专属切片关键词 (Keyword Boosting)
            all_text = "".join([s.get("text", "") for s in subtitles])
            matched_kws = [kw for kw in exclusive_kws if kw in all_text]
            if matched_kws:
                kw_str = "、".join(matched_kws[:3])
                trigger_tag = "专属名梗"
                trigger_reason = f"台词高频命中主播【{meta['anchor_name']}】专属切片词库「{kw_str}」！"
                print(f"🔥 [专属关键词命中] 主播【{meta['anchor_name']}】台词中检测到专属词库: {kw_str}")
            elif not has_acoustic_trigger:
                # 既无声学波峰又未命中专属关键词，跳过
                return False

            print(f"\n⚡ [高能自动捕获 #{part_idx} | 主播: {meta['anchor_name']}] 触发标签: 【{trigger_tag}】 | 归因: {trigger_reason}")

            # 再次代际检查（防止 ASR 耗时几秒内发生房间切换）
            if not self.is_monitoring or self._session_id != session_id:
                print(f"[高能捕获中止] 会话 #{session_id} 已过期，中止后续短视频与草稿生成")
                return False

            # 4. 构造精修上下文并提交 LangChain 大脑（深度挂载主播专属人设与关键词）
            peak_start = top_peak["start_time"] if top_peak else 2.0
            peak_end = top_peak["end_time"] if top_peak else min(total_d, 12.0)
            cand_info = {
                "start_time": max(0.0, peak_start - 6.0),
                "end_time": min(total_d, peak_end + 12.0),
                "peak_time": peak_start,
                "reason": trigger_reason
            }
            refined = self.semantic_filter.refine_candidate(
                cand_info,
                subtitles,
                anchor_profile=anchor_profile,
                video_path=seg_path
            )

            if not self.is_monitoring or self._session_id != session_id:
                return False

            # 若多模态视觉判定该段为大厅挂机/无实质看点假高能，自动过滤丢弃
            if refined.get("is_valid_highlight") is False:
                print(f"[多模态废片过滤] 片段 {os.path.basename(seg_path)} 经视觉校验无实质高能看点，已自动过滤。")
                return False

            start_t = refined.get("recommended_cut_start", cand_info["start_time"])
            end_t = refined.get("recommended_cut_end", cand_info["end_time"])
            best_title = refined.get("generated_titles", [f"主播精彩瞬间_{part_idx}"])[0]

            # 再次检查停止状态
            if not self.is_monitoring or self._session_id != session_id:
                print(f"[高能捕获中止] 监听已停止，取消后续短视频合成与草稿入库")
                return False

            # 3. 自动生成 9:16 成品短视频
            out_filename = ""
            if self.auto_short_enabled:
                if not self.is_monitoring or self._session_id != session_id:
                    return False
                out_filename = f"auto_{datetime.now().strftime('%H%M%S')}_{trigger_tag}.mp4"
                srt_content = ASRTranscriber.generate_srt(subtitles)
                self.composer.compose_short(
                    input_video=seg_path,
                    start_sec=start_t,
                    end_sec=end_t,
                    title=best_title,
                    srt_content=srt_content,
                    output_filename=out_filename
                )

            # 4. 自动写入剪映工程草稿
            draft_dir = ""
            if self.auto_draft_enabled and self.is_monitoring and self._session_id == session_id:
                draft_dir = self.jianying_exporter.export_draft(
                    draft_title=f"{trigger_tag}_{best_title[:15]}",
                    video_path=seg_path,
                    start_sec=start_t,
                    end_sec=end_t,
                    subtitles=subtitles
                )

            # 5. 登记高能记录
            if not self.is_monitoring or self._session_id != session_id:
                print(f"[高能捕获中止] 监听已停止，舍弃该条切片")
                return False

            seg_filename = os.path.basename(seg_path)
            final_trigger_reason = refined.get("trigger_reason") or trigger_reason
            highlight_record = {
                "id": f"hl_{int(time.time())}_{part_idx}",
                "trigger_tag": trigger_tag,
                "trigger_reason": final_trigger_reason,
                "intensity": intensity,
                "anchor_name": meta["anchor_name"],
                "title": best_title,
                "core_quote": refined.get("core_quote", "-"),
                "start_time": round(start_t, 1),
                "end_time": round(end_t, 1),
                "duration": round(end_t - start_t, 1),
                "source_video": seg_filename,
                "source_filename": seg_filename,
                "source_path": seg_path,
                "source_url": f"/static/recordings/{seg_filename}",
                "video_path": seg_path,
                "mp4_url": f"/static/output/{out_filename}",
                "draft_dir": draft_dir,
                "created_at": datetime.now().strftime("%H:%M:%S")
            }

            with self._lock:
                if self._session_id == session_id:
                    self.captured_highlights.append(highlight_record)
                    self.save_history()

            print(f"✅ [高能切片已生成 | 主播: {meta['anchor_name']}] 标题: {best_title} (时长: {round(end_t - start_t, 1)}s) 来自素材: {seg_filename}\n")
            return True

        except Exception as e:
            print(f"[高能流水线处理异常 #{session_id}] {e}")
            return False


# 全局单例
realtime_monitor = RealtimeHighEnergyMonitor()
