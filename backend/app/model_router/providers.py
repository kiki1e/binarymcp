"""
AI Provider 适配器

统一不同 AI 厂商的 API 调用接口，支持流式和非流式两种模式:
- OpenAI 兼容 (OpenAI/DeepSeek/Groq/xAI/Cerebras/Kimi/SiliconFlow/Moonshot/DashScope/Minimax/自定义)
- Anthropic (Claude)
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# 基类
# ═══════════════════════════════════════

class BaseProviderAdapter:
    """AI Provider 适配器基类"""

    name: str = ""
    default_base_url: str = ""

    async def list_models(self, client: httpx.AsyncClient, api_key: str, base_url: str = "") -> list[dict]:
        raise NotImplementedError

    async def chat(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """非流式调用"""
        raise NotImplementedError

    async def chat_stream(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式调用 — 逐块 yield 文本内容"""
        raise NotImplementedError


# ═══════════════════════════════════════
# OpenAI 兼容适配器 (通用)
# ═══════════════════════════════════════

class OpenAICompatAdapter(BaseProviderAdapter):
    """OpenAI /v1/chat/completions 兼容 API (支持流式)"""

    def __init__(self, name: str, default_base_url: str):
        self.name = name
        self.default_base_url = default_base_url

    def _url(self, base_url: str, path: str) -> str:
        base = (base_url or self.default_base_url).rstrip("/")
        return f"{base}{path}"

    def _headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def list_models(self, client: httpx.AsyncClient, api_key: str, base_url: str = "") -> list[dict]:
        url = self._url(base_url, "/v1/models")
        r = await client.get(url, headers=self._headers(api_key))
        r.raise_for_status()
        data = r.json().get("data", [])
        return [{"id": m["id"], "owned_by": m.get("owned_by", "")} for m in data]

    async def chat(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        url = self._url(base_url, "/v1/chat/completions")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        r = await client.post(url, json=payload, headers=self._headers(api_key))
        r.raise_for_status()
        data = r.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "usage": data.get("usage", {}),
        }

    async def chat_stream(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """流式调用 — SSE 逐块返回"""
        url = self._url(base_url, "/v1/chat/completions")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with client.stream("POST", url, json=payload, headers=self._headers(api_key)) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content is not None:
                        yield str(content)
                except json.JSONDecodeError:
                    continue


# ═══════════════════════════════════════
# Anthropic 适配器
# ═══════════════════════════════════════

class AnthropicAdapter(BaseProviderAdapter):
    name = "anthropic"
    default_base_url = "https://api.anthropic.com"

    def _headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def list_models(self, client: httpx.AsyncClient, api_key: str, base_url: str = "") -> list[dict]:
        url = f"{(base_url or self.default_base_url).rstrip('/')}/v1/models"
        try:
            r = await client.get(url, headers=self._headers(api_key))
            r.raise_for_status()
            data = r.json().get("data", [])
            return [{"id": m["id"], "owned_by": "anthropic"} for m in data]
        except Exception:
            return [
                {"id": "claude-opus-4-20250514", "owned_by": "anthropic"},
                {"id": "claude-sonnet-4-20250514", "owned_by": "anthropic"},
                {"id": "claude-haiku-4-20250514", "owned_by": "anthropic"},
            ]

    def _build_payload(self, messages, model, temperature, max_tokens, stream=False):
        system_msg = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg += m["content"] + "\n"
            else:
                user_messages.append(m)

        payload = {
            "model": model,
            "messages": user_messages or [{"role": "user", "content": "Hello"}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system_msg.strip():
            payload["system"] = system_msg.strip()
        return payload

    async def chat(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        url = f"{(base_url or self.default_base_url).rstrip('/')}/v1/messages"
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=False)

        r = await client.post(url, json=payload, headers=self._headers(api_key))
        r.raise_for_status()
        data = r.json()
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block["text"]
        return {
            "content": content,
            "model": data.get("model", model),
            "usage": data.get("usage", {}),
        }

    async def chat_stream(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        model: str,
        messages: list[dict],
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Anthropic 流式调用 — SSE 逐块返回"""
        url = f"{(base_url or self.default_base_url).rstrip('/')}/v1/messages"
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True)

        async with client.stream("POST", url, json=payload, headers=self._headers(api_key)) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if text:
                                yield str(text)
                except json.JSONDecodeError:
                    continue


# ═══════════════════════════════════════
# 注册所有适配器
# ═══════════════════════════════════════

PROVIDER_ADAPTERS: dict[str, BaseProviderAdapter] = {
    "openai": OpenAICompatAdapter("openai", "https://api.openai.com"),
    "deepseek": OpenAICompatAdapter("deepseek", "https://api.deepseek.com"),
    "groq": OpenAICompatAdapter("groq", "https://api.groq.com/openai"),
    "xai": OpenAICompatAdapter("xai", "https://api.x.ai"),
    "cerebras": OpenAICompatAdapter("cerebras", "https://api.cerebras.ai"),
    "kimi": OpenAICompatAdapter("kimi", "https://api.moonshot.cn"),
    "moonshot": OpenAICompatAdapter("moonshot", "https://api.moonshot.cn"),
    "siliconflow": OpenAICompatAdapter("siliconflow", "https://api.siliconflow.cn"),
    "dashscope": OpenAICompatAdapter("dashscope", "https://dashscope.aliyuncs.com/compatible-mode"),
    "minimax": OpenAICompatAdapter("minimax", "https://api.minimax.chat"),
    "anthropic": AnthropicAdapter(),
    "newapi": OpenAICompatAdapter("newapi", ""),  # base_url 由 verified_url 提供
    "custom": OpenAICompatAdapter("custom", ""),  # 用户自定义
}


def get_adapter(provider: str) -> Optional[BaseProviderAdapter]:
    return PROVIDER_ADAPTERS.get(provider)


def register_custom_provider(name: str, base_url: str) -> OpenAICompatAdapter:
    """注册自定义 provider (OpenAI 兼容模式)"""
    adapter = OpenAICompatAdapter(name, base_url)
    PROVIDER_ADAPTERS[name] = adapter
    return adapter


def unregister_provider(name: str) -> bool:
    """移除自定义 provider (内置 provider 不可移除)"""
    builtin = {"openai", "deepseek", "groq", "xai", "cerebras", "kimi",
               "moonshot", "siliconflow", "dashscope", "minimax", "anthropic"}
    if name in builtin:
        return False
    return PROVIDER_ADAPTERS.pop(name, None) is not None
