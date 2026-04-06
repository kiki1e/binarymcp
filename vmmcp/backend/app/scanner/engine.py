import asyncio
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import async_session
from app.models import Leak, ScanState
from app.scanner.github_client import GitHubClient, NewRepo
from app.scanner.patterns import scan_content
from app.scanner.redactor import hash_key
from app.scanner.validator import (
    validate_key, validate_openai_multi, validate_deepseek_with_fallback,
    close_session as close_validator,
)

logger = logging.getLogger(__name__)

# AI 相关关键词（小写），用于仓库名和描述匹配
_AI_KEYWORDS = frozenset({
    # 通用 AI/ML 术语
    "ai", "llm", "gpt", "ml", "nlp", "rag",
    "artificial-intelligence", "machine-learning", "deep-learning",
    "neural-network", "transformer", "fine-tune", "finetune",
    "generative-ai", "gen-ai", "genai", "agentic",
    # 模型/平台名（国际）
    "openai", "anthropic", "claude", "chatgpt", "gemini",
    "deepseek", "groq", "cerebras", "huggingface", "mistral",
    "llama", "qwen", "cohere", "perplexity", "siliconflow",
    "openrouter", "together-ai", "replicate", "ollama",
    "fireworks", "fireworks-ai", "stability-ai", "ai21",
    "voyage-ai", "jina-ai", "deepinfra", "novita-ai",
    "lepton-ai", "anyscale", "baseten",
    # 模型/平台名（国内）
    "moonshot", "kimi", "zhipu", "glm", "baichuan", "minimax",
    "yi-model", "01-ai", "ernie", "wenxin",
    "tongyi", "dashscope", "spark", "doubao",
    "hunyuan", "iflytek", "skywork", "internlm", "stepfun",
    "abab", "chatglm", "sensetime",
    # 常见误写/变体
    "openclaude", "openclaw", "opengpt", "open-ai",
    "chatai", "gpt4", "gpt-4", "gpt3", "gpt-3", "gpt-4o",
    "claude-3", "claude3", "claude-api", "llm-api", "ai-api",
    # 框架/工具
    "langchain", "llamaindex", "llama-index",
    "autogen", "crewai", "metagpt",
    "semantic-kernel", "haystack", "dify", "flowise",
    "lmstudio", "vllm", "litellm", "bentoml",
    "transformers", "diffusers", "safetensors",
    "lora", "qlora", "peft",
    "instructor", "guidance", "promptflow", "letta", "memgpt",
    "mem0", "agno", "phidata", "smolagents",
    "camel-ai", "taskweaver", "superagi",
    # MCP (Model Context Protocol)
    "mcp", "mcp-server", "mcp-client", "mcp-tool", "mcp-plugin",
    "model-context-protocol", "mcp-framework",
    # 向量数据库
    "chromadb", "pinecone", "weaviate", "milvus", "qdrant",
    # 可观测/实验
    "langfuse", "langsmith",
    # 应用场景
    "chatbot", "ai-agent", "copilot", "ai-assistant",
    "text-generation", "image-generation", "embedding",
    "prompt-engineering", "vector-database", "vector-store",
    "text-to-image", "text-to-speech", "speech-to-text",
    "stable-diffusion", "dall-e", "dalle", "whisper",
    "multimodal", "code-llm", "ai-search",
    "function-calling", "tool-use",
    "ai-chat", "aichat", "gpt-clone", "llm-chat",
    # API key 相关
    "api-key", "apikey",
    "openai-key", "anthropic-key", "api-keys",
})

# 编译为正则：匹配单词边界，避免 "fairy" 匹配 "ai"
_AI_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(kw) for kw in sorted(_AI_KEYWORDS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)

