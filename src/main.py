# -*- coding: utf-8 -*-
"""
智能直播切片系统 - 命令行统一入口 (CLI Entry)
"""

import sys
import os
import argparse
import time
import json

# 强制 UTF-8 标准输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from resolver import DouyinLiveResolver
from recorder import StreamRecorder
from audio_analyzer import AudioEnergyAnalyzer
from danmu_monitor import DanmuMonitor
from heat_scorer import HeatScorer
from asr_transcriber import ASRTranscriber
from semantic_filter import SemanticFilter
from llm_client import LLMClient
from video_composer import VideoComposer
from jianying_exporter import JianYingDraftExporter


def cmd_resolve(args):
    resolver = DouyinLiveResolver()
    print(f"\n>>> 正在解析直播间: {args.target} ...")
    res = resolver.resolve(args.target)
    if not res:
        print("[结果] 解析失败，请确认房间号是否正确或主播是否开播。")
        sys.exit(1)

    print("\n================= 直播间元数据 =================")
    print(f"房间号 (web_rid) : {res['web_rid']}")
    print(f"真实 RoomID      : {res['room_id']}")
    print(f"主播昵称         : {res['anchor_name']}")
    print(f"直播标题         : {res['title']}")
    print(f"当前状态         : {res['status_text']} (Code: {res['status']})")
    print("\n================= 推荐推流地址 =================")
    print(f"[最佳原画 FLV]   : {res['best_flv']}")
    print(f"[最佳原画 HLS]   : {res['best_hls']}")
    print("=================================================\n")


def cmd_record(args):
    recorder = StreamRecorder()
    recorder.record_once(args.target, duration_seconds=args.duration)


def cmd_segment(args):
    recorder = StreamRecorder()
    recorder.record_continuous_segmented(args.target, segment_duration_seconds=args.duration)


def cmd_analyze(args):
    """阶段二与阶段三联合分析：波峰提取 + ASR语音转文字 + 大模型语义精修"""
    video_path = os.path.abspath(args.video)
    if not os.path.exists(video_path):
        print(f"[错误] 视频文件不存在: {video_path}")
        sys.exit(1)

    print(f"\n>>> [阶段二] 开始音频能量波峰分析: {os.path.basename(video_path)}")
    analyzer = AudioEnergyAnalyzer()
    audio_res = analyzer.analyze_peaks(video_path, min_duration_sec=0.5)

    print(f"视频总时长   : {audio_res['total_duration']} 秒")
    print(f"捕获声量突变 : {len(audio_res['peaks'])} 处")

    # 进行热度打分与时间邻近聚类
    scorer = HeatScorer(lead_in_sec=5.0, tail_sec=5.0, min_duration_sec=5.0)
    candidates = scorer.fuse(
        audio_peaks=audio_res["peaks"],
        total_video_duration=audio_res["total_duration"]
    )

    if not candidates:
        print("[提示] 未检测到明显的声量爆发点。")
        return

    print(f"\n================ [阶段三] ASR 语音识别与大模型语义精修 ================")
    transcriber = ASRTranscriber(model_size="tiny")
    semantic_filter = SemanticFilter()

    # 针对最高评分的候选片段进行精修
    top_cand = candidates[0]
    print(f"\n正在对高分候选切片 ({top_cand.segment_id}) 进行 Whisper 语音转录...")
    
    # 截取候选区间的音频进行精准转录
    temp_wav = video_path + ".cand.wav"
    try:
        transcriber.extract_segment_audio(video_path, top_cand.start_time, top_cand.end_time, temp_wav)
        segments = transcriber.transcribe(temp_wav if os.path.exists(temp_wav) else video_path)
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

    print(f"识别出台词分句数量: {len(segments)}")
    for s in segments:
        print(f"  [{s['start']}s -> {s['end']}s] {s['text']}")

    print("\n正在调用大模型语义大脑分析最佳剪入剪出点并生成爆款标题...")
    refine_res = semantic_filter.refine_candidate(top_cand.__dict__, segments)

    print("\n" + "=" * 65)
    print("           ✨ AI 智能切片决策完成 (精修成片参数)")
    print("=" * 65)
    print(f"  • 核心主题   : {refine_res.get('highlight_theme')}")
    print(f"  • 灵魂金句   : 「{refine_res.get('core_quote')}」")
    print(f"  • 精准时间   : {refine_res.get('recommended_cut_start')}s  ===>  {refine_res.get('recommended_cut_end')}s (时长: {refine_res.get('duration')}s)")
    print(f"  • 推荐理由   : {refine_res.get('reason')}")
    print("\n  🔥 推荐抖音爆款标题池:")
    for idx, t in enumerate(refine_res.get("generated_titles", []), 1):
        print(f"    {idx}. {t}")
    print("=" * 65 + "\n")


