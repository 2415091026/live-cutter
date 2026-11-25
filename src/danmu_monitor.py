# -*- coding: utf-8 -*-
"""
抖音直播弹幕与礼物实时监听引擎 (Douyin Live Danmu & Gift Engine)
架构特性：
1. 内置零依赖纯 Python Protobuf Wire 动态解码器，精准解包 PushFrame / Response /
   WebcastChatMessage (弹幕) / WebcastGiftMessage (礼物) / WebcastRoomUserSeqMessage (在线人数) / WebcastLikeMessage (点赞)；
2. 双通道真实采集架构：
   - 主通道 (CDP Sniffer): 启动静默无头 Chrome/Edge 并屏蔽音视频流，通过 CDP 拦截抖音官方已签名 WebSocket 二进制帧与 IM HTTP 轮询包，零风控掉线；
   - 备选通道 (WS Direct): 携带 ttwid Cookie 直连 Webcast WebSocket，内置标准 Protobuf Ack 回执帧与 Ping 保活；
3. 支持连击礼物合并计算、主播专属热词高亮标注、滑动时间窗口热度统计以及多订阅者 SSE 毫秒级事件广播。
"""

import os
import re
import sys
import gzip
import json
import time
import uuid
import base64
import socket
import shutil
import tempfile
import threading
import subprocess
import queue
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional, Callable, Tuple
import requests
import websocket

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ==============================================================================
# 1. 纯 Python 零依赖 Protobuf Wire 编解码工具
# ==============================================================================

class ProtobufCodec:
    """轻量级通用 Protobuf Wire Type 编解码器（免预编译 .proto）"""

    @staticmethod
    def decode_fields(data: bytes) -> List[Tuple[int, int, Any]]:
        """
        解码二进制流为字段三元组列表: [(field_no, wire_type, value), ...]
        wire_type: 0=varint(int), 1=64bit(bytes), 2=length-delimited(bytes), 5=32bit(bytes)
        """
        fields: List[Tuple[int, int, Any]] = []
        idx = 0
        total_len = len(data)

        while idx < total_len:
            # 读取 Tag
            tag = 0
            shift = 0
            while idx < total_len:
                b = data[idx]
                idx += 1
                tag |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
                if shift > 35:
                    return fields

            field_no = tag >> 3
            wire_type = tag & 0x07
            if field_no <= 0:
                break

            if wire_type == 0:  # Varint
                val = 0
                shift = 0
                while idx < total_len:
                    b = data[idx]
                    idx += 1
                    val |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                    if shift > 70:
                        return fields
                fields.append((field_no, 0, val))

            elif wire_type == 1:  # 64-bit fixed
                if idx + 8 > total_len:
                    break
                fields.append((field_no, 1, data[idx:idx + 8]))
                idx += 8

            elif wire_type == 2:  # Length-delimited (string / bytes / sub-message)
                length = 0
                shift = 0
                while idx < total_len:
                    b = data[idx]
                    idx += 1
                    length |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                    if shift > 35:
                        return fields
                if length < 0 or idx + length > total_len:
                    break
                fields.append((field_no, 2, data[idx:idx + length]))
                idx += length

            elif wire_type == 5:  # 32-bit fixed
                if idx + 4 > total_len:
                    break
                fields.append((field_no, 5, data[idx:idx + 4]))
                idx += 4

            else:
                # 遇到未知 wire_type 立即中止当前层级解析
                break

        return fields

    @staticmethod
    def encode_varint(value: int) -> bytes:
        """编码无符号整数为 Protobuf Varint"""
        out = bytearray()
        value = max(0, int(value))
        while True:
            bits = value & 0x7F
            value >>= 7
            if value:
                out.append(bits | 0x80)
            else:
                out.append(bits)
                break
        return bytes(out)

    @classmethod
    def encode_push_frame_ack(cls, log_id: int, internal_ext: str) -> bytes:
        """
        编码抖音 Webcast PushFrame 的 ACK 回执二进制包
        PushFrame: field 2 = logId (varint), field 7 = payloadType ("ack"), field 8 = payload (internalExt bytes)
        """
        buf = bytearray()
        if log_id > 0:
            # field 2, wire_type 0 -> tag = (2 << 3) | 0 = 16 (0x10)
            buf.append(0x10)
            buf.extend(cls.encode_varint(log_id))

        ack_type = b"ack"
        # field 7, wire_type 2 -> tag = (7 << 3) | 2 = 58 (0x3A)
        buf.append(0x3A)
        buf.extend(cls.encode_varint(len(ack_type)))
        buf.extend(ack_type)

        ext_bytes = (internal_ext or "").encode("utf-8")
        if ext_bytes:
            # field 8, wire_type 2 -> tag = (8 << 3) | 2 = 66 (0x42)
            buf.append(0x42)
            buf.extend(cls.encode_varint(len(ext_bytes)))
            buf.extend(ext_bytes)

        return bytes(buf)


