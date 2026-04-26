import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from typing import Any

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

# 跳过的文件扩展名（二进制/资源/样式/不含密钥的文件）
SKIP_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp", ".tiff",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flac", ".ogg",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".wasm", ".class",
    ".min.js", ".min.css", ".map", ".snap",
    ".lock",
    # 样式文件 - 不含 API key
    ".css", ".scss", ".less", ".sass", ".styl",
})

# 跳过的文件名（精确匹配，小写）
SKIP_FILENAMES = frozenset({
    "license", "licence", "changelog", "changes", "history",
    "contributing", "contributors", "authors", "codeowners",
    "makefile", "rakefile", "gemfile", "podfile",
    ".gitignore", ".gitattributes", ".editorconfig", ".prettierrc",
    ".eslintignore", ".dockerignore", ".npmignore",
    "tsconfig.json", "jsconfig.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "composer.lock", "cargo.lock",
})

# 跳过的目录前缀
SKIP_DIRS = ("node_modules/", "vendor/", ".git/", "dist/", "build/", "__pycache__/", ".next/")


@dataclass
class NewRepo:
    """新创建的仓库信息"""
    owner: str
    name: str
    url: str
    default_branch: str
    created_at: str
    description: str = ""


@dataclass
class TokenState:
    """单个 Token 的状态追踪"""
    token: str
    valid: bool = True
    remaining: int = 5000  # 剩余配额
    reset_at: int = 0      # 配额重置时间戳
    last_error: str = ""


class GitHubClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._poll_interval: int = settings.poll_interval
        # Search API: 上次搜索时间戳
        self._last_search_time: str = ""
        # 已扫描仓库去重 (full_name)
        self._seen_repos: deque = deque(maxlen=5000)
        self._seen_repos_set: set = set()
        # 多 Token 管理
        self._tokens: list[TokenState] = [
            TokenState(token=t) for t in settings.token_list
        ]
        # Events API 状态
        self._events_etag: str = ""
        self._events_last_id: str = ""
        self._seen_events: set = set()
        self._seen_events_deque: deque = deque(maxlen=10000)
        self._repo_push_cooldown: dict[str, float] = {}  # {full_name: timestamp}

    async def validate_tokens(self):
        """启动时验证所有 Token 有效性，移除无效 Token"""
        if not self._tokens:
            logger.warning("未配置 GitHub Token，将以匿名模式运行（60次/小时）")
            return

        session = await self._get_session()
        valid_count = 0
        for ts in self._tokens:
            try:
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {ts.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                async with session.get(
                    "https://api.github.com/rate_limit", headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        core = data.get("resources", {}).get("core", {})
                        ts.remaining = core.get("remaining", 0)
                        ts.reset_at = core.get("reset", 0)
                        ts.valid = True
                        valid_count += 1
                        masked = ts.token[:4] + "..." + ts.token[-4:]
                        logger.info(
                            "Token %s 有效 (剩余: %d, 重置: %ds后)",
                            masked, ts.remaining,
                            max(ts.reset_at - int(time.time()), 0),
                        )
                    elif resp.status == 401:
                        ts.valid = False
                        ts.last_error = "认证失败(401)"
                        masked = ts.token[:4] + "..." + ts.token[-4:]
                        logger.error("Token %s 无效，已禁用", masked)
                    else:
                        ts.valid = False
                        ts.last_error = f"HTTP {resp.status}"
                        masked = ts.token[:4] + "..." + ts.token[-4:]
                        logger.warning("Token %s 验证异常: %d", masked, resp.status)
            except Exception as e:
                ts.valid = False
                ts.last_error = str(e)
                logger.error("Token 验证网络错误: %s", e)

        if valid_count == 0:
            logger.error("所有 Token 均无效！将以匿名模式运行")
        else:
            logger.info("Token 验证完成: %d/%d 有效", valid_count, len(self._tokens))

    def _pick_token(self) -> str | None:
        """选择最优 Token：优先剩余配额最多的有效 Token"""
        now = int(time.time())
        # 已过重置时间的 Token，恢复配额（不限 remaining<=0，避免低配额 Token 永不刷新）
        for ts in self._tokens:
            if ts.valid and ts.reset_at and now >= ts.reset_at:
                ts.remaining = 5000
                ts.reset_at = now + 3600

        # 按剩余配额降序排列，选第一个有效且有配额的
        candidates = [ts for ts in self._tokens if ts.valid and ts.remaining > 0]
        if not candidates:
            return None
        best = max(candidates, key=lambda t: t.remaining)
        return best.token

    def _get_token_state(self, token: str) -> TokenState | None:
        """根据 token 字符串查找对应的 TokenState"""
        for ts in self._tokens:
            if ts.token == token:
                return ts
        return None

    def _base_headers(self, token: str | None = None) -> dict:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        t = token or self._pick_token()
        if t:
            h["Authorization"] = f"Bearer {t}"
        return h

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _mark_repo_seen(self, full_name: str):
        """Bounded dedup for repos."""
        if len(self._seen_repos) >= self._seen_repos.maxlen:
            evicted = self._seen_repos[0]
            self._seen_repos_set.discard(evicted)
        self._seen_repos.append(full_name)
        self._seen_repos_set.add(full_name)

    def _mark_event_seen(self, event_id: str):
        """维护 bounded 事件 ID 去重集合"""
        if len(self._seen_events_deque) >= self._seen_events_deque.maxlen:
            evicted = self._seen_events_deque[0]
            self._seen_events.discard(evicted)
        self._seen_events_deque.append(event_id)
        self._seen_events.add(event_id)

    def _cleanup_cooldown(self):
        """清理超过 5 分钟的 push cooldown 记录"""
        cutoff = time.time() - 300
        expired = [k for k, v in self._repo_push_cooldown.items() if v < cutoff]
        for k in expired:
            del self._repo_push_cooldown[k]

    def _update_rate_limit(self, token: str, resp_headers: dict):
        """从响应头更新 Token 的速率限制状态"""
        ts = self._get_token_state(token)
        if not ts:
            return
        remaining = resp_headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            ts.remaining = int(remaining)
        reset = resp_headers.get("X-RateLimit-Reset")
        if reset is not None:
            ts.reset_at = int(reset)

    async def _request_with_rotation(
        self, url: str, headers: dict | None = None,
        params: dict | None = None, max_retries: int = 3,
    ) -> tuple[int, dict, Any]:
        """带 Token 轮转的通用请求方法。返回 (status, headers, json_body)"""
        session = await self._get_session()

        for attempt in range(max_retries):
            token = self._pick_token()
            h = headers.copy() if headers else {}
            h.update(self._base_headers(token))

            try:
                async with session.get(url, headers=h, params=params) as resp:
                    resp_headers = dict(resp.headers)
                    # 更新当前 Token 的速率限制
                    if token:
                        self._update_rate_limit(token, resp_headers)

                    if resp.status == 401:
                        # Token 失效，标记并切换
                        ts = self._get_token_state(token) if token else None
                        if ts:
                            ts.valid = False
                            ts.last_error = "认证失败(401)"
                            masked = token[:4] + "..." + token[-4:]
                            logger.warning("Token %s 已失效，切换下一个", masked)
                        continue

                    if resp.status == 403:
                        remaining = resp_headers.get("X-RateLimit-Remaining", "0")
                        if remaining == "0" and token:
                            ts = self._get_token_state(token)
                            if ts:
                                ts.remaining = 0
                                ts.reset_at = int(resp_headers.get("X-RateLimit-Reset", "0"))
                            # 尝试切换到其他 Token
                            next_token = self._pick_token()
                            if next_token and next_token != token:
                                logger.info("Token 配额耗尽，切换到下一个")
                                continue
                            # 所有 Token 耗尽，等待最短重置时间后重试
                            wait = self._min_reset_wait()
                            logger.warning("所有 Token 配额耗尽，等待 %ds", wait)
                            await asyncio.sleep(wait)
                            continue
                        return (resp.status, resp_headers, None)

                    body = await resp.json() if resp.status == 200 else None
                    return (resp.status, resp_headers, body)

            except Exception as e:
                logger.error("请求错误 (尝试 %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        return (0, {}, None)

    def _min_reset_wait(self) -> int:
        """计算所有 Token 中最短的重置等待时间"""
        now = int(time.time())
        waits = [
            max(ts.reset_at - now, 0)
            for ts in self._tokens if ts.valid and ts.reset_at > 0
        ]
        return max(min(waits), 60) if waits else 60

    async def poll_events(self, max_pages: int = 3) -> list[NewRepo]:
        """轮询 GitHub /events API，提取 PushEvent 对应的仓库。

        配额节省：
        - ETag 条件请求（304 不消耗配额）
        - 事件 ID 去重
        - 同仓库 60s 合并冷却
        - 已扫描仓库去重（复用 _seen_repos_set）
        """
        session = await self._get_session()
        repos: list[NewRepo] = []
        newest_event_id = ""

        for page in range(1, max_pages + 1):
            data = None
            token = self._pick_token()
            headers = self._base_headers(token)
            # 第一页使用 ETag 条件请求
            if page == 1 and self._events_etag:
                headers["If-None-Match"] = self._events_etag

            params = {"per_page": "100"}
            if page > 1:
                params["page"] = str(page)

            try:
                async with session.get(
                    "https://api.github.com/events",
                    headers=headers, params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp_headers = dict(resp.headers)
                    if token:
                        self._update_rate_limit(token, resp_headers)

                    # 更新 X-Poll-Interval
                    poll_int = resp_headers.get("X-Poll-Interval")
                    if poll_int:
                        self._poll_interval = max(int(poll_int), 30)

                    # 304: 无新事件，不消耗配额
                    if resp.status == 304:
                        return []

                    # 错误处理
                    if resp.status == 401 and token:
                        ts = self._get_token_state(token)
                        if ts:
                            ts.valid = False
                            ts.last_error = "认证失败(401)"
                        break
                    if resp.status == 403 and token:
                        remaining = resp_headers.get("X-RateLimit-Remaining", "0")
                        if remaining == "0":
                            ts = self._get_token_state(token)
                            if ts:
                                ts.remaining = 0
                                ts.reset_at = int(resp_headers.get("X-RateLimit-Reset", "0"))
                        break
                    if resp.status != 200:
                        logger.warning("Events API error: %d", resp.status)
                        break

                    # 更新 ETag（仅第一页）
                    if page == 1:
                        new_etag = resp_headers.get("Etag", "")
                        if new_etag:
                            self._events_etag = new_etag

                    data = await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error("Events API request error: %s", e)
                break

            if not data:
                break

            found_old = False
            now_ts = time.time()

            for event in data:
                event_id = event.get("id", "")
                event_type = event.get("type", "")

                # 处理 PushEvent 和 CreateEvent(新仓库)
                if event_type == "CreateEvent":
                    payload = event.get("payload", {})
                    if payload.get("ref_type") != "repository":
                        continue
                elif event_type != "PushEvent":
                    continue

                # 事件去重：已处理过或早于上次保存的 ID
                if event_id in self._seen_events:
                    found_old = True
                    break
                # 整数比较避免字符串位数不同时排序错误
                try:
                    eid_int = int(event_id)
                except (ValueError, TypeError):
                    eid_int = 0
                if self._events_last_id:
                    try:
                        last_int = int(self._events_last_id)
                    except (ValueError, TypeError):
                        last_int = 0
                    if eid_int and last_int and eid_int <= last_int:
                        found_old = True
                        break

                # 记录最新事件 ID（整数比较）
                try:
                    newest_int = int(newest_event_id) if newest_event_id else 0
                except (ValueError, TypeError):
                    newest_int = 0
                if not newest_event_id or eid_int > newest_int:
                    newest_event_id = event_id
                self._mark_event_seen(event_id)

                repo_data = event.get("repo", {})
                repo_full_name = repo_data.get("name", "")  # "owner/repo"
                if not repo_full_name:
                    continue

                # 已扫描仓库去重
                if repo_full_name in self._seen_repos_set:
                    continue

                # 同仓库 60s 合并冷却
                last_push = self._repo_push_cooldown.get(repo_full_name, 0)
                if now_ts - last_push < 60:
                    continue
                self._repo_push_cooldown[repo_full_name] = now_ts

                # 从 ref 提取分支名（PushEvent）/ 获取 master_branch（CreateEvent）
                if event_type == "CreateEvent":
                    # payload 已在上方 CreateEvent 分支中获取
                    branch = payload.get("master_branch", "main")
                    description = payload.get("description") or ""
                else:
                    payload = event.get("payload", {})
                    ref = payload.get("ref", "")
                    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else "main"
                    description = ""

                self._mark_repo_seen(repo_full_name)
                parts = repo_full_name.split("/", 1)
                repos.append(NewRepo(
                    owner=parts[0],
                    name=parts[1] if len(parts) > 1 else repo_full_name,
                    url=f"https://github.com/{repo_full_name}",
                    default_branch=branch,
                    created_at=event.get("created_at", ""),
                    description=description,
                ))

            if found_old or len(data) < 100:
                break

        # 更新持久化 ID
        if newest_event_id:
            self._events_last_id = newest_event_id

        # 清理过期冷却记录
        self._cleanup_cooldown()

        if repos:
            logger.info("Events API: %d unique repos from Push/CreateEvents", len(repos))
        return repos

    async def search_new_repos(self, keyword: str = "", max_pages: int = 1) -> list[NewRepo]:
        """通过 Search API 搜索最近创建的公开仓库。
        keyword 非空时进行 AI 关键词定向搜索，否则泛搜索。
        注意：调用方需在所有搜索完成后调用 mark_search_done() 更新时间戳。
        """
        now = datetime.now(timezone.utc)
        if not self._last_search_time:
            since = now - timedelta(minutes=3)
        else:
            try:
                since = datetime.fromisoformat(self._last_search_time)
            except ValueError:
                since = now - timedelta(minutes=3)

        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        query = f"{keyword} created:>={since_str}" if keyword else f"created:>={since_str}"

        repos: list[NewRepo] = []
        for page in range(1, max_pages + 1):
            status, _, data = await self._request_with_rotation(
                GITHUB_SEARCH_URL,
                params={
                    "q": query, "sort": "created", "order": "desc",
                    "per_page": "100", "page": str(page),
                },
            )
            if status != 200 or data is None:
                break

            items = data.get("items", [])
            for item in items:
                full_name = item.get("full_name", "")
                if not full_name or full_name in self._seen_repos_set:
                    continue
                self._mark_repo_seen(full_name)

                parts = full_name.split("/", 1)
                repos.append(NewRepo(
                    owner=parts[0],
                    name=parts[1] if len(parts) > 1 else full_name,
                    url=item.get("html_url", f"https://github.com/{full_name}"),
                    default_branch=item.get("default_branch", "main"),
                    created_at=item.get("created_at", ""),
                    description=item.get("description") or "",
                ))

            # 不足100条说明没有更多结果
            if len(items) < 100:
                break

        return repos

    def mark_search_done(self):
        """搜索完成后由调用方调用，更新搜索时间戳（确保多关键词搜索共享同一时间窗口）"""
        self._last_search_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _should_skip_file(filename: str) -> bool:
        """检查文件是否应跳过扫描"""
        # 加前缀 / 确保匹配完整目录名，避免 "rebuild/" 误匹配 "build/"
        prefixed = f"/{filename}"
        if any(f"/{d}" in prefixed for d in SKIP_DIRS):
            return True
        lower = filename.lower()
        basename = lower.rsplit("/", 1)[-1]
        if basename in SKIP_FILENAMES:
            return True
        return any(lower.endswith(ext) for ext in SKIP_EXTENSIONS)

    # P0: 最可能含密钥的配置/环境文件
    _P0_NAMES = frozenset({
        ".env", ".env.local", ".env.production", ".env.development", ".env.staging",
        "appsettings.json", "appsettings.development.json", "appsettings.production.json",
        "config.json", "config.js", "config.ts", "config.py", "config.yaml", "config.yml",
        "settings.py", "secrets.json", "credentials.json",
        "application.properties", "application.yml", "application.yaml",
        "docker-compose.yml", "docker-compose.yaml",
    })

    # P1: 源代码扩展名（可能硬编码密钥）
    _P1_EXTENSIONS = frozenset({
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php",
        ".rs", ".cs", ".kt", ".swift", ".r", ".sh", ".bash", ".zsh",
        ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf",
        ".properties", ".xml",
    })

    @staticmethod
    def _file_priority(path: str) -> int:
        """文件扫描优先级：0=配置文件, 1=源代码, 2=其他"""
        name = path.rsplit("/", 1)[-1].lower()
        if name in GitHubClient._P0_NAMES:
            return 0
        if name.startswith(".env") or "secret" in name or "credential" in name:
            return 0
        # 提取扩展名，集合查找 O(1)
        dot = name.rfind(".")
        if dot >= 0 and name[dot:] in GitHubClient._P1_EXTENSIONS:
            return 1
        return 2

    async def get_repo_blobs(self, repo: NewRepo) -> list[str]:
        """获取仓库文件树，过滤+排序+分层限额，返回待扫描文件路径列表"""
        tree_url = (
            f"https://api.github.com/repos/{repo.owner}/{repo.name}"
            f"/git/trees/{repo.default_branch}?recursive=1"
        )
        status, _, data = await self._request_with_rotation(tree_url)
        if status != 200 or data is None:
            return []

        MAX_BLOB_SIZE = 500_000
        # 按优先级分桶
        buckets: dict[int, list[str]] = {0: [], 1: [], 2: []}
        for item in data.get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            size = item.get("size", 0)
            if self._should_skip_file(path) or size > MAX_BLOB_SIZE or size == 0:
                continue
            p = self._file_priority(path)
            buckets[p].append(path)

        # 分层限额：P0 最多100, P1 最多60, P2 最多10，总计硬限制 150
        MAX_TOTAL = 150
        result = buckets[0][:100] + buckets[1][:60] + buckets[2][:10]
        return result[:MAX_TOTAL]

    async def fetch_file_raw(self, repo: NewRepo, path: str, max_retries: int = 2) -> str | None:
        """下载单个文件内容（raw.githubusercontent.com，不消耗 API 配额）"""
        session = await self._get_session()
        raw_url = (
            f"https://raw.githubusercontent.com/{repo.owner}/{repo.name}"
            f"/{repo.default_branch}/{path}"
        )
        for attempt in range(max_retries):
            try:
                async with session.get(raw_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="ignore")
                    if resp.status in (404, 451):
                        return None
                    # 5xx 等可重试状态
            except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError):
                pass
            if attempt < max_retries - 1:
                await asyncio.sleep(0.3)
        return None

    async def fetch_repo_info(self, owner: str, name: str) -> dict | None:
        """获取仓库元信息（description, fork, language 等）。
        GET /repos/{owner}/{name} — 消耗 1 次配额。
        """
        url = f"https://api.github.com/repos/{owner}/{name}"
        status, _, data = await self._request_with_rotation(url, max_retries=1)
        if status == 200 and data:
            return data
        return None

    async def batch_fetch_repo_info(
        self, repos: list[NewRepo], concurrency: int = 10,
    ) -> dict[str, str]:
        """批量获取仓库描述。返回 {full_name: description}。"""
        sem = asyncio.Semaphore(concurrency)
        results: dict[str, str] = {}

        async def _fetch_one(repo: NewRepo):
            async with sem:
                info = await self.fetch_repo_info(repo.owner, repo.name)
                if info:
                    results[f"{repo.owner}/{repo.name}"] = info.get("description") or ""

        await asyncio.gather(
            *[_fetch_one(r) for r in repos],
            return_exceptions=True,
        )
        return results

    @property
    def total_core_remaining(self) -> int:
        """所有有效 Token 的 Core 配额剩余总和"""
        now = int(time.time())
        for ts in self._tokens:
            if ts.valid and ts.reset_at and now >= ts.reset_at:
                ts.remaining = 5000
                ts.reset_at = now + 3600
        return sum(ts.remaining for ts in self._tokens if ts.valid)

    @property
    def last_search_time(self) -> str:
        return self._last_search_time

    @property
    def events_etag(self) -> str:
        return self._events_etag

    @property
    def events_last_id(self) -> str:
        return self._events_last_id

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def restore_state(self, last_search_time: str,
                      events_etag: str = "", events_last_id: str = ""):
        if last_search_time:
            self._last_search_time = last_search_time
        if events_etag:
            self._events_etag = events_etag
        if events_last_id:
            self._events_last_id = events_last_id