def cmd_danmu(args):
    """实时监听直播间弹幕与热度统计"""
    resolver = DouyinLiveResolver()
    print(f"\n>>> 正在获取直播间信息: {args.target} ...")
    meta = resolver.resolve(args.target)
    if not meta:
        print("[错误] 直播间不存在或解析失败")
        sys.exit(1)

    print(f"成功锁定主播: {meta['anchor_name']} (RoomID: {meta['room_id']})")
    print("正在尝试建立弹幕 WebSocket 连接...\n")

    monitor = DanmuMonitor(room_id=meta["room_id"], web_rid=meta["web_rid"])

    def on_message(user, text):
        print(f"[{user}]: {text}")

    monitor.add_danmu_callback(on_message)
    monitor.start()

    time.sleep(2)
    if not monitor.is_running:
        print("\n>>> [进入模拟演示模式] 演示 10s 滑动窗口热度密度与情绪关键词突增算法:")
        import random
        demo_texts = [
            "哈哈哈哈笑死我了", "主播太搞笑了", "66666", "神操作啊", "卧槽真的假的",
            "破防了退钱", "牛逼", "太真实了", "支持支持", "主播讲得好"
        ]
        try:
            for sec in range(1, 16):
                time.sleep(1)
                batch_count = random.randint(2, 6)
                for _ in range(batch_count):
                    t = random.choice(demo_texts)
                    with monitor.lock:
                        monitor.danmu_queue.append((time.time(), t, f"用户_{random.randint(100, 999)}"))
                
                if sec % 3 == 0:
                    metrics = monitor.get_window_heat_metrics()
                    print(f"[{sec:02d}s 热度心电图] 窗口弹幕: {metrics['danmu_count']:2d} 条 | 密度: {metrics['density_per_sec']:4.1f}/s | 关键词命中: {metrics['keyword_hits']} 次 | 高频词: {metrics['top_keywords']}")
            print("\n✅ 弹幕热度滑动窗口算法验证完毕！按 Ctrl+C 退出。\n")
        except KeyboardInterrupt:
            return

    try:
        while True:
            time.sleep(5)
            metrics = monitor.get_window_heat_metrics()
            if metrics["danmu_count"] > 0:
                print(f"[热度监控 10s窗口] 弹幕量: {metrics['danmu_count']} | 密度: {metrics['density_per_sec']}/s | 关键词命中: {metrics['keyword_hits']}次")
    except KeyboardInterrupt:
        print("\n正在停止弹幕监听...")
        monitor.stop()


def cmd_export(args):
    """一键渲染 9:16 成品短视频并同步导出剪映专业版草稿"""
    video_path = os.path.abspath(args.video)
    if not os.path.exists(video_path):
        print(f"[错误] 视频不存在: {video_path}")
        sys.exit(1)

    start_sec = args.start
    end_sec = args.end
    title = args.title or "直播精彩切片"

    print(f"\n>>> 正在为视频导出成片与剪映草稿: {os.path.basename(video_path)}")
    print(f"    区间: {start_sec}s -> {end_sec}s | 标题: {title}")

    # 1. 自动提取区间字幕
    transcriber = ASRTranscriber(model_size="tiny")
    temp_wav = video_path + ".temp_sub.wav"
    subtitles = []
    try:
        transcriber.extract_segment_audio(video_path, start_sec, end_sec, temp_wav)
        subtitles = transcriber.transcribe(temp_wav if os.path.exists(temp_wav) else video_path)
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

    srt_content = ASRTranscriber.generate_srt(subtitles)

    # 2. 通道 A: 导出 MP4
    composer = VideoComposer()
    mp4_path = composer.compose_short(
        input_video=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        title=title,
        srt_content=srt_content
    )

    # 3. 通道 B: 导出剪映工程草稿
    exporter = JianYingDraftExporter()
    draft_dir = exporter.export_draft(
        draft_title=title,
        video_path=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        subtitles=subtitles
    )

    print("\n" + "=" * 65)
    print("           ✨ 双轨成片与剪映工程导出完毕！")
    print("=" * 65)
    if mp4_path:
        print(f"  • 成品短视频 (MP4) : {mp4_path}")
    print(f"  • 剪映工程草稿目录 : {draft_dir}")
    print("=================================================\n")


def cmd_gui(args):
    """启动现代可视化工作台"""
    import subprocess
    gui_script = os.path.join(os.path.dirname(__file__), "start_gui.py")
    subprocess.run([sys.executable, gui_script])


def main():
    parser = argparse.ArgumentParser(description="智能直播切片系统 - 命令行统一入口")
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    p_resolve = subparsers.add_parser("resolve", help="解析直播间推流地址及状态")
    p_resolve.add_argument("target", help="直播间房间号、PC直播间网址或移动端短链")

    p_record = subparsers.add_parser("record", help="单次定长录制")
    p_record.add_argument("target", help="直播间房间号或网址")
    p_record.add_argument("-d", "--duration", type=int, default=10, help="录制时长(秒)，默认10秒")

    p_segment = subparsers.add_parser("segment", help="持续分片录制(工业流水线)")
    p_segment.add_argument("target", help="直播间房间号或网址")
    p_segment.add_argument("-d", "--duration", type=int, default=300, help="单分片时长(秒)，默认300秒")

    p_analyze = subparsers.add_parser("analyze", help="多模态能量分析 + Whisper语音转录 + 大模型语义精修")
    p_analyze.add_argument("video", help="待分析的 MP4 视频文件路径")

    p_danmu = subparsers.add_parser("danmu", help="实时监听直播间弹幕与热度指标")
    p_danmu.add_argument("target", help="直播间房间号或网址")

    # 阶段四核心: 一键导出 MP4 与剪映草稿
    p_export = subparsers.add_parser("export", help="一键合成9:16短视频成片并导出剪映草稿工程")
    p_export.add_argument("video", help="原始视频路径")
    p_export.add_argument("-s", "--start", type=float, default=0.0, help="剪入起始时间(秒)")
    p_export.add_argument("-e", "--end", type=float, default=10.0, help="剪出结束时间(秒)")
    p_export.add_argument("-t", "--title", default="", help="短视频爆款标题")

    # 阶段五核心: 可视化工作台启动命令
    p_gui = subparsers.add_parser("gui", help="一键启动现代可视化工作台 (Web/桌面浏览器)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "resolve": cmd_resolve,
        "record": cmd_record,
        "segment": cmd_segment,
        "analyze": cmd_analyze,
        "danmu": cmd_danmu,
        "export": cmd_export,
        "gui": cmd_gui,
    }

    if args.command in dispatch:
        dispatch[args.command](args)


if __name__ == "__main__":
    main()
