"""
Model Router — AI 模型智能路由

功能:
- 统一调用多个 AI Provider (OpenAI 兼容 / Anthropic)
- 流式/非流式两种模式
- 根据可用 API Key 自动发现模型
- 根据赛题类型智能选择最优模型
- 自定义 Provider 动态注册
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from app.model_router.providers import (
    PROVIDER_ADAPTERS,
    BaseProviderAdapter,
    get_adapter,
    register_custom_provider,
    unregister_provider,
)

logger = logging.getLogger(__name__)


class ModelRouter:
    """AI 模型智能选择 + 统一调用接口"""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=120)

    async def close(self):
        await self._client.aclose()

    # ─────────────────────────────────────
    # 自定义 Provider 管理
    # ─────────────────────────────────────

    def register_provider(self, name: str, base_url: str) -> bool:
        """注册自定义 provider"""
        try:
            register_custom_provider(name, base_url)
            logger.info("Registered custom provider: %s -> %s", name, base_url)
            return True
        except Exception as e:
            logger.error("Failed to register provider %s: %s", name, e)
            return False

    def remove_provider(self, name: str) -> bool:
        """移除自定义 provider"""
        return unregister_provider(name)

    def list_providers(self) -> list[dict]:
        """列出所有已注册的 provider"""
        return [
            {
                "name": adapter.name,
                "default_base_url": adapter.default_base_url,
                "builtin": adapter.name in (
                    "openai", "deepseek", "groq", "xai", "cerebras", "kimi",
                    "moonshot", "siliconflow", "dashscope", "minimax", "anthropic",
                ),
            }
            for adapter in PROVIDER_ADAPTERS.values()
        ]

    # ─────────────────────────────────────
    # 模型发现
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
    # 模型选择
    # ─────────────────────────────────────

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
        "web_analyze": [
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

        available_index = {}
        for key_info in available_keys:
            provider = key_info.get("verified_provider") or key_info.get("provider", "")
            for model in key_info.get("models", []):
                model_id = model if isinstance(model, str) else model.get("id", "")
                available_index[(provider, model_id)] = key_info

        for pref_provider, pref_model in preferences:
            key = available_index.get((pref_provider, pref_model))
            if key:
                return {
                    "provider": pref_provider,
                    "model": pref_model,
                    "api_key": key["api_key"],
                    "base_url": key.get("base_url", ""),
                }

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
    # 统一调用 (非流式)
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
        """非流式调用"""
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
            err_type = type(e).__name__
            err_msg = str(e) or "(no message)"
            logger.error("模型调用失败 [%s/%s]: %s: %s", provider, model, err_type, err_msg)
            return {"error": f"[{err_type}] {err_msg}"}

    # ─────────────────────────────────────
    # 统一调用 (流式)
    # ─────────────────────────────────────

    async def call_model_stream(
        self,
        provider: str,
        model: str,
        api_key: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式调用 — 逐块 yield 文本"""
        adapter = get_adapter(provider)
        if not adapter:
            yield json.dumps({"error": f"不支持的 provider: {provider}"})
            return

        try:
            async for chunk in adapter.chat_stream(
                client=self._client,
                api_key=api_key,
                model=model,
                messages=messages,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        except httpx.HTTPStatusError as e:
            logger.error("流式调用 HTTP 错误 [%s/%s]: %s", provider, model, e)
            yield json.dumps({"error": f"HTTP {e.response.status_code}: {e.response.text}"})
        except Exception as e:
            logger.error("流式调用失败 [%s/%s]: %s", provider, model, e)
            yield json.dumps({"error": str(e)})


# 全局单例
model_router = ModelRouter()
