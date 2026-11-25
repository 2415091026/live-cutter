# -*- coding: utf-8 -*-
"""
智能直播切片系统 - 后台服务 (FastAPI API Server)
为现代可视化工作台提供直播推流解析、录制调度、AI精彩识别与双轨成片导出的全功能接口
"""

import os
import sys
import json
import subprocess
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from resolver import DouyinLiveResolver
from recorder import StreamRecorder
from audio_analyzer import AudioEnergyAnalyzer
from heat_scorer import HeatScorer
from asr_transcriber import ASRTranscriber
from semantic_filter import SemanticFilter
from llm_client import LLMClient
from video_composer import VideoComposer
from jianying_exporter import JianYingDraftExporter
from anchor_profile import AnchorProfileManager
from realtime_monitor import realtime_monitor
from danmu_monitor import danmu_service

app = FastAPI(title="Live-Cutter API Server", version="1.0.0")

# 全局服务退出信号（用于按 Ctrl+C 时 1 秒内中断所有 SSE 与直播流代理长连接）
_server_shutdown_event = threading.Event()


@app.on_event("startup")
async def _install_windows_asyncio_filter():
    """静默过滤 Windows ProactorEventLoop 在浏览器主动断开视频 Range/SSE 连接时产生的 WinError 10054 噪声日志"""
    _server_shutdown_event.clear()
    if sys.platform != "win32":
        return
    import asyncio
    loop = asyncio.get_running_loop()
    orig_handler = loop.get_exception_handler()

    def _filtered_handler(cur_loop, context):
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054:
            return
        if orig_handler:
            orig_handler(cur_loop, context)
        else:
            cur_loop.default_exception_handler(context)

    loop.set_exception_handler(_filtered_handler)


@app.on_event("shutdown")
def _graceful_shutdown_cleanup():
    """服务关闭时立即广播退出信号并彻底清理所有后台拉流与无头浏览器子进程"""
    _server_shutdown_event.set()
    try:
        danmu_service.stop()
    except Exception:
        pass
    try:
        realtime_monitor.stop_monitoring()
    except Exception:
        pass
    with _live_preview_lock:
        _terminate_preview_proc(_active_preview_proc)

# 跨域支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DRAFTS_DIR = os.path.join(BASE_DIR, "drafts")
WEB_DIR = os.path.join(BASE_DIR, "web")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LLM_CONFIG_FILE = os.path.join(CONFIG_DIR, "llm_config.json")
SYSTEM_CONFIG_FILE = os.path.join(CONFIG_DIR, "system_config.json")

os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

