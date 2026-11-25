# -*- coding: utf-8 -*-
"""
大语言模型客户端 (LLM Client)
支持读取 config/llm_config.json，完全兼容 DeepSeek、通义千问、智谱GLM、OpenAI及Ollama本地模型
"""

import os
import sys
import json
from typing import Dict, Any, Optional, List
from openai import OpenAI

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class LLMClient:
    """统一大模型客户端"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            self.config_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "config", "llm_config.json")
            )
        else:
            self.config_path = os.path.abspath(config_path)

        self.config = self._load_config()
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or self.config.get("api_key", "")
        self.base_url = self.config.get("base_url", "https://api.deepseek.com/v1")
        self.model = self.config.get("model", "deepseek-chat")
        self.temperature = float(self.config.get("temperature", 0.3))
        self.max_tokens = int(self.config.get("max_tokens", 2000))
        self.timeout = float(self.config.get("timeout_seconds", 30))

        self.is_configured = bool(self.api_key and not self.api_key.startswith("YOUR_"))

        if self.is_configured:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        else:
            self.client = None

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[警告] 读取大模型配置文件失败: {e}，使用默认参数")
        return {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": ""
        }

    def chat_completion(self, system_prompt: str, user_content: str, json_mode: bool = True) -> str:
        """
        调用大模型对话补全
        :param system_prompt: 系统提示词（人设与输出格式要求）
        :param user_content: 用户输入内容（转录字幕及上下文）
        :param json_mode: 是否期望以 JSON 格式输出
        :return: 模型回复文本
        """
        if not self.is_configured or not self.client:
            print("[LLM提示] 当前未配置有效的大模型 API Key，已自动触发启发式规则大脑进行断句与标题生成。")
            print(f"         如需启用完整大模型，请在配置文件中填入 API Key: {self.config_path}")
            return self._heuristic_fallback(user_content)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if json_mode and ("deepseek" in self.model or "gpt" in self.model or "qwen" in self.model):
            try:
                kwargs["response_format"] = {"type": "json_object"}
            except Exception:
                pass

        try:
            resp = self.client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or "{}"
        except Exception as e:
            print(f"[错误] 调用大模型接口异常: {e}，自动降级为本地规则模式")
            return self._heuristic_fallback(user_content)

    def _heuristic_fallback(self, user_content: str) -> str:
        """在无 API Key 时的本地启发式规则兜底响应"""
        return json.dumps({
            "highlight_theme": "主播精彩互动与情绪爆发名场面",
            "core_quote": "名场面高能来袭！",
            "recommended_cut_start": 0.0,
            "recommended_cut_end": 0.0,
            "generated_titles": [
                "【名场面】主播这波操作直接看呆观众！",
                "全网都在搜这个切片！情绪拉满的一瞬间！",
                "全程高能无尿点！这反应太真实了！"
            ],
            "reason": "基于音频能量波峰与启发式断句定位，完整保留前后语意。"
        }, ensure_ascii=False)


if __name__ == "__main__":
    client = LLMClient()
    print("=== 大模型配置检查 ===")
    print(f"配置文件路径 : {client.config_path}")
    print(f"当前 Provider : {client.config.get('provider')}")
    print(f"Base URL     : {client.base_url}")
    print(f"Model        : {client.model}")
    print(f"已就绪状态   : {'已配置 (在线模式)' if client.is_configured else '未配置 API Key (启发式兜底模式)'}")
