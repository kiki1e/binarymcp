"""API Key validation module.

Validates leaked keys against provider read-only endpoints.
HTTP 200 = valid, 401/403 = invalid, others = unchecked (retryable).
"""

import asyncio
import logging
import re
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)

# 模块级 Session 复用，避免每次验证创建新连接
_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=TIMEOUT)
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


@dataclass(frozen=True)
class _EndpointConfig:
    url: str
    headers: dict[str, str] | None = None  # None = use key as query param
    key_param: str | None = None  # query param name for key


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


# 8 supported providers - verified against official docs
ENDPOINTS: dict[str, _EndpointConfig] = {
    "openai": _EndpointConfig(
        url="https://api.openai.com/v1/models",
    ),
    "anthropic": _EndpointConfig(
        url="https://api.anthropic.com/v1/models",
        headers={"anthropic-version": "2023-06-01"},
    ),
    "google": _EndpointConfig(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        key_param="key",
    ),
    "openrouter": _EndpointConfig(
        url="https://openrouter.ai/api/v1/models",
    ),
    "groq": _EndpointConfig(
        url="https://api.groq.com/openai/v1/models",
    ),
    "xai": _EndpointConfig(
        url="https://api.x.ai/v1/models",
    ),
    "cerebras": _EndpointConfig(
        url="https://api.cerebras.ai/v1/models",
    ),
    # deepseek: 使用 /user/balance 接口验证，见 validate_key 特殊处理
    "siliconflow": _EndpointConfig(
        url="https://api.siliconflow.cn/v1/models",
    ),
    "huggingface": _EndpointConfig(
        url="https://huggingface.co/api/whoami-v2",
    ),
    "github": _EndpointConfig(
        url="https://api.github.com/user",
    ),
    "kimi": _EndpointConfig(
        url="https://api.kimi.com/coding/v1/models",
    ),
}

SUPPORTED_PROVIDERS = set(ENDPOINTS.keys()) | {"deepseek"}

# OpenAI 兼容格式 key 的多厂商验证端点（按使用频率排序）
OPENAI_COMPATIBLE_ENDPOINTS: list[tuple[str, str]] = [
    ("openai", "https://api.openai.com/v1/models"),
    ("dashscope", "https://dashscope.aliyuncs.com/compatible-mode/v1/models"),
    ("moonshot", "https://api.moonshot.ai/v1/models"),
]

# 从文件内容中提取含 /v1 的 URL
_BASE_URL_PATTERN = re.compile(r'https?://[^\s"\'<>\]})]+/v1(?:/[^\s"\'<>\]})]*)?' )


async def query_deepseek_balance(raw_key: str) -> dict:
    """Query DeepSeek account balance. Returns balance info dict."""
    url = "https://api.deepseek.com/user/balance"
    headers = {"Accept": "application/json", **_bearer(raw_key)}
    try:
        session = await _get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"error": f"HTTP {resp.status}"}
    except (aiohttp.ClientError, TimeoutError) as e:
        return {"error": str(e)}


async def _try_bearer_get(url: str, raw_key: str) -> int | None:
    """GET with Bearer auth, return HTTP status or None on network error."""
    try:
        session = await _get_session()
        async with session.get(url, headers=_bearer(raw_key)) as resp:
            return resp.status
    except Exception:
        return None


async def revalidate_verified_url(raw_key: str, verified_url: str) -> str | None:
    """Re-validate key against its previously verified URL.
    Returns 'valid'/'invalid' or None if inconclusive (caller should fallback).
    """
    # Normalize: ensure URL ends with /models for GET validation
    url = verified_url.rstrip("/")
    if not url.endswith("/models"):
        url = url + "/models"
    status = await _try_bearer_get(url, raw_key)
    if status == 200:
        return "valid"
    if status in (401, 403):
        return "invalid"
    return None


def _guess_provider_from_url(url: str) -> str:
    """文件 URL 爬取的 key 统一归类为 newapi。"""
    return "newapi"