class DouyinWebcastDecoder:
    """抖音直播 Webcast 二进制协议消息解码器"""

    @staticmethod
    def _safe_utf8(raw: bytes) -> str:
        """安全解码 UTF-8 字符串，若含非法控制字符则返回空串"""
        if not raw:
            return ""
        try:
            text = raw.decode("utf-8")
            # 排除明显的二进制子消息误判（允许换行与常见空白，排除不可见控制符）
            for ch in text:
                code = ord(ch)
                if code < 32 and ch not in ("\n", "\r", "\t"):
                    return ""
            return text.strip()
        except UnicodeDecodeError:
            return ""

    @classmethod
    def _extract_image_url(cls, img_bytes: bytes) -> str:
        """从抖音 Image 子消息 (field 1 = repeated urlList) 提取首个 HTTP(S) URL"""
        for fno, wt, val in ProtobufCodec.decode_fields(img_bytes):
            if fno == 1 and wt == 2:
                url = cls._safe_utf8(val)
                if url.startswith("http://") or url.startswith("https://"):
                    return url
        return ""

    @classmethod
    def _extract_user(cls, user_bytes: bytes) -> Dict[str, Any]:
        """
        解析抖音 User 子消息:
        field 1 = id (uint64), field 3 = nickName (string), field 9 = AvatarThumb (Image)
        """
        user_id = 0
        nickname = ""
        avatar = ""
        display_id = ""

        for fno, wt, val in ProtobufCodec.decode_fields(user_bytes):
            if fno == 1 and wt == 0 and not user_id:
                user_id = val
            elif fno == 3 and wt == 2 and not nickname:
                s = cls._safe_utf8(val)
                if s and not s.startswith("http"):
                    nickname = s
            elif fno == 9 and wt == 2 and not avatar:
                avatar = cls._extract_image_url(val)
            elif fno == 38 and wt == 2 and not display_id:
                display_id = cls._safe_utf8(val)

        return {
            "user_id": str(user_id) if user_id else "",
            "nickname": nickname or "-",
            "avatar": avatar
        }

    @classmethod
    def _extract_common_describe(cls, common_bytes: bytes) -> str:
        """从 Common 子消息 (field 8 = describe) 提取描述文案兜底"""
        for fno, wt, val in ProtobufCodec.decode_fields(common_bytes):
            if fno == 8 and wt == 2:
                desc = cls._safe_utf8(val)
                if desc:
                    return desc
        return ""

    @classmethod
    def _extract_gift_struct(cls, gift_bytes: bytes) -> Dict[str, Any]:
        """
        解析抖音 GiftStruct 子消息:
        field 1 = image (Image), field 2 = describe (string), field 5 = id (uint64),
        field 12 = diamondCount (uint32), field 16 = name (string), field 21 = icon (Image)
        """
        gift_name = ""
        describe = ""
        diamond_count = 0
        icon_url = ""
        fallback_icon = ""

        for fno, wt, val in ProtobufCodec.decode_fields(gift_bytes):
            if fno == 1 and wt == 2 and not icon_url:
                icon_url = cls._extract_image_url(val)
            elif fno == 21 and wt == 2 and not fallback_icon:
                fallback_icon = cls._extract_image_url(val)
            elif fno == 2 and wt == 2 and not describe:
                describe = cls._safe_utf8(val)
            elif fno == 12 and wt == 0:
                diamond_count = int(val)
            elif fno == 16 and wt == 2 and not gift_name:
                s = cls._safe_utf8(val)
                if s and not s.startswith("http"):
                    gift_name = s

        if not gift_name and describe:
            # 例如 "送出小心心" / "送出了人气票" -> 提取礼物名
            cleaned = re.sub(r"^送出(了)?\s*", "", describe).strip()
            if cleaned:
                gift_name = cleaned

        return {
            "gift_name": gift_name,
            "describe": describe,
            "diamond_count": diamond_count,
            "gift_icon": icon_url or fallback_icon
        }

    @classmethod
    def decode_push_frame(cls, raw_bytes: bytes) -> Tuple[int, str, bytes]:
        """
        解包外层 PushFrame
        :return: (log_id, payload_type, decompressed_response_bytes)
        """
        log_id = 0
        payload_type = ""
        payload = b""
        is_gzip = False

        for fno, wt, val in ProtobufCodec.decode_fields(raw_bytes):
            if fno == 2 and wt == 0:
                log_id = val
            elif fno == 5 and wt == 2:
                # HeadersList: key=1, value=2
                hk, hv = "", ""
                for hf, hwt, hval in ProtobufCodec.decode_fields(val):
                    if hf == 1 and hwt == 2:
                        hk = cls._safe_utf8(hval)
                    elif hf == 2 and hwt == 2:
                        hv = cls._safe_utf8(hval)
                if hk == "compress_type" and hv == "gzip":
                    is_gzip = True
            elif fno == 7 and wt == 2:
                payload_type = cls._safe_utf8(val)
            elif fno == 8 and wt == 2:
                payload = val

        # 若未匹配 PushFrame 外壳（例如来自 HTTP /webcast/im/fetch 的直接 Response 包）
        target_bytes = payload if payload else raw_bytes
        if is_gzip or target_bytes[:2] == b"\x1f\x8b":
            try:
                target_bytes = gzip.decompress(target_bytes)
            except Exception:
                pass

        return log_id, payload_type or "msg", target_bytes

    @classmethod
    def decode_response(cls, resp_bytes: bytes) -> Dict[str, Any]:
        """
        解包 Response 二进制流，提取内部所有弹幕、礼物及房间指标事件
        :return: {
            "need_ack": bool,
            "internal_ext": str,
            "events": List[Dict[str, Any]]
        }
        """
        need_ack = False
        internal_ext = ""
        events: List[Dict[str, Any]] = []

        for fno, wt, val in ProtobufCodec.decode_fields(resp_bytes):
            if fno == 5 and wt == 2:
                internal_ext = cls._safe_utf8(val)
            elif fno == 9 and wt == 0:
                need_ack = bool(val)
            elif fno == 1 and wt == 2:
                # 单条 Message: field 1 = method, field 2 = payload, field 3 = msgId
                method = ""
                msg_payload = b""
                msg_id = 0
                for mf, mwt, mval in ProtobufCodec.decode_fields(val):
                    if mf == 1 and mwt == 2:
                        method = cls._safe_utf8(mval)
                    elif mf == 2 and mwt == 2:
                        msg_payload = mval
                    elif mf == 3 and mwt == 0:
                        msg_id = mval

                if not method or not msg_payload:
                    continue

                parsed_evt = cls._parse_single_message(method, msg_payload, msg_id)
                if parsed_evt:
                    events.append(parsed_evt)

        return {
            "need_ack": need_ack,
            "internal_ext": internal_ext,
            "events": events
        }

    @classmethod
    def _parse_single_message(cls, method: str, payload: bytes, msg_id: int) -> Optional[Dict[str, Any]]:
        """按消息类型精确解码业务结构"""
        now_ts = time.time()
        time_str = datetime.fromtimestamp(now_ts).strftime("%H:%M:%S")

        # 1. 弹幕聊天消息
        if method == "WebcastChatMessage":
            user_info = {"user_id": "", "nickname": "-", "avatar": ""}
            content = ""
            for fno, wt, val in ProtobufCodec.decode_fields(payload):
                if fno == 2 and wt == 2:
                    user_info = cls._extract_user(val)
                elif fno == 3 and wt == 2 and not content:
                    content = cls._safe_utf8(val)

            if not content:
                return None

            return {
                "type": "chat",
                "msg_id": str(msg_id or uuid.uuid4().hex),
                "timestamp": now_ts,
                "time_str": time_str,
                "user_id": user_info["user_id"],
                "nickname": user_info["nickname"],
                "avatar": user_info["avatar"],
                "content": content
            }

        # 2. 礼物打赏消息
        elif method == "WebcastGiftMessage":
            gift_id = 0
            group_count = 1
            repeat_count = 1
            combo_count = 1
            repeat_end = 0
            group_id = 0
            common_desc = ""
            user_info = {"user_id": "", "nickname": "-", "avatar": ""}
            gift_struct = {"gift_name": "", "describe": "", "diamond_count": 0, "gift_icon": ""}

            for fno, wt, val in ProtobufCodec.decode_fields(payload):
                if fno == 1 and wt == 2:
                    common_desc = cls._extract_common_describe(val)
                elif fno == 2 and wt == 0:
                    gift_id = val
                elif fno == 4 and wt == 0 and val > 0:
                    group_count = int(val)
                elif fno == 5 and wt == 0 and val > 0:
                    repeat_count = int(val)
                elif fno == 6 and wt == 0 and val > 0:
                    combo_count = int(val)
                elif fno == 7 and wt == 2:
                    u_parsed = cls._extract_user(val)
                    if u_parsed["nickname"] != "-" or u_parsed["user_id"]:
                        user_info = u_parsed
                elif fno == 9 and wt == 0:
                    repeat_end = int(val)
                elif fno == 11 and wt == 0:
                    group_id = val
                elif fno == 15 and wt == 2:
                    gift_struct = cls._extract_gift_struct(val)

            gift_name = gift_struct["gift_name"]
            if not gift_name and common_desc:
                # 从类似 "观众名: 送出了 小心心" 或 "送出 粉丝灯牌" 中提取
                m_desc = re.search(r"送出(?:了)?\s*([^\s×xX0-9]+)", common_desc)
                if m_desc:
                    gift_name = m_desc.group(1).strip()

            if not gift_name:
                if gift_id:
                    gift_name = f"礼物#{gift_id}"
                else:
                    return None

            effective_combo = max(combo_count, repeat_count, 1)
            total_count = effective_combo * max(group_count, 1)
            unit_diamond = max(0, gift_struct["diamond_count"])
            total_diamonds = unit_diamond * total_count

            if total_diamonds >= 1000:
                tier = "legend"
            elif total_diamonds >= 99:
                tier = "epic"
            else:
                tier = "normal"

            combo_key = f"{user_info['user_id'] or user_info['nickname']}_{gift_id}_{group_id}"

            return {
                "type": "gift",
                "msg_id": str(msg_id or uuid.uuid4().hex),
                "combo_key": combo_key,
                "timestamp": now_ts,
                "time_str": time_str,
                "user_id": user_info["user_id"],
                "nickname": user_info["nickname"],
                "avatar": user_info["avatar"],
                "gift_id": str(gift_id),
                "gift_name": gift_name,
                "gift_icon": gift_struct["gift_icon"],
                "count": total_count,
                "combo_count": effective_combo,
                "group_count": group_count,
                "unit_diamond": unit_diamond,
                "total_diamonds": total_diamonds,
                "repeat_end": bool(repeat_end),
                "tier": tier
            }

        # 3. 实时在线观众人数消息 (兼容 UserSeq 与 RoomStats 两种事件)
        elif method == "WebcastRoomUserSeqMessage":
            online_count = 0
            total_str = ""
            for fno, wt, val in ProtobufCodec.decode_fields(payload):
                if fno == 3 and wt == 0:
                    online_count = int(val)
                elif fno in (7, 8) and wt == 2 and not total_str:
                    s = cls._safe_utf8(val)
                    if s:
                        total_str = s
            if online_count <= 0 and not total_str:
                return None
            return {
                "type": "room_stats",
                "online_count": online_count,
                "total_user_str": total_str
            }

        elif method == "WebcastRoomStatsMessage":
            online_count = 0
            total_str = ""
            for fno, wt, val in ProtobufCodec.decode_fields(payload):
                if fno == 6 and wt == 0:
                    online_count = int(val)
                elif fno in (2, 3) and wt == 2 and not total_str:
                    s = cls._safe_utf8(val)
                    if s:
                        total_str = s
            if online_count <= 0 and not total_str:
                return None
            return {
                "type": "room_stats",
                "online_count": online_count,
                "total_user_str": total_str
            }

        # 4. 直播间点赞消息
        elif method == "WebcastLikeMessage":
            like_delta = 0
            like_total = 0
            for fno, wt, val in ProtobufCodec.decode_fields(payload):
                if fno == 2 and wt == 0:
                    like_delta = int(val)
                elif fno == 3 and wt == 0:
                    like_total = int(val)
            if like_total <= 0 and like_delta <= 0:
                return None
            return {
                "type": "like_stats",
                "like_delta": like_delta,
                "like_total": like_total
            }

        return None