# 静态资源挂载
app.mount("/static/recordings", StaticFiles(directory=RECORDINGS_DIR), name="recordings")
app.mount("/static/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# 挂载 Vue 3 构建资源
assets_dir = os.path.join(WEB_DIR, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

resolver = DouyinLiveResolver()
profile_mgr = AnchorProfileManager()
llm_client = LLMClient()
transcriber = ASRTranscriber(model_size="tiny")
semantic_filter = SemanticFilter(llm_client=llm_client)
composer = VideoComposer(output_dir=OUTPUT_DIR)
jianying_exporter = JianYingDraftExporter(custom_drafts_dir=DRAFTS_DIR)


# 数据入参模型
class ResolveReq(BaseModel):
    target: str

class RecordReq(BaseModel):
    target: str
    duration: int = 10

class AnalyzeReq(BaseModel):
    video_path: str
    anchor_id: Optional[str] = None

class ExportReq(BaseModel):
    video_path: str
    start_time: float
    end_time: float
    title: str = "直播精彩切片"
    subtitles: Optional[List[Dict[str, Any]]] = None

class DeleteRecordingReq(BaseModel):
    filename: str

class DeleteBatchReq(BaseModel):
    date: Optional[str] = None
    filenames: Optional[List[str]] = None


def find_video_path(filename_or_path: str) -> Optional[str]:
    """
    多层级递归定位视频文件真实路径（兼容绝对路径、相对路径及日期子目录）
    """
    if not filename_or_path:
        return None
    # 1. 尝试直接作为绝对路径
    if os.path.isabs(filename_or_path) and os.path.exists(filename_or_path):
        return filename_or_path
    
    # 2. 尝试直接与 RECORDINGS_DIR 拼接
    direct_p = os.path.join(RECORDINGS_DIR, filename_or_path)
    if os.path.exists(direct_p):
        return direct_p

    target_name = os.path.basename(filename_or_path)
    # 3. 递归在 RECORDINGS_DIR 及其所有子目录中搜索同名文件
    for root, _, files in os.walk(RECORDINGS_DIR):
        if target_name in files:
            return os.path.join(root, target_name)
            
    return None

LLM_CONFIG_PATH = os.path.join(BASE_DIR, "config", "llm_config.json")
SYSTEM_CONFIG_PATH = os.path.join(BASE_DIR, "config", "system_config.json")

class ConfigSaveReq(BaseModel):
    llm: Dict[str, Any]
    system: Dict[str, Any]

@app.get("/api/config")
def get_config():
    """获取系统全部配置（包含大模型配置与切片录制策略）"""
    llm_cfg = {}
    if os.path.exists(LLM_CONFIG_PATH):
        try:
            with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
                llm_cfg = json.load(f)
        except Exception:
            pass

    sys_cfg = {}
    if os.path.exists(SYSTEM_CONFIG_PATH):
        try:
            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as f:
                sys_cfg = json.load(f)
        except Exception:
            pass

    return {
        "llm": {
            "engine_mode": llm_cfg.get("engine_mode", "multimodal"),
            "provider": llm_cfg.get("provider", "qwen"),
            "base_url": llm_cfg.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "api_key": llm_cfg.get("api_key", ""),
            "model": llm_cfg.get("model", "qwen3.8-omni-flash"),
            "text_model": llm_cfg.get("text_model", "qwen3.8-flash"),
            "multimodal_model": llm_cfg.get("multimodal_model", "qwen3.8-omni-flash"),
            "frame_sample_count": llm_cfg.get("frame_sample_count", 6),
            "temperature": llm_cfg.get("temperature", 0.3),
            "timeout_seconds": llm_cfg.get("timeout_seconds", 35),
            "max_tokens": llm_cfg.get("max_tokens", 2000)
        },
        "system": {
            "segment_duration": sys_cfg.get("segment_duration", realtime_monitor.seg_duration),
            "default_record_duration": sys_cfg.get("default_record_duration", 20),
            "target_slice_min": sys_cfg.get("target_slice_min", realtime_monitor.target_slice_min),
            "target_slice_max": sys_cfg.get("target_slice_max", realtime_monitor.target_slice_max),
            "intensity_threshold": sys_cfg.get("intensity_threshold", realtime_monitor.intensity_threshold),
            "min_energy": sys_cfg.get("min_energy", realtime_monitor.min_energy),
            "auto_short_enabled": sys_cfg.get("auto_short_enabled", realtime_monitor.auto_short_enabled),
            "auto_draft_enabled": sys_cfg.get("auto_draft_enabled", realtime_monitor.auto_draft_enabled)
        }
    }

@app.post("/api/config")
def save_config(req: ConfigSaveReq):
    """保存并热重载配置（大模型双模配置与系统切片策略）"""
    try:
        cur_llm = {}
        if os.path.exists(LLM_CONFIG_PATH):
            with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
                cur_llm = json.load(f)
        cur_llm.update(req.llm)
        # 根据当前选择的 engine_mode 同步主 model 字段
        mode = cur_llm.get("engine_mode", "multimodal")
        if mode == "multimodal":
            cur_llm["model"] = cur_llm.get("multimodal_model", "qwen3.8-omni-flash")
        else:
            cur_llm["model"] = cur_llm.get("text_model", "qwen3.8-flash")

        with open(LLM_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cur_llm, f, ensure_ascii=False, indent=2)

        with open(SYSTEM_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(req.system, f, ensure_ascii=False, indent=2)

        realtime_monitor.update_config(req.system)
        
        global llm_client, semantic_filter
        llm_client = LLMClient()
        semantic_filter = SemanticFilter(llm_client=llm_client)
        realtime_monitor.semantic_filter = semantic_filter

        return {
            "status": "ok",
            "engine_mode": semantic_filter.engine_mode,
            "active_model": semantic_filter.active_model,
            "message": f"配置已热重载生效！当前模式: {semantic_filter.engine_mode} ({semantic_filter.active_model})"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")


@app.get("/api/system/status")
def get_system_status():
    """获取系统整体状态与大模型配置"""
    return {
        "status": "online",
        "llm_framework": "LangChain (LCEL)",
        "engine_mode": semantic_filter.engine_mode,
        "llm_provider": llm_client.config.get("provider", "qwen"),
        "llm_model": semantic_filter.active_model,
        "text_model": semantic_filter.analyzer.text_model,
        "multimodal_model": semantic_filter.analyzer.multimodal_model,
        "llm_ready": llm_client.is_configured,
        "storage": {
            "recordings_count": len([f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp4")]),
            "output_count": len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")]),
            "drafts_count": len(os.listdir(DRAFTS_DIR))
        }
    }


@app.get("/api/anchors")
def list_anchors():
    """获取所有主播档案"""
    return profile_mgr.list_profiles()


@app.post("/api/anchors")
def save_anchor(profile: Dict[str, Any]):
    """保存主播档案"""
    success = profile_mgr.save_profile(profile)
    if not success:
        raise HTTPException(status_code=400, detail="保存失败，请提供有效的 anchor_id")
    return {"message": "保存成功"}


@app.post("/api/resolve")
def resolve_live(req: ResolveReq):
    """解析直播间推流地址"""
    res = resolver.resolve(req.target)
    if not res:
        raise HTTPException(status_code=404, detail="无法解析该直播间，请确认房间号是否正确或主播是否开播")
    return res


# 全局直播预览代理进程锁（确保同一时刻只保留最新一路预览拉流，杜绝僵尸进程）
_live_preview_lock = threading.Lock()
_active_preview_proc: Optional[subprocess.Popen] = None


def _terminate_preview_proc(proc: Optional[subprocess.Popen]):
    """彻底终止指定的预览代理 FFmpeg 子进程"""
    if proc and proc.poll() is None:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                proc.kill()
        except Exception:
            pass


@app.get("/api/live/proxy")
def proxy_live_stream(target: str = "", stream_url: str = ""):
    """
    抖音直播流零转码实时代理接口 (FLV/HLS -> fragmented MP4 流式透传)
    解决浏览器跨域 (CORS)、Referer 防盗链校验以及原生 <video> 无法直接解封装 FLV 的问题
    """
    global _active_preview_proc

    pull_url = stream_url.strip()
    if not pull_url:
        if not target.strip():
            raise HTTPException(status_code=400, detail="请提供直播间房间号 target 或推流地址 stream_url")
        meta = resolver.resolve(target.strip())
        if not meta or not meta.get("is_living"):
            raise HTTPException(status_code=404, detail="主播当前未开播或无法获取有效直播流")
        pull_url = meta.get("best_flv") or meta.get("best_hls") or ""
        if not pull_url:
            raise HTTPException(status_code=404, detail="未找到可用的高清推流地址")

    ua = resolver.headers["User-Agent"]
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-analyzeduration", "1000000",
        "-probesize", "1000000",
        "-headers", f"User-Agent: {ua}\r\nReferer: https://live.douyin.com/\r\n",
        "-i", pull_url,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "mp4",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "pipe:1"
    ]

    with _live_preview_lock:
        # 切换频道或刷新流时，先清理上一路预览进程
        _terminate_preview_proc(_active_preview_proc)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            _active_preview_proc = proc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"启动直播流代理失败: {str(e)}")

    def stream_generator():
        try:
            while not _server_shutdown_event.is_set():
                if proc.stdout is None:
                    break
                chunk = proc.stdout.read(32768)
                if not chunk:
                    break
                yield chunk
        except (GeneratorExit, BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _terminate_preview_proc(proc)
            with _live_preview_lock:
                global _active_preview_proc
                if _active_preview_proc is proc:
                    _active_preview_proc = None

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(stream_generator(), media_type="video/mp4", headers=headers)


@app.post("/api/record")
def record_stream(req: RecordReq):
    """触发录制"""
    recorder = StreamRecorder(output_dir=RECORDINGS_DIR)
    saved_file = recorder.record_once(req.target, duration_seconds=req.duration)
    if not saved_file:
        raise HTTPException(status_code=500, detail="录制失败，请检查直播源或网络")
    return {
        "file_path": saved_file,
        "filename": os.path.basename(saved_file),
        "url": f"/static/recordings/{os.path.basename(saved_file)}"
    }


class MonitorReq(BaseModel):
    target: str

@app.post("/api/monitor/start")
def start_monitor(req: MonitorReq):
    """主动开启实时高能监听与自动录制（同步联动实时弹幕与礼物采集）"""
    try:
        res = realtime_monitor.start_monitoring(req.target)
        try:
            danmu_service.start(req.target)
        except Exception as dm_err:
            print(f"[弹幕联动提示] 启动弹幕监听异常: {dm_err}")
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/monitor/stop")
def stop_monitor():
    """停止实时监控"""
    return realtime_monitor.stop_monitoring()


# ==============================================================================
# 实时弹幕与礼物控制及 SSE 推送接口
# ==============================================================================

class DanmuStartReq(BaseModel):
    target: str
    meta: Optional[Dict[str, Any]] = None

@app.post("/api/danmu/start")
def start_danmu(req: DanmuStartReq):
    """启动或切换直播间实时弹幕与礼物采集"""
    try:
        return danmu_service.start(req.target, resolved_meta=req.meta)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/danmu/stop")
def stop_danmu():
    """停止直播间实时弹幕与礼物采集"""
    return danmu_service.stop()

@app.post("/api/danmu/clear")
def clear_danmu():
    """清空当前缓存的弹幕与礼物列表"""
    return danmu_service.clear_history()

@app.post("/api/danmu/login")
def launch_danmu_login():
    """打开本机浏览器扫码登录抖音以解锁直播间完整实时礼物推送"""
    try:
        return danmu_service.launch_douyin_login()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CookieSaveReq(BaseModel):
    cookie: str

@app.post("/api/danmu/cookie")
def save_danmu_cookie(req: CookieSaveReq):
    """手动保存抖音登录态 Cookie"""
    try:
        return danmu_service.save_cookie_string(req.cookie)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/danmu/status")
def get_danmu_status():
    """查询当前弹幕与礼物连接状态、统计指标及历史消息列表"""
    return danmu_service.get_status(include_lists=True)

@app.get("/api/danmu/stream")
def stream_danmu_events():
    """
    SSE 实时弹幕与礼物事件流接口
    首帧下发 snapshot，后续毫秒级推送 chat / gift / metrics / state / cleared 事件
    """
    import queue as py_queue

    def event_generator():
        sub_q = danmu_service.subscribe()
        try:
            # 首帧推送当前完整快照
            snapshot = danmu_service.get_status(include_lists=True)
            yield f"data: {json.dumps({'type': 'snapshot', 'data': snapshot}, ensure_ascii=False)}\n\n"

            idle_ticks = 0
            while not _server_shutdown_event.is_set():
                try:
                    evt = sub_q.get(timeout=1.0)
                    idle_ticks = 0
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                except py_queue.Empty:
                    idle_ticks += 1
                    if idle_ticks >= 15:
                        idle_ticks = 0
                        # 发送 SSE 注释心跳帧维持长连接
                        yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            danmu_service.unsubscribe(sub_q)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@app.get("/api/monitor/status")
def get_monitor_status():
    """获取当前监听状态与实时捕获的高能切片列表，附带录像素材库的动态遥测信息"""
    status = realtime_monitor.get_status()
    try:
        mp4_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp4")]
        status["recordings_count"] = len(mp4_files)
        if mp4_files:
            latest_f = max(mp4_files, key=lambda f: os.path.getmtime(os.path.join(RECORDINGS_DIR, f)))
            status["latest_recording"] = latest_f
            status["latest_recording_mtime"] = os.path.getmtime(os.path.join(RECORDINGS_DIR, latest_f))
        else:
            status["latest_recording"] = None
            status["latest_recording_mtime"] = 0
    except Exception:
        status["recordings_count"] = 0
        status["latest_recording"] = None
        status["latest_recording_mtime"] = 0
    return status

@app.get("/api/recordings")
def list_recordings():
    """获取已有录制视频列表 (支持递归扫描日期子目录，提取精准日期与时间元数据)"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    files = []

    # 递归遍历 RECORDINGS_DIR 根目录及所有日期子目录
    for root, _, filenames in os.walk(RECORDINGS_DIR):
        for f in filenames:
            if f.endswith(".mp4"):
                p = os.path.join(root, f)
                try:
                    sz = os.path.getsize(p)
                    if sz > 1024:  # 至少大于 1KB 的有效视频
                        mtime = os.path.getmtime(p)
                        dt = datetime.fromtimestamp(mtime)
                        time_display = dt.strftime("%H:%M:%S")
                        date_str = dt.strftime("%Y-%m-%d")

                        # 人性化日期标签
                        if date_str == today_str:
                            date_display = f"今天 ({dt.strftime('%m-%d')})"
                        elif date_str == yesterday_str:
                            date_display = f"昨天 ({dt.strftime('%m-%d')})"
                        else:
                            date_display = date_str

                        # 计算相对路径，供静态资源 url 访问
                        rel_path = os.path.relpath(p, RECORDINGS_DIR).replace("\\", "/")

                        # 智能解析文件名，提取主播与时段标签
                        anchor_label = "-"
                        name_core = f.replace(".mp4", "")
                        parts = name_core.split("_")
                        if len(parts) >= 3:
                            # 新规则: 21-22-30_PANDAER_p001.mp4 或 21-25-30_PANDAER_10s.mp4
                            if "-" in parts[0] and len(parts[0]) == 8:
                                anchor_label = parts[1]
                            # 旧规则: live_256751986134_20261102_190555_10s.mp4
                            elif parts[0] == "live":
                                t_part = parts[-2]
                                if len(t_part) == 6 and t_part.isdigit():
                                    time_display = f"{t_part[0:2]}:{t_part[2:4]}:{t_part[4:6]}"
                        
                        files.append({
                            "filename": f,
                            "rel_path": rel_path,
                            "file_path": p,
                            "size_mb": round(sz / (1024 * 1024), 2),
                            "url": f"/static/recordings/{rel_path}",
                            "mtime": mtime,
                            "date": date_str,
                            "date_display": date_display,
                            "time_display": time_display,
                            "anchor_label": anchor_label
                        })
                except Exception:
                    pass

    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


@app.post("/api/recordings/delete")
def delete_recording(req: DeleteRecordingReq):
    """删除单条录像素材 (物理删除并清除同名缓存文件)"""
    real_path = find_video_path(req.filename)
    if not real_path or not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.filename}")

    try:
        os.remove(real_path)
        # 尝试清理可能存在的同名波形缓存与音频碎片
        base_no_ext = os.path.splitext(real_path)[0]
        import glob
        for extra_f in glob.glob(base_no_ext + "*"):
            if extra_f != real_path and (extra_f.endswith(".wav") or extra_f.endswith(".srt")):
                try:
                    os.remove(extra_f)
                except Exception:
                    pass
        return {"status": "ok", "message": f"已成功删除视频: {os.path.basename(real_path)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@app.post("/api/recordings/delete-batch")
def delete_recordings_batch(req: DeleteBatchReq):
    """批量删除录像素材 (支持按日期整天删除或指定文件名批量清理)"""
    deleted_count = 0
    all_files = list_recordings()

    target_paths = []
    if req.date:
        for item in all_files:
            if item.get("date") == req.date:
                target_paths.append(item["file_path"])
    elif req.filenames:
        for fn in req.filenames:
            p = find_video_path(fn)
            if p:
                target_paths.append(p)

    for p in target_paths:
        if os.path.exists(p):
            try:
                os.remove(p)
                deleted_count += 1
            except Exception:
                pass

    return {
        "status": "ok",
        "deleted_count": deleted_count,
        "message": f"成功删除 {deleted_count} 个视频文件"
    }


@app.post("/api/recordings/organize-by-date")
def organize_recordings_by_date():
    """将 recordings 根目录下的已有平铺视频按其修改日期整理移动到 YYYY-MM-DD 子目录中"""
    import shutil
    moved_count = 0
    for f in os.listdir(RECORDINGS_DIR):
        p = os.path.join(RECORDINGS_DIR, f)
        if os.path.isfile(p) and f.endswith(".mp4"):
            try:
                mtime = os.path.getmtime(p)
                date_folder = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                target_dir = os.path.join(RECORDINGS_DIR, date_folder)
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, f)
                if not os.path.exists(target_path):
                    shutil.move(p, target_path)
                    moved_count += 1
            except Exception as e:
                print(f"[归档跳过] {f}: {e}")
    return {
        "status": "ok",
        "moved_count": moved_count,
        "message": f"已将 {moved_count} 个文件按日期整理归档到各日期文件夹中！"
    }


@app.post("/api/analyze")
def analyze_video(req: AnalyzeReq):
    """全自动多模态波峰分析 + 语音转录 + Qwen 语义精修"""
    real_path = find_video_path(req.video_path)
    if real_path:
        req.video_path = real_path
    else:
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {req.video_path}")

    # 1. 音频能量波峰
    analyzer = AudioEnergyAnalyzer()
    audio_res = analyzer.analyze_peaks(req.video_path, min_duration_sec=0.5)

    # 2. 多模态聚类初筛
    scorer = HeatScorer(lead_in_sec=4.0, tail_sec=4.0, min_duration_sec=4.0)
    candidates = scorer.fuse(
        audio_peaks=audio_res["peaks"],
        total_video_duration=audio_res["total_duration"]
    )

    if not candidates:
        return {"peaks": audio_res["peaks"], "candidates": []}

    profile = profile_mgr.get_profile(req.anchor_id) if req.anchor_id else None
    if not profile:
        profile = profile_mgr.match_profile(anchor_name=os.path.basename(req.video_path))

    # 3. 针对前 3 个候选片段调用 Whisper 与大模型精修
    enriched_candidates = []
    for cand in candidates[:3]:
        # 提取音频分句
        temp_wav = req.video_path + f".cand_{cand.segment_id}.wav"
        subtitles = []
        try:
            transcriber.extract_segment_audio(req.video_path, cand.start_time, cand.end_time, temp_wav)
            if os.path.exists(temp_wav):
                subtitles = transcriber.transcribe(temp_wav)
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

        # 大模型精修断句与标题（支持声文模式与多模态音画模式）
        refined = semantic_filter.refine_candidate(
            cand.__dict__,
            subtitles,
            anchor_profile=profile,
            video_path=req.video_path
        )

        source_filename = os.path.basename(req.video_path)
        enriched_candidates.append({
            "segment_id": cand.segment_id,
            "heat_score": cand.heat_score,
            "raw_start": cand.start_time,
            "raw_end": cand.end_time,
            "peak_time": cand.peak_time,
            "precise_start": refined.get("recommended_cut_start", cand.start_time),
            "precise_end": refined.get("recommended_cut_end", cand.end_time),
            "duration": refined.get("duration", cand.duration),
            "theme": refined.get("highlight_theme", "高能名场面"),
            "trigger_tag": refined.get("highlight_theme", "高能爆发"),
            "trigger_reason": refined.get("trigger_reason") or cand.reason,
            "visual_action_summary": refined.get("visual_action_summary", ""),
            "layout_recommendation": refined.get("layout_recommendation", "split_screen_game"),
            "engine_mode": refined.get("engine_mode", semantic_filter.engine_mode),
            "model_used": refined.get("model_used", semantic_filter.active_model),
            "core_quote": refined.get("core_quote", "-"),
            "titles": refined.get("generated_titles", ["高能精彩片段"]),
            "reason": refined.get("trigger_reason") or cand.reason,
            "subtitles": subtitles,
            "source_video": source_filename,
            "source_filename": source_filename,
            "source_path": req.video_path,
            "source_url": f"/static/recordings/{source_filename}",
            "video_path": req.video_path
        })

    return {
        "total_duration": audio_res["total_duration"],
        "avg_energy": audio_res["avg_energy"],
        "peaks_count": len(audio_res["peaks"]),
        "candidates": enriched_candidates
    }


@app.post("/api/analyze/stream")
def analyze_video_stream(req: AnalyzeReq):
    """
    流式大模型分析接口 (SSE)
    实时输出：音频分析进度 -> Whisper分词 -> SystemMessage角色设定 -> HumanMessage输入上下文 -> LangChain Token流式打字 -> 结构化切片
    """
    def event_stream():
        import json
        real_path = find_video_path(req.video_path)
        if real_path:
            req.video_path = real_path
        else:
            yield f"data: {json.dumps({'type': 'error', 'content': f'视频文件不存在: {req.video_path}'})}\n\n"
            return

        # 阶段 1: 音频能量波峰
        yield f"data: {json.dumps({'type': 'step', 'step': 1, 'content': '⚡ 正在提取 PCM 音频波形并计算短时能量波峰 (RMS)...'}, ensure_ascii=False)}\n\n"
        analyzer = AudioEnergyAnalyzer()
        audio_res = analyzer.analyze_peaks(req.video_path, min_duration_sec=0.5)

        # 阶段 2: 能量聚合粗筛
        total_d = audio_res.get("total_duration", 0)
        p_count = len(audio_res.get("peaks", []))
        step2_msg = f"📊 声场分析完成：总时长 {total_d}s，捕捉到 {p_count} 处高潮能量波峰"
        yield f"data: {json.dumps({'type': 'step', 'step': 2, 'content': step2_msg}, ensure_ascii=False)}\n\n"
        scorer = HeatScorer(lead_in_sec=4.0, tail_sec=4.0, min_duration_sec=4.0)
        candidates = scorer.fuse(
            audio_peaks=audio_res["peaks"],
            total_video_duration=audio_res["total_duration"]
        )

        if not candidates:
            yield f"data: {json.dumps({'type': 'finish', 'candidates': [], 'peaks': audio_res['peaks']}, ensure_ascii=False)}\n\n"
            return

        profile = profile_mgr.get_profile(req.anchor_id) if req.anchor_id else None
        if not profile:
            profile = profile_mgr.match_profile(anchor_name=os.path.basename(req.video_path))

        enriched_candidates = []
        for idx, cand in enumerate(candidates[:2], start=1):
            yield f"data: {json.dumps({'type': 'step', 'step': 3, 'content': f'🎙️ [片段 #{idx}] 正在调度 Faster-Whisper 进行毫秒级语音对齐...'}, ensure_ascii=False)}\n\n"

            temp_wav = req.video_path + f".cand_{cand.segment_id}.wav"
            subtitles = []
            try:
                transcriber.extract_segment_audio(req.video_path, cand.start_time, cand.end_time, temp_wav)
                if os.path.exists(temp_wav):
                    subtitles = transcriber.transcribe(temp_wav)
            finally:
                if os.path.exists(temp_wav):
                    try:
                        os.remove(temp_wav)
                    except Exception:
                        pass

            # 阶段 3: LangChain 大模型流式认知（自适应路由 qwen3.8-flash 或 qwen3.8-omni-flash 多模态）
            current_aname = profile.get("anchor_name", "通用") if profile else "通用"
            mode_tag = f"多模态音画 ({semantic_filter.active_model})" if semantic_filter.engine_mode == "multimodal" else f"经典声文 ({semantic_filter.active_model})"
            step_text = f"🧠 [片段 #{idx}] 启动 {mode_tag} 认知链，挂载主播【{current_aname}】专属档案..."
            yield f"data: {json.dumps({'type': 'step', 'step': 4, 'content': step_text}, ensure_ascii=False)}\n\n"

            cand_dict = cand.__dict__
            refined_result = None

            # 迭代 stream_refine_candidate 生成器
            for event in semantic_filter.stream_refine_candidate(
                cand_dict,
                subtitles,
                anchor_profile=profile,
                video_path=req.video_path
            ):
                evt_type = event.get("event")
                if evt_type == "system_message":
                    pass
                elif evt_type == "human_message":
                    yield f"data: {json.dumps({'type': 'human_message', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif evt_type == "token":
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif evt_type == "result":
                    refined_result = event.get("data", {})

            if not refined_result:
                refined_result = semantic_filter.refine_candidate(
                    cand_dict,
                    subtitles,
                    anchor_profile=profile,
                    video_path=req.video_path
                )

            source_filename = os.path.basename(req.video_path)
            cand_obj = {
                "segment_id": cand.segment_id,
                "heat_score": cand.heat_score,
                "raw_start": cand.start_time,
                "raw_end": cand.end_time,
                "peak_time": cand.peak_time,
                "precise_start": refined_result.get("recommended_cut_start", cand.start_time),
                "precise_end": refined_result.get("recommended_cut_end", cand.end_time),
                "duration": refined_result.get("duration", cand.duration),
                "theme": refined_result.get("highlight_theme", "高能名场面"),
                "trigger_tag": refined_result.get("highlight_theme", "高能爆发"),
                "trigger_reason": refined_result.get("trigger_reason") or cand.reason,
                "visual_action_summary": refined_result.get("visual_action_summary", ""),
                "layout_recommendation": refined_result.get("layout_recommendation", "split_screen_game"),
                "engine_mode": refined_result.get("engine_mode", semantic_filter.engine_mode),
                "model_used": refined_result.get("model_used", semantic_filter.active_model),
                "core_quote": refined_result.get("core_quote", "-"),
                "titles": refined_result.get("generated_titles", ["高能精彩片段"]),
                "reason": refined_result.get("trigger_reason") or cand.reason,
                "subtitles": subtitles,
                "source_video": source_filename,
                "source_filename": source_filename,
                "source_path": req.video_path,
                "source_url": f"/static/recordings/{source_filename}",
                "video_path": req.video_path
            }
            enriched_candidates.append(cand_obj)

            yield f"data: {json.dumps({'type': 'candidate_ready', 'candidate': cand_obj}, ensure_ascii=False)}\n\n"

        # 全部完成
        yield f"data: {json.dumps({'type': 'finish', 'candidates': enriched_candidates, 'peaks': audio_res['peaks'], 'total_duration': audio_res['total_duration'], 'avg_energy': audio_res['avg_energy']}, ensure_ascii=False)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.post("/api/export")
def export_short(req: ExportReq):
    """双轨成片导出 (MP4 + 剪映草稿)"""
    real_path = find_video_path(req.video_path)
    if real_path:
        req.video_path = real_path
    else:
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {req.video_path}")

    srt_content = ""
    subtitles = req.subtitles or []
    if subtitles:
        srt_content = ASRTranscriber.generate_srt(subtitles)

    # 1. 渲染 MP4 成品
    mp4_filename = f"clip_{int(req.start_time)}_{int(req.end_time)}.mp4"
    mp4_path = composer.compose_short(
        input_video=req.video_path,
        start_sec=req.start_time,
        end_sec=req.end_time,
        title=req.title,
        srt_content=srt_content,
        output_filename=mp4_filename
    )

    # 2. 导出剪映专业版草稿
    draft_dir = jianying_exporter.export_draft(
        draft_title=req.title,
        video_path=req.video_path,
        start_sec=req.start_time,
        end_sec=req.end_time,
        subtitles=subtitles
    )

    # 3. 构造直发标签与发布文案
    tags = ["#直播名场面", "#高能时刻", "#电竞日常", "#游戏名场面"]
    if "陈伯" in req.video_path or "陈伯" in req.title:
        tags.insert(0, "#陈伯")
        tags.insert(1, "#跑跑卡丁车")
    
    publish_text = f"🔥 {req.title}\n\n主播高能名场面来袭，这波操作直接封神！\n{' '.join(tags)}"

    return {
        "success": True,
        "title": req.title,
        "publish_text": publish_text,
        "tags": tags,
        "mp4_path": mp4_path,
        "mp4_url": f"/static/output/{os.path.basename(mp4_path)}" if mp4_path else None,
        "draft_dir": draft_dir
    }


# 前端页面根路由
@app.get("/")
def serve_index():
    index_file = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Live-Cutter Web UI is loading..."}
