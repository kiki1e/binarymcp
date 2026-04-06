"""
Model Router — AI 模型智能路由

根据可用的 API Key 自动识别可调用的模型，
并根据赛题分析任务类型智能选择最优模型。
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.model_router.providers import (
    PROVIDER_ADAPTERS,
    BaseProviderAdapter,
    get_adapter,
)

logger = logging.getLogger(__name__)


class ModelRouter:
    """AI 模型智能选择 + 统一调用接口"""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=60)

    async def close(self):
        await self._client.aclose()

    # ─────────────────────────────────────
    # 模型发现: 通过 Key 获取可用模型列表
    # ─────────────────────────────────────

    async def list_models_for_key(self, provider: str, api_key: str, base_url: str = "") -> list[dict]:
        """查询某个 Key 可用的模型列表"""
        adapter = get_adapter(provider)
        if not adapter:
            return []
        try:
            return await adapter.list_models(self._client, api_key, base_url)
        except Exception as e:
            logger.warning("获取模型列表失败 [%s]: %s", provider, e)
            return []

    # ─────────────────────────────────────
    # 模型选择: 根据任务类型推荐模型
    # ─────────────────────────────────────

    # 任务类型 → 推荐模型 (按优先级)
    MODEL_PREFERENCES = {
        "deep_reverse": [
            ("anthropic", "claude-opus-4-20250514"),
            ("openai", "o1-preview"),
            ("deepseek", "deepseek-reasoner"),
            ("openai", "gpt-4o"),
            ("anthropic", "claude-sonnet-4-20250514"),
        ],
        "vuln_identify": [
            ("anthropic", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o"),
            ("deepseek", "deepseek-chat"),
            ("kimi", "moonshot-v1-auto"),
        ],
        "rop_chain": [
            ("deepseek", "deepseek-reasoner"),
            ("anthropic", "claude-opus-4-20250514"),
            ("openai", "o1-preview"),
        ],
        "exploit_gen": [
            ("anthropic", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o"),
            ("deepseek", "deepseek-chat"),
        ],
        "crypto_solve": [
            ("deepseek", "deepseek-reasoner"),
            ("anthropic", "claude-opus-4-20250514"),
            ("openai", "o1-preview"),
        ],
        "quick_classify": [
            ("groq", "llama-3.3-70b-versatile"),
            ("cerebras", "llama3.1-70b"),
            ("xai", "grok-2"),
            ("openai", "gpt-4o-mini"),
        ],
        "iot_firmware": [
            ("anthropic", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o"),
            ("deepseek", "deepseek-chat"),
        ],
        "general": [
            ("anthropic", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o"),
            ("deepseek", "deepseek-chat"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
    }

    async def select_model(
        self,
        task_type: str,
        available_keys: list[dict],
    ) -> Optional[dict]:
        """
        根据任务类型和可用 Key, 选择最优模型。

        available_keys: [{"provider": "openai", "api_key": "sk-...", "models": [...]}]
        返回: {"provider", "model", "api_key", "base_url"} 或 None
        """
        preferences = self.MODEL_PREFERENCES.get(task_type, self.MODEL_PREFERENCES["general"])

        # 构建可用模型索引: (provider, model) → key_info
        available_index = {}
        for key_info in available_keys:
            provider = key_info.get("verified_provider") or key_info.get("provider", "")
            for model in key_info.get("models", []):
                model_id = model if isinstance(model, str) else model.get("id", "")
                available_index[(provider, model_id)] = key_info

        # 按优先级匹配
        for pref_provider, pref_model in preferences:
            key = available_index.get((pref_provider, pref_model))
            if key:
                return {
                    "provider": pref_provider,
                    "model": pref_model,
                    "api_key": key["api_key"],
                    "base_url": key.get("base_url", ""),
                }

        # 兜底: 任何可用模型
        for key_info in available_keys:
            if key_info.get("models"):
                provider = key_info.get("verified_provider") or key_info.get("provider", "")
                model = key_info["models"][0]
                model_id = model if isinstance(model, str) else model.get("id", "")
                return {
                    "provider": provider,
                    "model": model_id,
                    "api_key": key_info["api_key"],
                    "base_url": key_info.get("base_url", ""),
                }

        return None

    # ─────────────────────────────────────
    # 统一调用: 向选中的模型发送请求
    # ─────────────────────────────────────

    async def call_model(
        self,
        provider: str,
        model: str,
        api_key: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """
        统一调用 AI 模型。

        返回: {"content": "...", "model": "...", "usage": {...}}
        """
        adapter = get_adapter(provider)
        if not adapter:
            return {"error": f"不支持的 provider: {provider}"}

        try:
            return await adapter.chat(
                client=self._client,
                api_key=api_key,
                model=model,
                messages=messages,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("模型调用失败 [%s/%s]: %s", provider, model, e)
            return {"error": str(e)}


# 全局单例
model_router = ModelRouter()