# ==============================================================================
# 2. 原有滑动窗口弹幕监听器 (保留 100% 向后兼容)
# ==============================================================================

class DanmuMonitor:
    """抖音直播弹幕监听与热度统计器（基础兼容类）"""

    DEFAULT_EMOTION_KEYWORDS = [
        "哈哈", "笑死", "卧槽", "666", "牛逼", "神了", "离谱", "破防",
        "？？", "问号", "太贵了", "退钱", "绝了", "真的假的", "泪目", "翻车",
        "上链接", "小黄车", "牛啊", "太帅了", "封神"
    ]

    def __init__(
        self,
        room_id: str,
        web_rid: str,
        window_size_seconds: int = 10,
        custom_keywords: Optional[List[str]] = None
    ):
        self.room_id = room_id
        self.web_rid = web_rid
        self.window_size = window_size_seconds
        self.keywords = list(set(self.DEFAULT_EMOTION_KEYWORDS + (custom_keywords or [])))

        self.ws: Optional[websocket.WebSocketApp] = None
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

        self.danmu_queue = deque()
        self.lock = threading.Lock()
        self.on_danmu_callbacks: List[Callable[[str, str], None]] = []

    def add_danmu_callback(self, cb: Callable[[str, str], None]):
        """注册收到新弹幕时的回调: cb(username, text)"""
        self.on_danmu_callbacks.append(cb)

    def _on_message(self, ws, message):
        """解析二进制 PushFrame 并回调"""
        if isinstance(message, bytes):
            log_id, p_type, resp_bytes = DouyinWebcastDecoder.decode_push_frame(message)
            decoded = DouyinWebcastDecoder.decode_response(resp_bytes)
            if decoded["need_ack"] and ws:
                try:
                    ack_pkt = ProtobufCodec.encode_push_frame_ack(log_id, decoded["internal_ext"])
                    ws.send(ack_pkt, opcode=websocket.ABNF.OPCODE_BINARY)
                except Exception:
                    pass

            now = time.time()
            with self.lock:
                for evt in decoded["events"]:
                    if evt["type"] == "chat":
                        self.danmu_queue.append((now, evt["content"], evt["nickname"]))
                        for cb in self.on_danmu_callbacks:
                            try:
                                cb(evt["nickname"], evt["content"])
                            except Exception:
                                pass

    def _on_error(self, ws, error):
        print(f"[弹幕监听异常] {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.is_running = False

    def _on_open(self, ws):
        self.is_running = True

        def heartbeat():
            while self.is_running and self.ws:
                try:
                    time.sleep(10)
                    if self.ws and self.ws.sock and self.ws.sock.connected:
                        self.ws.send(b":", websocket.ABNF.OPCODE_PING)
                except Exception:
                    break

        threading.Thread(target=heartbeat, daemon=True).start()

    def start(self):
        """启动后台监听线程"""
        if self.is_running:
            return

        ws_url = (
            f"wss://webcast5-ws-web-lf.douyin.com/webcast/im/push/v2/?"
            f"app_name=douyin_web&version_code=180800&webcast_sdk_version=1.0.14-beta.0"
            f"&update_version_code=1.0.14-beta.0&compress=gzip&device_platform=web"
            f"&cookie_enabled=true&screen_width=1920&screen_height=1080&browser_language=zh-CN"
            f"&browser_platform=Win32&browser_name=Mozilla&browser_version=5.0"
            f"&room_id={self.room_id}&live_id=1&did_rule=3"
        )

        headers = [
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Origin: https://live.douyin.com"
        ]

        self.ws = websocket.WebSocketApp(
            ws_url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        self._thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听"""
        self.is_running = False
        if self.ws:
            self.ws.close()

    def get_window_heat_metrics(self) -> Dict[str, Any]:
        """获取当前滑动时间窗口内的热度指标"""
        now = time.time()
        window_start = now - self.window_size

        with self.lock:
            while self.danmu_queue and self.danmu_queue[0][0] < window_start:
                self.danmu_queue.popleft()
            current_window = list(self.danmu_queue)

        danmu_count = len(current_window)
        density_per_second = round(danmu_count / max(self.window_size, 1), 2)

        hit_keywords: Dict[str, int] = {}
        for _, content, _ in current_window:
            for kw in self.keywords:
                if kw in content:
                    hit_keywords[kw] = hit_keywords.get(kw, 0) + 1

        return {
            "window_sec": self.window_size,
            "danmu_count": danmu_count,
            "density_per_sec": density_per_second,
            "keyword_hits": sum(hit_keywords.values()),
            "top_keywords": sorted(hit_keywords.items(), key=lambda x: x[1], reverse=True)[:5]
        }


# ==============================================================================
# 3. 全局实时弹幕与礼物双通道采集服务 (DouyinLiveDanmuService)
# ==============================================================================

class DouyinLiveDanmuService:
    """
    面向可视化导播台的实时弹幕与礼物中枢服务：
    - 支持会话代际隔离 (session_id)，切台秒切无串流；
    - 优先启用本机无头 Chrome/Edge CDP WebSocket 帧与 IM Fetch 嗅探（屏蔽音视频流量）；
    - 无浏览器环境自动回退携带 ttwid 与 Protobuf Ack 的直连 WebSocket；
    - 支持多前端客户端 SSE 实时事件流订阅。
    """

    def __init__(self):
        from resolver import DouyinLiveResolver
        from anchor_profile import AnchorProfileManager

        self.resolver = DouyinLiveResolver()
        self.profile_mgr = AnchorProfileManager()

        self._lock = threading.RLock()
        self._session_id = 0
        self.is_running = False
        self.connection_state = "idle"  # idle | connecting | connected | error
        self.transport_mode = "-"       # CDP | WS | -
        self.error_message = ""

        self.current_target = ""
        self.web_rid = ""
        self.room_id = ""
        self.anchor_name = "-"
        self.room_title = "-"
        self.started_at = 0.0

        # 实时缓存队列
        self.chats: deque = deque(maxlen=250)
        self.gifts: deque = deque(maxlen=120)
        self._seen_msg_ids: deque = deque(maxlen=2000)
        self._sliding_chat_times: deque = deque(maxlen=1000)

        # 累计统计指标
        self.total_chats = 0
        self.total_gifts = 0
        self.total_diamonds = 0
        self.online_count = 0
        self.total_user_str = "-"
        self.like_total = 0

        # 当前生效的情绪/主播热词集
        self.active_keywords: List[str] = list(DanmuMonitor.DEFAULT_EMOTION_KEYWORDS)

        # 子进程与连接句柄
        self._browser_proc: Optional[subprocess.Popen] = None
        self._browser_user_dir: Optional[str] = None
        self._cdp_ws: Optional[websocket.WebSocket] = None
        self._direct_ws: Optional[websocket.WebSocketApp] = None
        self._worker_thread: Optional[threading.Thread] = None

        # SSE 客户端订阅队列池
        self._subscribers: List[queue.Queue] = []

        # 抖音登录态 Cookie 存储路径（用于解锁 Webcast 完整礼物下发）
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._cookie_file = os.path.join(base_dir, "config", "douyin_cookies.json")
        self._login_proc: Optional[subprocess.Popen] = None
        self._login_in_progress = False
        self._saved_cookies: List[Dict[str, Any]] = self._load_saved_cookies()

    def _load_saved_cookies(self) -> List[Dict[str, Any]]:
        """加载已保存的抖音登录态 Cookie"""
        if os.path.exists(self._cookie_file):
            try:
                with open(self._cookie_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def has_login_cookies(self) -> bool:
        """检查是否具备有效的抖音登录会话 Cookie（如 sessionid / sessionid_ss）"""
        names = {c.get("name", "") for c in self._saved_cookies}
        return bool(names & {"sessionid", "sessionid_ss", "sid_tt", "passport_csrf_token"})

    def save_cookie_string(self, cookie_str: str) -> Dict[str, Any]:
        """支持手动粘贴浏览器 Cookie 字符串保存登录态"""
        items = []
        for part in (cookie_str or "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                k, v = k.strip(), v.strip()
                if k and v:
                    items.append({
                        "name": k,
                        "value": v,
                        "domain": ".douyin.com",
                        "path": "/"
                    })
        if not items:
            raise ValueError("Cookie 格式无效，请粘贴完整的抖音 Cookie 字符串")

        os.makedirs(os.path.dirname(self._cookie_file), exist_ok=True)
        with open(self._cookie_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        with self._lock:
            self._saved_cookies = items

        self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})
        return {"status": "ok", "is_logged_in": self.has_login_cookies(), "count": len(items)}

    def launch_douyin_login(self) -> Dict[str, Any]:
        """弹出可见浏览器窗口引导用户扫码登录抖音，登录成功后自动保存 Cookie 并关闭窗口"""
        if self._login_in_progress:
            return {"status": "already_open", "message": "登录窗口已打开，请在弹出的浏览器中扫码登录抖音"}

        browser_exe = self._find_local_chromium()
        if not browser_exe:
            raise RuntimeError("未检测到本机 Chrome 或 Edge 浏览器，请改用手动粘贴 Cookie 方式")

        port = self._get_free_port()
        user_dir = tempfile.mkdtemp(prefix="live_cutter_login_")
        cmd = [
            browser_exe,
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1100,760",
            "--disable-blink-features=AutomationControlled",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_dir}",
            "https://live.douyin.com/"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._login_proc = proc
        self._login_in_progress = True

        def _watch_login():
            ws_login = None
            try:
                ws_url = None
                for _ in range(30):
                    if proc.poll() is not None:
                        return
                    time.sleep(0.4)
                    try:
                        tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=1.5).json()
                        for tab in tabs:
                            if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                                ws_url = tab["webSocketDebuggerUrl"]
                                break
                        if ws_url:
                            break
                    except Exception:
                        continue
                if not ws_url:
                    return

                ws_login = websocket.create_connection(ws_url, timeout=5)
                ws_login.settimeout(2.0)
                cmd_id = 10
                deadline = time.time() + 180  # 最多等待 3 分钟扫码
                while time.time() < deadline and proc.poll() is None:
                    cmd_id += 1
                    ws_login.send(json.dumps({"id": cmd_id, "method": "Network.getAllCookies"}))
                    try:
                        while True:
                            resp = json.loads(ws_login.recv())
                            if resp.get("id") == cmd_id:
                                all_c = resp.get("result", {}).get("cookies", [])
                                dy_cookies = [
                                    {
                                        "name": c["name"],
                                        "value": c["value"],
                                        "domain": c.get("domain", ".douyin.com"),
                                        "path": c.get("path", "/")
                                    }
                                    for c in all_c
                                    if "douyin.com" in c.get("domain", "")
                                ]
                                names = {c["name"] for c in dy_cookies}
                                if names & {"sessionid", "sessionid_ss", "sid_tt"}:
                                    os.makedirs(os.path.dirname(self._cookie_file), exist_ok=True)
                                    with open(self._cookie_file, "w", encoding="utf-8") as f:
                                        json.dump(dy_cookies, f, ensure_ascii=False, indent=2)
                                    with self._lock:
                                        self._saved_cookies = dy_cookies
                                    print(f"[弹幕引擎] ✅ 已捕获并保存抖音登录态 ({len(dy_cookies)} 条 Cookie)，完整礼物通道已解锁！")
                                    self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})
                                    return
                                break
                    except websocket.WebSocketTimeoutException:
                        pass
                    time.sleep(1.5)
            except Exception as e:
                print(f"[登录监听提示] {e}")
            finally:
                self._login_in_progress = False
                if ws_login:
                    try:
                        ws_login.close()
                    except Exception:
                        pass
                if proc.poll() is None:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass
                time.sleep(0.8)
                shutil.rmtree(user_dir, ignore_errors=True)

        threading.Thread(target=_watch_login, daemon=True).start()
        return {"status": "opened", "message": "已打开抖音登录窗口，请扫码登录，登录成功后将自动保存凭证并关闭窗口"}

    @staticmethod
    def _find_local_chromium() -> Optional[str]:
        """探测本机已安装的 Chrome 或 Edge 浏览器路径"""
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for path in candidates:
            try:
                if path and os.path.exists(path):
                    return path
            except Exception:
                continue
        return None

    @staticmethod
    def _get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    def _detach_resources_unlocked(self):
        """在锁内瞬间摘除旧连接与子进程句柄，避免持锁期间阻塞"""
        handles = (
            self._cdp_ws,
            self._direct_ws,
            self._browser_proc,
            self._browser_user_dir,
        )
        self._cdp_ws = None
        self._direct_ws = None
        self._browser_proc = None
        self._browser_user_dir = None
        return handles

    @staticmethod
    def _dispose_resources_async(handles):
        """后台异步清理旧无头浏览器进程树、WebSocket 与临时目录，绝不阻塞主请求"""
        cdp_ws, direct_ws, proc, udir = handles
        if not any(handles):
            return

        def _worker():
            # 优先强杀旧浏览器进程树，令阻塞中的 cdp_ws.recv() 立即释放
            if proc:
                try:
                    if proc.poll() is None:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=5
                            )
                        else:
                            proc.kill()
                except Exception:
                    pass
            if cdp_ws:
                try:
                    cdp_ws.close()
                except Exception:
                    pass
            if direct_ws:
                try:
                    direct_ws.close()
                except Exception:
                    pass
            if udir:
                time.sleep(0.8)
                shutil.rmtree(udir, ignore_errors=True)

        threading.Thread(target=_worker, daemon=True).start()

    def _cleanup_resources(self):
        """安全终止浏览器进程树、WebSocket 连接与临时缓存目录（非阻塞）"""
        with self._lock:
            handles = self._detach_resources_unlocked()
        self._dispose_resources_async(handles)

    def subscribe(self) -> queue.Queue:
        """注册新的 SSE 客户端事件队列"""
        q: queue.Queue = queue.Queue(maxsize=300)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """移除已断开的 SSE 客户端事件队列"""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast(self, event_payload: Dict[str, Any]):
        """向所有在线 SSE 客户端广播实时事件"""
        with self._lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event_payload)
                except queue.Full:
                    try:
                        q.get_nowait()
                        q.put_nowait(event_payload)
                    except Exception:
                        dead_queues.append(q)
            for dq in dead_queues:
                if dq in self._subscribers:
                    self._subscribers.remove(dq)

    def _reset_metrics_unlocked(self):
        """清空上一场直播间的消息与统计数据"""
        self.chats.clear()
        self.gifts.clear()
        self._seen_msg_ids.clear()
        self._sliding_chat_times.clear()
        self.total_chats = 0
        self.total_gifts = 0
        self.total_diamonds = 0
        self.online_count = 0
        self.total_user_str = "-"
        self.like_total = 0
        self.error_message = ""

    def start(self, target: str, resolved_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """启动或平滑切换指定直播间的实时弹幕与礼物采集"""
        target_clean = str(target).strip()
        if not target_clean:
            raise ValueError("请输入有效的抖音直播间房间号或链接")

        old_handles = (None, None, None, None)
        with self._lock:
            # 幂等保护：若已经在采集同一个房间且处于活跃态，直接返回当前状态
            if (
                self.is_running
                and self.connection_state in ("connecting", "connected")
                and target_clean in (self.current_target, self.web_rid)
            ):
                return self.get_status(include_lists=False)

            self._session_id += 1
            session_id = self._session_id
            self.is_running = False
            old_handles = self._detach_resources_unlocked()

        # 锁外异步销毁旧浏览器进程与连接，零阻塞
        self._dispose_resources_async(old_handles)

        # 优先复用前端已解析好的元数据实现 0ms 瞬切，否则现场解析
        meta = resolved_meta if (resolved_meta and resolved_meta.get("web_rid")) else self.resolver.resolve(target_clean)
        if not meta:
            raise ValueError(f"无法解析直播间 {target_clean}，请确认房间号正确且主播正在开播")
        if not meta.get("is_living"):
            raise ValueError(f"主播【{meta.get('anchor_name', target_clean)}】当前已关播，暂无实时弹幕与礼物")

        # 挂载主播专属热词库
        profile = self.profile_mgr.match_profile(
            target=meta.get("web_rid", target_clean),
            anchor_name=meta.get("anchor_name", "")
        )
        exclusive_kws = profile.get("exclusive_keywords", []) if profile else []

        with self._lock:
            if session_id != self._session_id:
                return {"status": "cancelled"}

            self._reset_metrics_unlocked()
            self.is_running = True
            self.connection_state = "connecting"
            self.transport_mode = "-"
            self.current_target = target_clean
            self.web_rid = str(meta.get("web_rid") or target_clean)
            self.room_id = str(meta.get("room_id") or self.web_rid)
            self.anchor_name = meta.get("anchor_name") or "-"
            self.room_title = meta.get("title") or "-"
            self.started_at = time.time()
            self.active_keywords = list(set(DanmuMonitor.DEFAULT_EMOTION_KEYWORDS + exclusive_kws))

            self._worker_thread = threading.Thread(
                target=self._run_collector_session,
                args=(session_id, self.web_rid, self.room_id),
                daemon=True
            )
            self._worker_thread.start()

        self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})
        return self.get_status(include_lists=False)

    def stop(self) -> Dict[str, Any]:
        """停止实时弹幕与礼物采集并释放所有后台资源"""
        with self._lock:
            self._session_id += 1
            self.is_running = False
            self.connection_state = "idle"
            self.transport_mode = "-"
            self._cleanup_resources()

        status = self.get_status(include_lists=False)
        self._broadcast({"type": "state", "data": status})
        return status

    def clear_history(self) -> Dict[str, Any]:
        """清空当前屏幕缓存的弹幕与礼物记录（保留连接不断开）"""
        with self._lock:
            self.chats.clear()
            self.gifts.clear()
        self._broadcast({"type": "cleared"})
        return {"status": "ok"}

    def _run_collector_session(self, session_id: int, web_rid: str, room_id: str):
        """采集工作主线程：优先执行 CDP 嗅探，异常或无浏览器时自动回退直连 WS"""
        browser_exe = self._find_local_chromium()
        if browser_exe:
            ok = self._run_cdp_sniffer(session_id, browser_exe, web_rid)
            if ok or not self.is_running or session_id != self._session_id:
                return
            print("[弹幕引擎] CDP 嗅探通道未能建立，正在自动切换至 WebSocket 直连备选通道...")

        if self.is_running and session_id == self._session_id:
            self._run_direct_ws(session_id, web_rid, room_id)

    def _run_cdp_sniffer(self, session_id: int, browser_exe: str, web_rid: str) -> bool:
        """使用无头浏览器 CDP 拦截抖音官方 WebSocket 二进制帧与 IM Fetch 响应"""
        port = self._get_free_port()
        user_dir = tempfile.mkdtemp(prefix="live_cutter_danmu_")
        live_url = f"https://live.douyin.com/{web_rid}"
        chrome_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

        # 关键：先以 about:blank 启动无头浏览器并显式伪装标准桌面 UA，
        # 待 CDP 挂载完 Network.enable 与反检测脚本后再导航至直播间，彻底避免竞态丢包
        cmd = [
            browser_exe,
            "--headless=new",
            "--mute-audio",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--window-size=1280,800",
            f"--user-agent={chrome_ua}",
            "--disable-blink-features=AutomationControlled",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_dir}",
            "about:blank"
        ]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            shutil.rmtree(user_dir, ignore_errors=True)
            print(f"[弹幕引擎] 启动无头浏览器失败: {e}")
            return False

        with self._lock:
            if not self.is_running or session_id != self._session_id:
                try:
                    proc.kill()
                except Exception:
                    pass
                shutil.rmtree(user_dir, ignore_errors=True)
                return False
            self._browser_proc = proc
            self._browser_user_dir = user_dir
            self.transport_mode = "CDP"

        # 等待 CDP 调试端口就绪
        ws_debugger_url = None
        for _ in range(30):
            if not self.is_running or session_id != self._session_id:
                return False
            time.sleep(0.4)
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/json", timeout=1.5)
                tabs = resp.json()
                for tab in tabs:
                    if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                        ws_debugger_url = tab["webSocketDebuggerUrl"]
                        break
                if ws_debugger_url:
                    break
            except Exception:
                continue

        if not ws_debugger_url:
            self._cleanup_resources()
            return False

        try:
            cdp_ws = websocket.create_connection(ws_debugger_url, timeout=5)
            with self._lock:
                if not self.is_running or session_id != self._session_id:
                    cdp_ws.close()
                    return False
                self._cdp_ws = cdp_ws

            # 启用 Network 监控并屏蔽音视频大流量流文件，仅保留网页信令与弹幕礼物通道
            cdp_ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
            cdp_ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
            cdp_ws.send(json.dumps({
                "id": 3,
                "method": "Page.addScriptToEvaluateOnNewDocument",
                "params": {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"}
            }))
            cdp_ws.send(json.dumps({
                "id": 4,
                "method": "Network.setBlockedURLs",
                "params": {
                    "urls": [
                        "*.flv*", "*.m3u8*", "*.ts*", "*.mp4*",
                        "*pull-flv*", "*pull-hls*", "*pull-cmaf*"
                    ]
                }
            }))
            # 若已保存抖音登录态 Cookie，则在导航前注入以解锁服务端完整礼物消息 (WebcastGiftMessage)
            if self._saved_cookies:
                cdp_cookies = []
                for ck in self._saved_cookies:
                    if ck.get("name") and ck.get("value"):
                        cdp_cookies.append({
                            "name": ck["name"],
                            "value": ck["value"],
                            "domain": ck.get("domain", ".douyin.com"),
                            "path": ck.get("path", "/"),
                            "url": "https://live.douyin.com"
                        })
                if cdp_cookies:
                    cdp_ws.send(json.dumps({
                        "id": 45,
                        "method": "Network.setCookies",
                        "params": {"cookies": cdp_cookies}
                    }))
            # 全部拦截钩子就绪后再导航至目标直播间，确保捕获首个 IM Fetch 与 WebSocket 握手
            cdp_ws.send(json.dumps({
                "id": 5,
                "method": "Page.navigate",
                "params": {"url": live_url}
            }))

            cdp_ws.settimeout(1.0)
            cmd_seq = 100
            im_fetch_requests: Dict[str, bool] = {}
            body_cmd_map: Dict[int, str] = {}
            connected_marked = False

            print(f"[弹幕引擎] CDP 嗅探通道已挂载直播间 {web_rid}，正在监听 Webcast 数据帧...")

            while self.is_running and session_id == self._session_id:
                if proc.poll() is not None:
                    break
                try:
                    raw_msg = cdp_ws.recv()
                    if not raw_msg:
                        continue
                    evt = json.loads(raw_msg)
                    method = evt.get("method", "")

                    # 1. WebSocket 握手创建通知
                    if method == "Network.webSocketCreated":
                        ws_url = evt.get("params", {}).get("url", "")
                        if "webcast" in ws_url or "/im/push" in ws_url:
                            if not connected_marked:
                                connected_marked = True
                                self._mark_connected(session_id, "CDP")

                    # 2. 捕获抖音 Webcast 二进制帧 (PushFrame)
                    elif method == "Network.webSocketFrameReceived":
                        frame = evt.get("params", {}).get("response", {})
                        if frame.get("opcode") == 2 and frame.get("payloadData"):
                            if not connected_marked:
                                connected_marked = True
                                self._mark_connected(session_id, "CDP")
                            raw_frame = base64.b64decode(frame["payloadData"])
                            _, _, resp_bytes = DouyinWebcastDecoder.decode_push_frame(raw_frame)
                            self._ingest_response_bytes(session_id, resp_bytes)

                    # 3. 兼容 HTTP /webcast/im/fetch/ 轮询降级包
                    elif method == "Network.responseReceived":
                        resp_url = evt.get("params", {}).get("response", {}).get("url", "")
                        req_id = evt.get("params", {}).get("requestId", "")
                        if req_id and "/webcast/im/fetch" in resp_url:
                            im_fetch_requests[req_id] = True
                            if not connected_marked:
                                connected_marked = True
                                self._mark_connected(session_id, "CDP")

                    elif method == "Network.loadingFinished":
                        req_id = evt.get("params", {}).get("requestId", "")
                        if req_id in im_fetch_requests:
                            im_fetch_requests.pop(req_id, None)
                            cmd_seq += 1
                            body_cmd_map[cmd_seq] = req_id
                            cdp_ws.send(json.dumps({
                                "id": cmd_seq,
                                "method": "Network.getResponseBody",
                                "params": {"requestId": req_id}
                            }))

                    elif "id" in evt and evt["id"] in body_cmd_map:
                        body_cmd_map.pop(evt["id"], None)
                        res_obj = evt.get("result", {})
                        body_str = res_obj.get("body", "")
                        if body_str:
                            raw_body = (
                                base64.b64decode(body_str)
                                if res_obj.get("base64Encoded")
                                else body_str.encode("latin1", errors="ignore")
                            )
                            if raw_body[:2] == b"\x1f\x8b":
                                try:
                                    raw_body = gzip.decompress(raw_body)
                                except Exception:
                                    pass
                            self._ingest_response_bytes(session_id, raw_body)

                except websocket.WebSocketTimeoutException:
                    continue
                except Exception as loop_err:
                    if not self.is_running or session_id != self._session_id:
                        break
                    print(f"[弹幕引擎] CDP 帧读取异常: {loop_err}")
                    break

            return connected_marked

        except Exception as e:
            print(f"[弹幕引擎] CDP 连接异常: {e}")
            return False
        finally:
            if session_id == self._session_id and not self.is_running:
                self._cleanup_resources()

    def _run_direct_ws(self, session_id: int, web_rid: str, room_id: str):
        """备选通道：携带 ttwid Cookie 与 Protobuf Ack 直连抖音 Webcast WebSocket"""
        self.resolver._ensure_ttwid()
        cookie_pairs = [f"{k}={v}" for k, v in self.resolver.session.cookies.get_dict().items()]
        cookie_header = "; ".join(cookie_pairs)

        ws_url = (
            f"wss://webcast5-ws-web-lf.douyin.com/webcast/im/push/v2/?"
            f"app_name=douyin_web&version_code=180800&webcast_sdk_version=1.0.14-beta.0"
            f"&update_version_code=1.0.14-beta.0&compress=gzip&device_platform=web"
            f"&cookie_enabled=true&screen_width=1920&screen_height=1080&browser_language=zh-CN"
            f"&browser_platform=Win32&browser_name=Mozilla&browser_version=5.0"
            f"&room_id={room_id}&live_id=1&did_rule=3&identity=audience"
        )

        headers = [
            f"User-Agent: {self.resolver.headers['User-Agent']}",
            "Origin: https://live.douyin.com"
        ]
        if cookie_header:
            headers.append(f"Cookie: {cookie_header}")

        def on_open(ws):
            if not self.is_running or session_id != self._session_id:
                ws.close()
                return
            self._mark_connected(session_id, "WS")

            def ping_loop():
                while self.is_running and session_id == self._session_id:
                    time.sleep(10)
                    try:
                        if ws.sock and ws.sock.connected:
                            ws.send(b"hb", websocket.ABNF.OPCODE_PING)
                    except Exception:
                        break

            threading.Thread(target=ping_loop, daemon=True).start()

        def on_message(ws, message):
            if not self.is_running or session_id != self._session_id:
                ws.close()
                return
            if isinstance(message, bytes):
                log_id, _, resp_bytes = DouyinWebcastDecoder.decode_push_frame(message)
                decoded = self._ingest_response_bytes(session_id, resp_bytes)
                if decoded and decoded.get("need_ack"):
                    try:
                        ack_bytes = ProtobufCodec.encode_push_frame_ack(log_id, decoded.get("internal_ext", ""))
                        ws.send(ack_bytes, opcode=websocket.ABNF.OPCODE_BINARY)
                    except Exception:
                        pass

        def on_error(ws, error):
            if session_id == self._session_id and self.is_running:
                with self._lock:
                    self.connection_state = "error"
                    self.error_message = f"弹幕通道连接受限: {error}"
                self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})

        def on_close(ws, code, msg):
            if session_id == self._session_id and self.is_running:
                with self._lock:
                    if self.connection_state != "error":
                        self.connection_state = "idle"
                        self.is_running = False
                self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})

        ws_app = websocket.WebSocketApp(
            ws_url,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        with self._lock:
            if not self.is_running or session_id != self._session_id:
                return
            self._direct_ws = ws_app
            self.transport_mode = "WS"

        ws_app.run_forever()

    def _mark_connected(self, session_id: int, mode: str):
        with self._lock:
            if session_id != self._session_id or not self.is_running:
                return
            self.connection_state = "connected"
            self.transport_mode = mode
            self.error_message = ""
        print(f"[弹幕引擎] ✅ 已成功连通主播【{self.anchor_name}】({self.web_rid}) 实时弹幕与礼物流 (通道: {mode})")
        self._broadcast({"type": "state", "data": self.get_status(include_lists=False)})

    def _ingest_response_bytes(self, session_id: int, resp_bytes: bytes) -> Optional[Dict[str, Any]]:
        """处理解码后的 Response 事件列表，完成去重、热词标注、连击合并与实时推送"""
        if not resp_bytes or not self.is_running or session_id != self._session_id:
            return None

        decoded = DouyinWebcastDecoder.decode_response(resp_bytes)
        events = decoded.get("events", [])
        if not events:
            return decoded

        stats_dirty = False

        for evt in events:
            if not self.is_running or session_id != self._session_id:
                break

            evt_type = evt.get("type")

            # 1. 处理弹幕消息
            if evt_type == "chat":
                msg_id = evt["msg_id"]
                with self._lock:
                    if msg_id in self._seen_msg_ids:
                        continue
                    self._seen_msg_ids.append(msg_id)

                    content = evt["content"]
                    matched_kws = [kw for kw in self.active_keywords if kw in content]
                    evt["is_hot"] = len(matched_kws) > 0
                    evt["hit_keywords"] = matched_kws[:2]

                    self.chats.append(evt)
                    self.total_chats += 1
                    self._sliding_chat_times.append(evt["timestamp"])

                self._broadcast({"type": "chat", "data": evt})
                stats_dirty = True

            # 2. 处理礼物消息（含同组连击智能合并与差额钻石累加）
            elif evt_type == "gift":
                msg_id = evt["msg_id"]
                combo_key = evt["combo_key"]
                updated_existing = False

                with self._lock:
                    if msg_id in self._seen_msg_ids:
                        continue
                    self._seen_msg_ids.append(msg_id)

                    # 查找最近 20 条礼物中是否存在同一用户同一组连击
                    prev_diamonds = 0
                    for idx in range(len(self.gifts) - 1, max(-1, len(self.gifts) - 20), -1):
                        prev_g = self.gifts[idx]
                        if (
                            prev_g.get("combo_key") == combo_key
                            and evt["timestamp"] - prev_g.get("timestamp", 0) <= 15.0
                        ):
                            if evt["count"] >= prev_g["count"]:
                                prev_diamonds = prev_g.get("total_diamonds", 0)
                                prev_g.update(evt)
                                evt = dict(prev_g)
                                updated_existing = True
                            break

                    if not updated_existing:
                        self.gifts.append(evt)
                        self.total_gifts += 1
                        self.total_diamonds += evt.get("total_diamonds", 0)
                    else:
                        delta_d = max(0, evt.get("total_diamonds", 0) - prev_diamonds)
                        self.total_diamonds += delta_d

                self._broadcast({
                    "type": "gift",
                    "is_combo_update": updated_existing,
                    "data": evt
                })
                stats_dirty = True

            # 3. 处理直播间在线人数更新
            elif evt_type == "room_stats":
                with self._lock:
                    if evt.get("online_count", 0) > 0:
                        self.online_count = evt["online_count"]
                    if evt.get("total_user_str"):
                        self.total_user_str = evt["total_user_str"]
                stats_dirty = True

            # 4. 处理点赞数更新
            elif evt_type == "like_stats":
                with self._lock:
                    if evt.get("like_total", 0) > self.like_total:
                        self.like_total = evt["like_total"]
                    elif evt.get("like_delta", 0) > 0:
                        self.like_total += evt["like_delta"]
                stats_dirty = True

        if stats_dirty:
            self._broadcast({"type": "metrics", "data": self._get_metrics_snapshot()})

        return decoded

    def _get_metrics_snapshot(self) -> Dict[str, Any]:
        """计算实时统计快照（含最近 10 秒弹幕速率）"""
        now = time.time()
        cutoff = now - 10.0
        with self._lock:
            while self._sliding_chat_times and self._sliding_chat_times[0] < cutoff:
                self._sliding_chat_times.popleft()
            recent_10s_count = len(self._sliding_chat_times)

            return {
                "total_chats": self.total_chats,
                "chats_per_10s": recent_10s_count,
                "total_gifts": self.total_gifts,
                "total_diamonds": self.total_diamonds,
                "online_count": self.online_count,
                "total_user_str": self.total_user_str,
                "like_total": self.like_total
            }

    def get_window_heat_metrics(self, window_sec: int = 15) -> Dict[str, Any]:
        """供 realtime_monitor 调用：获取最近 N 秒内的弹幕与礼物爆发特征以辅助高能切片"""
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            recent_chats = [c for c in self.chats if c.get("timestamp", 0) >= cutoff]
            recent_gifts = [g for g in self.gifts if g.get("timestamp", 0) >= cutoff]

        hot_words: List[str] = []
        for c in recent_chats:
            for kw in c.get("hit_keywords", []):
                if kw not in hot_words:
                    hot_words.append(kw)

        window_diamonds = sum(g.get("total_diamonds", 0) for g in recent_gifts)
        top_gift_desc = ""
        if recent_gifts:
            best_g = max(recent_gifts, key=lambda x: x.get("total_diamonds", 0))
            top_gift_desc = f"{best_g['nickname']} 送出 {best_g['gift_name']} x{best_g['count']}"

        return {
            "is_active": self.is_running and self.connection_state == "connected",
            "danmu_count": len(recent_chats),
            "density_per_sec": round(len(recent_chats) / max(window_sec, 1), 2),
            "hot_keywords": hot_words[:4],
            "gift_count": len(recent_gifts),
            "window_diamonds": window_diamonds,
            "top_gift_desc": top_gift_desc
        }

    def get_status(self, include_lists: bool = True) -> Dict[str, Any]:
        """获取当前完整的弹幕/礼物监听状态与消息快照"""
        metrics = self._get_metrics_snapshot()
        with self._lock:
            elapsed = int(time.time() - self.started_at) if self.is_running and self.started_at else 0
            res: Dict[str, Any] = {
                "is_running": self.is_running,
                "connection_state": self.connection_state,
                "transport_mode": self.transport_mode,
                "is_logged_in": self.has_login_cookies(),
                "error_message": self.error_message,
                "target": self.current_target,
                "web_rid": self.web_rid,
                "room_id": self.room_id,
                "anchor_name": self.anchor_name,
                "room_title": self.room_title,
                "elapsed_seconds": elapsed,
                "metrics": metrics
            }
            if include_lists:
                res["chats"] = list(self.chats)
                res["gifts"] = list(self.gifts)
            return res


# 全局单例服务
danmu_service = DouyinLiveDanmuService()
