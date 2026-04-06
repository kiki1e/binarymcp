import logging
import math
import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPattern:
    name: str
    regex: re.Pattern
    keywords: tuple[str, ...]  # 快速预过滤关键词


# Ordered by specificity: specific prefixes first, generic "sk-" last.
# deepseek MUST precede generic openai to avoid misclassification.
PROVIDERS: list[ProviderPattern] = [
    ProviderPattern("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), ("sk-ant-",)),
    ProviderPattern("openrouter", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}"), ("sk-or-",)),
    ProviderPattern("openai", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), ("sk-proj-",)),
    ProviderPattern("stripe", re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{20,}"), ("sk_live_", "sk_test_")),
    ProviderPattern("google", re.compile(r"AIza[0-9A-Za-z\-_]{35}"), ("AIza",)),
    ProviderPattern("xai", re.compile(r"xai-[A-Za-z0-9]{20,}"), ("xai-",)),
    ProviderPattern("groq", re.compile(r"gsk_[A-Za-z0-9]{20,}"), ("gsk_",)),
    ProviderPattern("cerebras", re.compile(r"csk-[A-Za-z0-9]{20,}"), ("csk-",)),
    ProviderPattern("aws", re.compile(r"AKIA[0-9A-Z]{16}"), ("AKIA",)),
    ProviderPattern("twilio", re.compile(r"SK[0-9a-fA-F]{32}"), ("SK",)),
    ProviderPattern("sendgrid", re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"), ("SG.",)),
    ProviderPattern("mailgun", re.compile(r"(?:api)?key-[0-9a-f]{32}(?![0-9a-f])"), ("key-",)),
    ProviderPattern("slack", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), ("xoxb-", "xoxa-", "xoxp-", "xoxr-", "xoxs-")),
    ProviderPattern("github", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")),
    ProviderPattern("huggingface", re.compile(r"hf_[A-Za-z0-9]{20,}"), ("hf_",)),
    ProviderPattern("pinecone", re.compile(r"pcsk_[A-Za-z0-9_-]{20,}"), ("pcsk_",)),
    ProviderPattern("livekit", re.compile(r"API[A-Za-z0-9]{10,}"), ("LIVEKIT_API_KEY",)),
    ProviderPattern("minimax", re.compile(r"sk-cp-[A-Za-z0-9_-]{20,}"), ("sk-cp-",)),
    ProviderPattern("kimi", re.compile(r"sk-kimi-[A-Za-z0-9_-]{20,}"), ("sk-kimi-",)),
    ProviderPattern("siliconflow", re.compile(r"sk-[a-z]{40,}"), ("sk-",)),
    ProviderPattern("deepseek", re.compile(r"sk-[0-9a-f]{32}(?![0-9a-zA-Z])"), ("sk-",)),
    ProviderPattern("openai", re.compile(r"sk-[A-Za-z0-9_-]{20,}"), ("sk-",)),
]

logger = logging.getLogger(__name__)

ENTROPY_THRESHOLD = 3.0

# 占位符/示例 key 中常见的停用词
STOPWORDS = frozenset({
    "example", "placeholder", "your", "test", "fake", "dummy",
    "sample", "demo", "todo", "fixme", "replace", "insert",
    "change", "update", "xxxx", "yyyy", "zzzz", "here",
    "mock", "temp", "null", "undefined", "none",
})

# 已知前缀（按长度降序，优先匹配长前缀）
_KNOWN_PREFIXES = sorted([
    "sk-ant-api03-", "sk-ant-", "sk-or-", "sk-proj-", "sk-cp-", "sk-kimi-",
    "sk_live_", "sk_test_", "AIza", "xai-", "gsk_", "csk-",
    "AKIA", "SG.", "key-", "ghp_", "gho_", "ghu_", "ghs_", "ghr_",
    "hf_", "pcsk_", "sk-", "API",
    "xoxb-", "xoxa-", "xoxp-", "xoxr-", "xoxs-",
], key=len, reverse=True)

# CSS 类名关键词
_CSS_WORDS = ("label", "container", "toggle", "wrapper", "button", "arrow", "item", "hidden")


def _has_sequential_run(s: str, min_len: int = 6) -> bool:
    """检测字符串中是否存在连续 min_len+ 字符的升序或降序 run（如 abcdef, 654321, zyxwvu）"""
    if len(s) < min_len:
        return False
    asc = 1
    desc = 1
    for i in range(1, len(s)):
        if ord(s[i]) == ord(s[i - 1]) + 1:
            asc += 1
            if asc >= min_len:
                return True
        else:
            asc = 1
        if ord(s[i]) == ord(s[i - 1]) - 1:
            desc += 1
            if desc >= min_len:
                return True
        else:
            desc = 1
    return False


def _shannon_entropy(s: str) -> float:
    """计算字符串的 Shannon 信息熵 (bits per character)"""
    if not s:
        return 0.0
    length = len(s)
    counts = Counter(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _strip_prefix(key: str) -> str:
    """去掉已知 provider 前缀，返回 key 的随机主体部分"""
    for prefix in _KNOWN_PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def _is_false_positive(key: str) -> bool:
    """过滤明显的误报：占位符、重复字符、低熵值、顺序字符等"""
    # 1. 双下划线（CSS module hash 等）
    if "__" in key:
        logger.debug("Filtered (double underscore): %s", key[:20])
        return True

    lower = key.lower()

    # 2. CSS 类名关键词
    if any(w in lower for w in _CSS_WORDS):
        logger.debug("Filtered (CSS word): %s", key[:20])
        return True

    # 3. 占位符/停用词
    if any(w in lower for w in STOPWORDS):
        logger.debug("Filtered (stopword): %s", key[:20])
        return True

    # 4-6: 去前缀后的 body 分析
    body = _strip_prefix(key)

    # 4. slug 模式：2+ 个纯字母段（各 3+ 字符）
    if sum(1 for p in body.split("-") if p.isalpha() and len(p) >= 3) >= 2:
        logger.debug("Filtered (slug pattern): %s", key[:20])
        return True

    # 5. 可读单词：含 2+ 个连续 7+ 小写字母段
    if len(re.findall(r'[a-z]{7,}', body)) >= 2:
        logger.debug("Filtered (readable words): %s", key[:20])
        return True

    # 连续 10+ 位纯数字（如 sk-bd-005-1771655226273474702）
    if re.search(r'\d{10,}', body):
        logger.debug("Filtered (consecutive digits): %s", key[:20])
        return True

    if len(body) < 8:
        return False

    # 6. 重复字符（字符种类 <= 2）
    if len(set(body)) <= 2:
        logger.debug("Filtered (repeated chars): %s", key[:20])
        return True

    # 6. 顺序字符：检测连续6+字符的升序/降序 run
    if _has_sequential_run(body.lower(), 6):
        logger.debug("Filtered (sequential run): %s", key[:20])
        return True

    # 7. 低熵值（最后执行，计算开销最大）
    if len(body) >= 10:
        entropy = _shannon_entropy(body)
        if entropy < ENTROPY_THRESHOLD:
            logger.debug("Filtered (low entropy %.2f): %s", entropy, key[:20])
            return True

    return False


def scan_content(text: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Scan text and return (valid_matches, filtered_matches).
    Each match is (provider, raw_key).
    """
    found: list[tuple[str, str]] = []
    filtered: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for p in PROVIDERS:
        if not any(kw in text for kw in p.keywords):
            continue
        for m in p.regex.finditer(text):
            key = m.group()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if _is_false_positive(key):
                filtered.append((p.name, key))
            else:
                found.append((p.name, key))
    return found, filtered
