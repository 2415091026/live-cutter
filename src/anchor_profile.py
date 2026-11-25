# -*- coding: utf-8 -*-
"""
主播专属性格档案系统 (Anchor Persona Profile)
支持为不同主播定制专属黑话字典、专属剪辑构图模版、触发灵敏度与专属大模型提示词
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class AnchorProfileManager:
    """主播档案管理器"""

    def __init__(self, profiles_dir: Optional[str] = None):
        if profiles_dir is None:
            self.profiles_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "config", "anchors")
            )
        else:
            self.profiles_dir = os.path.abspath(profiles_dir)
        os.makedirs(self.profiles_dir, exist_ok=True)
        self._init_default_profiles()

    def _init_default_profiles(self):
        """初始化默认的主播预设档案"""
        defaults = [
            {
                "anchor_id": "dongfang_zhenxuan",
                "anchor_name": "东方甄选",
                "web_rid": "80017709309",
                "category": "电商知识/助农文化",
                "layout_template": "vertical_9_16", # 9:16竖屏
                "exclusive_keywords": ["董宇辉", "俞敏洪", "小黄车", "上链接", "太划算了", "绝了", "下单"],
                "heat_sensitivity": 0.75, # 灵敏度 0~1
                "persona_prompt": "该主播以知识讲解、文化金句和助农带货为核心看点。重点提炼主播输出的文化哲学短句、幽默自嘲、以及商品破价上车的激烈时刻。"
            },
            {
                "anchor_id": "game_master",
                "anchor_name": "竞技游戏主播 (通用模版)",
                "web_rid": "",
                "category": "电竞/游戏爆笑",
                "layout_template": "split_screen_game", # 上下分屏
                "exclusive_keywords": ["破防", "下饭", "退钱", "666", "卧槽", "神操作", "单杀", "翻车"],
                "heat_sensitivity": 0.85,
                "persona_prompt": "该主播以极限操作、被反杀破防、吹牛被打脸为主要笑点。重点在主播大声咆哮、自夸后光速翻车的剧情转折处进行切片。"
            }
        ]

        for p in defaults:
            p_file = os.path.join(self.profiles_dir, f"{p['anchor_id']}.json")
            if not os.path.exists(p_file):
                with open(p_file, "w", encoding="utf-8") as f:
                    json.dump(p, f, ensure_ascii=False, indent=2)

    def list_profiles(self) -> List[Dict[str, Any]]:
        """获取所有主播档案列表"""
        profiles = []
        for f in os.listdir(self.profiles_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.profiles_dir, f), "r", encoding="utf-8") as fp:
                        profiles.append(json.load(fp))
                except Exception:
                    pass
        return profiles

    def get_profile(self, anchor_id: str) -> Optional[Dict[str, Any]]:
        """获取单个主播档案"""
        p_file = os.path.join(self.profiles_dir, f"{anchor_id}.json")
        if os.path.exists(p_file):
            try:
                with open(p_file, "r", encoding="utf-8") as fp:
                    return json.load(fp)
            except Exception:
                pass
        return None

    def save_profile(self, profile_data: Dict[str, Any]) -> bool:
        """新增或更新主播档案"""
        anchor_id = profile_data.get("anchor_id")
        if not anchor_id:
            return False
        p_file = os.path.join(self.profiles_dir, f"{anchor_id}.json")
        try:
            with open(p_file, "w", encoding="utf-8") as fp:
                json.dump(profile_data, fp, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def match_profile(self, target: str = "", anchor_name: str = "") -> Optional[Dict[str, Any]]:
        """根据目标房间号或主播昵称模糊/精确匹配对应的主播专属档案与切片词库"""
        profiles = self.list_profiles()
        target_clean = str(target).strip()
        name_clean = str(anchor_name).strip()

        # 1. 优先根据 web_rid 房间号匹配
        if target_clean:
            for p in profiles:
                if p.get("web_rid") and str(p.get("web_rid")).strip() == target_clean:
                    return p

        # 2. 根据主播名称模糊匹配 (如 陈伯 匹配 陈伯(全能王))
        if name_clean and name_clean != "-":
            for p in profiles:
                p_name = p.get("anchor_name", "")
                if p_name and (p_name in name_clean or name_clean in p_name):
                    return p

        return None
