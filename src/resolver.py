# -*- coding: utf-8 -*-
"""
抖音直播流解析器 (Douyin Live Stream Resolver)
支持通过房间号、PC直播间网址、移动端分享短链解析原画 FLV / HLS 流地址
"""

import json
import re
import urllib.parse
from typing import Dict, Any, Optional
import requests


class DouyinLiveResolver:
    """抖音直播流解析核心类"""

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://live.douyin.com/",
        }
        self.session.headers.update(self.headers)
        self._ensure_ttwid()

    def _ensure_ttwid(self) -> None:
        """确保会话中具有合法的 ttwid 凭证"""
        if "ttwid" in self.session.cookies:
            return
        try:
            self.session.get("https://live.douyin.com/", timeout=10)
        except Exception as e:
            print(f"[警告] 初始化直播主站 ttwid 失败: {e}")

    @staticmethod
    def extract_web_rid(target: str) -> str:
        """从输入内容（纯数字ID、PC端链接、移动端短链）中提取 web_rid"""
        target = target.strip()
        if target.isdigit():
            return target

        # 匹配 PC 端 live.douyin.com/{web_rid}
        m = re.search(r"live\.douyin\.com/(\d+)", target)
        if m:
            return m.group(1)

        # 匹配移动端分享短链 v.douyin.com/xxxx/
        if "v.douyin.com" in target:
            try:
                resp = requests.get(target, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=10)
                final_url = resp.url
                m_pc = re.search(r"live\.douyin\.com/(\d+)", final_url)
                if m_pc:
                    return m_pc.group(1)
                m_room = re.search(r"room_id=(\d+)", final_url)
                if m_room:
                    return m_room.group(1)
            except Exception as e:
                print(f"[警告] 移动端短链重定向失败: {e}")

        return target

    def resolve(self, target: str) -> Optional[Dict[str, Any]]:
        """
        解析直播间推流信息
        :param target: 房间号或直播间 URL
        :return: 包含标题、主播、状态及高清 FLV/HLS 地址的元数据字典
        """
        web_rid = self.extract_web_rid(target)
        if not web_rid:
            raise ValueError(f"无法识别有效的抖音直播房间号: {target}")

        self._ensure_ttwid()
        page_url = f"https://live.douyin.com/{web_rid}"
        
        try:
            resp = self.session.get(page_url, timeout=12)
            html_text = resp.text
        except Exception as e:
            print(f"[错误] 请求直播间页面超时或失败: {e}")
            return None

        # 1. 提取 FLV 和 HLS 推流字典
        flv_match = re.search(r'\\"flv_pull_url\\":(\{.*?\})', html_text)
        hls_match = re.search(r'\\"hls_pull_url_map\\":(\{.*?\})', html_text)

        flv_urls: Dict[str, str] = {}
        if flv_match:
            try:
                raw_flv = flv_match.group(1).replace(r'\"', '"').replace(r'\\', '\\').replace(r'\u0026', '&')
                flv_urls = json.loads(raw_flv)
            except Exception:
                pass

        hls_urls: Dict[str, str] = {}
        if hls_match:
            try:
                raw_hls = hls_match.group(1).replace(r'\"', '"').replace(r'\\', '\\').replace(r'\u0026', '&')
                hls_urls = json.loads(raw_hls)
            except Exception:
                pass

        if not flv_urls and not hls_urls:
            print(f"[提示] 未能从直播间 {web_rid} 提取到有效流地址（主播可能未开播）")
            return None

        # 2. 提取直播间状态与标题
        status_match = re.search(r'\\"status\\":([0-9]+)', html_text)
        status = int(status_match.group(1)) if status_match else 0
        
        def safe_unescape(text: str) -> str:
            """安全还原 JSON 中的 unicode 与特殊字符"""
            if not text:
                return "-"
            try:
                # 优先使用 json.loads 规范反序列化
                return json.loads(f'"{text}"')
            except Exception:
                try:
                    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
                except Exception:
                    return text

        # 优先在 room / roomInfo 节点内精确匹配直播间真实标题，避免误匹配网页顶部导航菜单（如"广告投放"）
        nav_noise_titles = {"广告投放", "抖音直播", "直播伴侣", "客户端", "充值", "合作"}
        title_match = (
            re.search(r'\\"room\\":\{.{0,1200}?\\"title\\":\\"(.*?)\\"', html_text)
            or re.search(r'\\"roomInfo\\":\{.{0,1500}?\\"title\\":\\"(.*?)\\"', html_text)
            or re.search(r'\\"id_str\\":\\"[0-9]{15,}\\".{0,600}?\\"title\\":\\"(.*?)\\"', html_text)
        )
        raw_title = title_match.group(1) if title_match else ""
        title = safe_unescape(raw_title) if raw_title else ""

        if not title or title in nav_noise_titles:
            # 兜底遍历所有 title 字段，跳过导航菜单杂项
            for m_t in re.finditer(r'\\"title\\":\\"(.*?)\\"', html_text):
                cand_t = safe_unescape(m_t.group(1))
                if cand_t and cand_t not in nav_noise_titles and len(cand_t) >= 2:
                    title = cand_t
                    break
        if not title:
            title = f"直播间_{web_rid}"

        # 提取主播昵称
        nickname_match = (
            re.search(r'\\"anchor\\":\{.*?\\"nickname\\":\\"(.*?)\\"', html_text)
            or re.search(r'\\"nickname\\":\\"(.*?)\\"', html_text)
        )
        raw_nickname = nickname_match.group(1) if nickname_match else "-"
        anchor_name = safe_unescape(raw_nickname)

        # 提取真实 roomId
        room_id_match = (
            re.search(r'\\"roomId\\":\\"([0-9]+)\\"', html_text)
            or re.search(r'\\"room_id\\":\\"([0-9]+)\\"', html_text)
            or re.search(r'\\"id_str\\":\\"([0-9]{15,})\\"', html_text)
        )
        room_id = room_id_match.group(1) if room_id_match else web_rid

        # 3. 筛选最优画质
        best_flv = (
            flv_urls.get("FULL_HD1")
            or flv_urls.get("HD1")
            or flv_urls.get("SD1")
            or (list(flv_urls.values())[-1] if flv_urls else None)
        )
        best_hls = (
            hls_urls.get("FULL_HD1")
            or hls_urls.get("HD1")
            or (list(hls_urls.values())[-1] if hls_urls else None)
        )

        return {
            "web_rid": web_rid,
            "room_id": room_id,
            "title": title,
            "anchor_name": anchor_name,
            "status": status,
            "is_living": (status == 2),
            "status_text": "正在直播" if status == 2 else "已关播",
            "best_flv": best_flv,
            "best_hls": best_hls,
            "flv_urls": flv_urls,
            "hls_urls": hls_urls
        }