# AI 定向搜索关键词 — 轮转使用，每次取 3 个
# 优先覆盖高频泄露 provider 对应的关键词
_SEARCH_KEYWORDS = [
    "openai",
    "langchain",
    "chatgpt",
    "anthropic claude",
    "deepseek",
    "llm api",
    "ai-agent",
    "mcp-server",
    "huggingface",
    "stable-diffusion",
    "groq cerebras",
    "embedding vector",
    "dify flowise",
    "copilot ai-assistant",
    "llamaindex rag",
]


MAX_KEYS_PER_REPO = 5


class ScanEngine:
    def __init__(self):
        self.client = GitHubClient()
        self._running = False
        self._repos_count = 0
        # Events 专用信号量（高优先级，保证事件覆盖率）
        self._events_sem = asyncio.Semaphore(10)
        # Search 专用信号量（低优先级，不抢占 Events 资源）
        self._search_sem = asyncio.Semaphore(5)
        self._events_scanned = 0
        self._search_keyword_idx = 0
        # bounded 缓存：已达 key 上限的仓库，最多保留 2000 条
        self._repo_key_full: dict[str, float] = {}
        self._repo_key_full_max = 2000
        # 后台任务
        self._search_task: asyncio.Task | None = None
        self._validate_task: asyncio.Task | None = None

    @staticmethod
    def _is_ai_related(repo: NewRepo) -> bool:
        """根据仓库名和描述判断是否 AI 相关"""
        # 将 _ 替换为 - 使 \b 能正确匹配 my_ai_project 中的 "ai"
        text = f"{repo.owner}/{repo.name} {repo.description}".replace("_", "-")
        return bool(_AI_PATTERN.search(text))

    async def _load_state(self):
        async with async_session() as session:
            state = (await session.execute(select(ScanState))).scalar_one_or_none()
            if state:
                self.client.restore_state(
                    last_search_time=state.last_event_id,
                    events_etag=state.etag,
                    events_last_id=getattr(state, 'last_event_id_events', ''),
                )
                self._repos_count = state.total_commits_scanned
                self._events_scanned = state.total_events_scanned

    async def _save_state(self):
        async with async_session() as session:
            state = (await session.execute(select(ScanState))).scalar_one_or_none()
            if not state:
                state = ScanState(id=1)
                session.add(state)
            state.last_event_id = self.client.last_search_time
            state.etag = self.client.events_etag
            if hasattr(state, 'last_event_id_events'):
                state.last_event_id_events = self.client.events_last_id
            state.total_events_scanned = self._events_scanned
            state.total_commits_scanned = self._repos_count
            await session.commit()

    async def _store_leak(self, provider: str, raw_key: str,
                          repo_url: str, repo_owner: str,
                          repo_name: str, file_path: str,
                          timestamp: str, key_status: str = "unchecked") -> int | None:
        """存储泄露记录，返回 leak_id；重复则返回 None。"""
        # 单仓库 key 数量上限检查（bounded dict，LRU 淘汰）
        repo_full = f"{repo_owner}/{repo_name}"
        if repo_full in self._repo_key_full:
            return None

        kh = hash_key(raw_key)
        async with async_session() as session:
            repo_count = (await session.execute(
                select(func.count()).select_from(Leak).where(
                    Leak.repo_owner == repo_owner,
                    Leak.repo_name == repo_name,
                )
            )).scalar()
            if repo_count >= MAX_KEYS_PER_REPO:
                # bounded: 超限时淘汰最早的条目
                if len(self._repo_key_full) >= self._repo_key_full_max:
                    oldest = next(iter(self._repo_key_full))
                    del self._repo_key_full[oldest]
                self._repo_key_full[repo_full] = time.time()
                logger.debug("Repo %s hit %d-key limit, skipping", repo_full, MAX_KEYS_PER_REPO)
                return None

        introduced_at = None
        if timestamp:
            try:
                introduced_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                logger.debug("Invalid timestamp format: %s", timestamp[:30])
        leak = Leak(
            provider=provider,
            key_hash=kh,
            raw_key=raw_key,
            repo_url=repo_url,
            repo_owner=repo_owner,
            repo_name=repo_name,
            file_path=file_path,
            leak_introduced_at=introduced_at,
            leak_detected_at=datetime.now(timezone.utc),
            key_status=key_status,
        )
        async with async_session() as session:
            try:
                session.add(leak)
                await session.commit()
                if key_status != "filtered":
                    logger.info("Leak found: %s in %s/%s", provider, repo_owner, repo_name)
                return leak.id
            except IntegrityError:
                await session.rollback()
                return None

    async def _scan_repo(self, repo, *, count: bool = True,
                         sem: asyncio.Semaphore | None = None) -> list[tuple[int, str, str, str, str]]:
        """边下载边扫描单个仓库，返回 [(leak_id, provider, raw_key, repo_url, file_path), ...]"""
        # 已达上限的仓库直接跳过，节省 Tree API 配额
        repo_full = f"{repo.owner}/{repo.name}"
        if repo_full in self._repo_key_full:
            return []
        _sem = sem or self._events_sem
        async with _sem:
            if count:
                self._repos_count += 1
            blobs = await self.client.get_repo_blobs(repo)
            if not blobs:
                return []
            logger.info("Scanning %s/%s: %d files", repo.owner, repo.name, len(blobs))

            new_leaks: list[tuple[int, str, str, str, str]] = []
            file_sem = asyncio.Semaphore(20)

            async def _fetch_and_scan(path: str):
                async with file_sem:
                    try:
                        content = await self.client.fetch_file_raw(repo, path)
                        if not content:
                            return
                        valid, filtered = scan_content(content)
                        for provider, raw_key in valid:
                            leak_id = await self._store_leak(
                                provider=provider, raw_key=raw_key,
                                repo_url=repo.url, repo_owner=repo.owner,
                                repo_name=repo.name, file_path=path,
                                timestamp=repo.created_at,
                            )
                            if leak_id is not None:
                                new_leaks.append((leak_id, provider, raw_key, repo.url, path))
                        for provider, raw_key in filtered:
                            await self._store_leak(
                                provider=provider, raw_key=raw_key,
                                repo_url=repo.url, repo_owner=repo.owner,
                                repo_name=repo.name, file_path=path,
                                timestamp=repo.created_at,
                                key_status="filtered",
                            )
                    except Exception as e:
                        logger.warning("Error scanning %s/%s:%s: %s",
                                       repo.owner, repo.name, path, e)

            await asyncio.gather(
                *[_fetch_and_scan(p) for p in blobs],
                return_exceptions=True,
            )

            if new_leaks:
                logger.info("%s/%s: %d leaks in %d files",
                            repo.owner, repo.name, len(new_leaks), len(blobs))
            return new_leaks

    async def _batch_validate(self, leaks: list[tuple[int, str, str, str, str]]):
        """批量并发验证所有新发现的 key"""
        sem = asyncio.Semaphore(5)

        async def _validate_one(leak_id: int, provider: str, raw_key: str,
                                repo_url: str, file_path: str):
            async with sem:
                verified_provider = ""
                verified_url = ""

                if provider in ("google", "openrouter"):
                    status = "unsupported"
                elif provider == "openai" and not raw_key.startswith("sk-proj-"):
                    # generic openai 格式 key: 多 URL 验证 + 文件回退
                    status = "unchecked"
                    for attempt in range(2):
                        try:
                            status, verified_provider, verified_url = \
                                await validate_openai_multi(raw_key, repo_url, file_path)
                            if status != "unchecked":
                                break
                        except Exception as e:
                            logger.warning("Multi-validate error (leak_id=%d, attempt %d): %s",
                                           leak_id, attempt + 1, e)
                        if attempt < 1:
                            await asyncio.sleep(2)
                elif provider == "deepseek":
                    # sk-[0-9a-f]{32} 格式被 deepseek/dashscope 等共用
                    status = "unchecked"
                    for attempt in range(2):
                        try:
                            status, verified_provider, verified_url = \
                                await validate_deepseek_with_fallback(
                                    raw_key, repo_url, file_path)
                            if status != "unchecked":
                                break
                        except Exception as e:
                            logger.warning("Deepseek validate error (leak_id=%d, attempt %d): %s",
                                           leak_id, attempt + 1, e)
                        if attempt < 1:
                            await asyncio.sleep(2)
                else:
                    status = "unchecked"
                    for attempt in range(3):
                        try:
                            status = await validate_key(provider, raw_key)
                            if status != "unchecked":
                                break
                        except Exception as e:
                            logger.warning("Validation error for %s (leak_id=%d, attempt %d): %s",
                                           provider, leak_id, attempt + 1, e)
                        if attempt < 2:
                            await asyncio.sleep(2)

                async with async_session() as session:
                    db_leak = (await session.execute(
                        select(Leak).where(Leak.id == leak_id)
                    )).scalar_one_or_none()
                    if db_leak:
                        db_leak.key_status = status
                        db_leak.validated_at = datetime.now(timezone.utc)
                        if verified_provider:
                            db_leak.verified_provider = verified_provider
                        if verified_url:
                            db_leak.verified_url = verified_url
                        await session.commit()
                logger.info("Validated %s key: %s (verified: %s)",
                            provider, status, verified_provider or provider)

        await asyncio.gather(
            *[_validate_one(lid, p, k, ru, fp) for lid, p, k, ru, fp in leaks],
            return_exceptions=True,
        )

    async def _process_events(self) -> list[tuple[int, str, str, str, str]]:
        """Events 数据源：配额充裕全扫，配额不足时 AI 过滤"""
        events_repos = await self.client.poll_events()
        if not events_repos:
            return []

        self._events_scanned += len(events_repos)
        low_quota = self.client.total_core_remaining < 1000

        if low_quota:
            # --- 低配额模式：AI 过滤 + 描述补全 ---
            name_matched: list = []
            name_unmatched: list = []
            for r in events_repos:
                if self._is_ai_related(r):
                    name_matched.append(r)
                else:
                    name_unmatched.append(r)

            desc_matched: list = []
            if name_unmatched:
                batch = name_unmatched[:20]
                descriptions = await self.client.batch_fetch_repo_info(batch)
                for r in batch:
                    full_name = f"{r.owner}/{r.name}"
                    desc = descriptions.get(full_name, "")
                    if desc:
                        r.description = desc
                        if self._is_ai_related(r):
                            desc_matched.append(r)

            scan_repos = name_matched + desc_matched
            if not scan_repos:
                return []
            logger.info(
                "Events [SAVE]: %d repos, %d AI(name:%d+desc:%d), scanning...",
                len(events_repos), len(scan_repos),
                len(name_matched), len(desc_matched),
            )
        else:
            # --- 正常模式：全扫 ---
            scan_repos = events_repos
            logger.info("Events: %d repos, scanning all...", len(scan_repos))

        all_leaks: list[tuple[int, str, str, str, str]] = []
        results = await asyncio.gather(
            *[self._scan_repo(r, sem=self._events_sem) for r in scan_repos],
            return_exceptions=True,
        )
        for repo, r in zip(scan_repos, results):
            if isinstance(r, BaseException):
                logger.error("Repo scan failed (%s/%s): %s",
                             repo.owner, repo.name, r)
            elif isinstance(r, list) and r:
                all_leaks.extend(r)
        return all_leaks

    async def _process_search(self) -> list[tuple[int, str, str, str, str]]:
        """Search 数据源：配额充裕广搜全扫，配额不足时关键词定向搜索"""
        low_quota = self.client.total_core_remaining < 1000

        if low_quota:
            # --- 低配额模式：关键词定向搜索 ---
            keywords: list[str] = []
            for _ in range(3):
                keywords.append(_SEARCH_KEYWORDS[self._search_keyword_idx % len(_SEARCH_KEYWORDS)])
                self._search_keyword_idx += 1

            search_tasks = [self.client.search_new_repos(keyword=kw) for kw in keywords]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            self.client.mark_search_done()

            all_repos: list = []
            for kw, r in zip(keywords, search_results):
                if isinstance(r, BaseException):
                    logger.warning("Search error for '%s': %s", kw, r)
                elif isinstance(r, list):
                    all_repos.extend(r)

            if not all_repos:
                return []
            logger.info("Search [SAVE] [%s]: %d repos, scanning...",
                         ", ".join(keywords), len(all_repos))
        else:
            # --- 正常模式：限制 1 页（最多 100 repos），避免拖慢 Events ---
            all_repos = await self.client.search_new_repos(max_pages=1)
            self.client.mark_search_done()

            if not all_repos:
                return []
            logger.info("Search: %d repos, scanning all...", len(all_repos))

        all_leaks: list[tuple[int, str, str, str, str]] = []
        results = await asyncio.gather(
            *[self._scan_repo(r, sem=self._search_sem) for r in all_repos],
            return_exceptions=True,
        )
        for repo, r in zip(all_repos, results):
            if isinstance(r, BaseException):
                logger.error("Repo scan failed (%s/%s): %s",
                             repo.owner, repo.name, r)
            elif isinstance(r, list) and r:
                all_leaks.extend(r)
        return all_leaks

    async def _search_and_validate(self):
        """Search 后台任务：搜索 + 扫描 + 验证，独立运行不阻塞主循环"""
        try:
            search_leaks = await self._process_search()
            if search_leaks:
                logger.info("Search batch validating %d keys", len(search_leaks))
                await self._batch_validate(search_leaks)
            await self._save_state()
        except Exception as e:
            logger.error("Search background task error: %s", e, exc_info=True)

    async def run(self):
        self._running = True
        await self.client.validate_tokens()
        await self._load_state()
        logger.info("Scan engine started (Events priority + Search background)")

        search_counter = 0

        while self._running:
            try:
                cycle_start = time.time()

                # --- Events: 主线程同步处理（高优先级）---
                events_leaks = await self._process_events()

                # --- Search: 后台异步处理（低优先级，不阻塞 Events）---
                search_counter += 1
                if search_counter >= 2:
                    search_counter = 0
                    # 上一轮 Search 完成后才启动新一轮
                    if self._search_task is None or self._search_task.done():
                        if self._search_task and self._search_task.done():
                            exc = self._search_task.exception() if not self._search_task.cancelled() else None
                            if exc:
                                logger.error("Search task error: %s", exc)
                        self._search_task = asyncio.create_task(
                            self._search_and_validate())

                # --- 验证: 后台异步处理（不阻塞下一轮扫描）---
                if events_leaks:
                    logger.info("Batch validating %d new keys (background)",
                                len(events_leaks))
                    # 等待上一轮验证完成后再启动新一轮
                    if self._validate_task and not self._validate_task.done():
                        await self._validate_task
                    self._validate_task = asyncio.create_task(
                        self._batch_validate(events_leaks))

                await self._save_state()

                cycle_ms = int((time.time() - cycle_start) * 1000)
                logger.info("Cycle done: %dms, events_leaks=%d",
                            cycle_ms, len(events_leaks))

            except Exception as e:
                logger.error("Scan loop error: %s", e, exc_info=True)

            await asyncio.sleep(self.client.poll_interval)

    async def stop(self):
        self._running = False
        # 取消后台 Search 任务
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
            try:
                await self._search_task
            except asyncio.CancelledError:
                pass
        # 等待后台验证任务完成（避免丢失验证结果）
        if self._validate_task and not self._validate_task.done():
            try:
                await asyncio.wait_for(self._validate_task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._validate_task.cancel()
        await self.client.close()
        await close_validator()