async def _extract_base_urls(repo_url: str, file_path: str) -> list[str]:
    """Download source file from GitHub and extract base URLs containing /v1."""
    m = re.search(r'github\.com/([^/]+/[^/]+)', repo_url)
    if not m:
        return []
    raw_url = f"https://raw.githubusercontent.com/{m.group(1)}/HEAD/{file_path}"
    try:
        session = await _get_session()
        async with session.get(raw_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            content = await resp.text(errors="ignore")
    except (aiohttp.ClientError, TimeoutError):
        return []

    # Extract and deduplicate base URLs (truncate to /v1)
    seen: set[str] = set()
    result: list[str] = []
    known = {ep_url for _, ep_url in OPENAI_COMPATIBLE_ENDPOINTS}
    for raw in _BASE_URL_PATTERN.findall(content):
        base = raw.split("/v1")[0] + "/v1"
        if base not in seen:
            seen.add(base)
            # Skip URLs already covered by OPENAI_COMPATIBLE_ENDPOINTS
            if not any(base in k for k in known):
                result.append(base)
    return result


async def validate_openai_multi(
    raw_key: str, repo_url: str = "", file_path: str = "",
) -> tuple[str, str, str]:
    """Validate generic openai-format key against multiple providers.
    Returns (status, verified_provider, verified_url).
    Step 1 and Step 2 use asyncio.gather for concurrent requests.
    """
    has_auth_error = False

    # Step 1: try known compatible endpoints concurrently
    tasks = [_try_bearer_get(url, raw_key) for _, url in OPENAI_COMPATIBLE_ENDPOINTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for (provider_name, url), status in zip(OPENAI_COMPATIBLE_ENDPOINTS, results):
        if isinstance(status, BaseException):
            continue
        if status == 200:
            return ("valid", provider_name, url)
        if status in (401, 403):
            has_auth_error = True

    # Step 2: try URLs extracted from source file concurrently
    if repo_url and file_path:
        file_urls = await _extract_base_urls(repo_url, file_path)
        if file_urls:
            models_urls = [u.rstrip("/") + "/models" for u in file_urls]
            results2 = await asyncio.gather(
                *[_try_bearer_get(mu, raw_key) for mu in models_urls],
                return_exceptions=True,
            )
            for base_url, status in zip(file_urls, results2):
                if isinstance(status, BaseException):
                    continue
                if status == 200:
                    return ("valid", _guess_provider_from_url(base_url), base_url)
                if status in (401, 403):
                    has_auth_error = True

    return ("invalid" if has_auth_error else "unchecked", "", "")


async def validate_deepseek_with_fallback(
    raw_key: str, repo_url: str = "", file_path: str = "",
) -> tuple[str, str, str]:
    """Validate sk-[0-9a-f]{32} key against deepseek, then all compatible endpoints.
    Returns (status, verified_provider, verified_url).
    sk- hex32 format is shared by deepseek, dashscope, and potentially others.
    """
    # Step 1: try deepseek balance API (deepseek-specific)
    data = await query_deepseek_balance(raw_key)
    if "error" not in data:
        if data.get("is_available"):
            return ("valid", "deepseek", "https://api.deepseek.com/v1")
        # deepseek recognized the key but balance exhausted
        return ("invalid", "", "")

    deepseek_status = "invalid" if any(
        code in str(data["error"]) for code in ("401", "403")
    ) else "unchecked"

    # Step 2: not a deepseek key, try all compatible endpoints + file URL extraction
    # validate_openai_multi covers: openai, dashscope, moonshot + source file URLs
    if deepseek_status == "invalid":
        try:
            status, vp, vu = await validate_openai_multi(
                raw_key, repo_url, file_path)
            if status != "unchecked":
                return (status, vp, vu)
        except Exception as e:
            logger.warning("Deepseek fallback multi-validate error: %s", e)

    return (deepseek_status, "", "")


async def validate_key(provider: str, raw_key: str) -> str:
    """Validate a single API key. Returns 'valid'/'invalid'/'unchecked'/'unsupported'."""
    # minimax: GET 返回 404，需用 POST 验证；429=余额不足但 key 有效
    if provider == "minimax":
        url = "https://api.minimaxi.com/v1/chat/completions"
        body = b'{"model":"MiniMax-Text-01","messages":[{"role":"user","content":"hi"}],"max_tokens":1}'
        try:
            session = await _get_session()
            async with session.post(url, headers={**_bearer(raw_key), "Content-Type": "application/json"}, data=body) as resp:
                if resp.status in (200, 429):
                    return "valid"
                if resp.status in (401, 403):
                    return "invalid"
                return "unchecked"
        except (aiohttp.ClientError, TimeoutError) as e:
            logger.warning("Validation error for minimax: %s", e)
            return "unchecked"

    # deepseek: 通过余额接口判断 is_available
    if provider == "deepseek":
        data = await query_deepseek_balance(raw_key)
        if "error" in data:
            return "invalid" if "401" in str(data["error"]) or "403" in str(data["error"]) else "unchecked"
        return "valid" if data.get("is_available") else "invalid"

    if provider not in ENDPOINTS:
        return "unsupported"

    cfg = ENDPOINTS[provider]

    # Build request kwargs
    if cfg.key_param:
        # Key as query parameter (Google)
        url = f"{cfg.url}?{cfg.key_param}={raw_key}"
        headers = cfg.headers or {}
    else:
        # Key as Bearer token or custom header
        if provider == "anthropic":
            headers = {"x-api-key": raw_key, **(cfg.headers or {})}
        elif provider == "github":
            headers = {"Authorization": f"token {raw_key}", **(cfg.headers or {})}
        else:
            headers = {**_bearer(raw_key), **(cfg.headers or {})}
        url = cfg.url

    try:
        session = await _get_session()
        async with session.get(url, headers=headers) as resp:
            status = resp.status
            if status == 200:
                return "valid"
            if status in (400, 401, 403):
                return "invalid"
            logger.warning(
                "Unexpected status %d validating %s key", status, provider
            )
            return "unchecked"
    except (aiohttp.ClientError, TimeoutError) as e:
        logger.warning("Validation error for %s: %s", provider, e)
        return "unchecked"
