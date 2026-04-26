"""
会话持久化存储 — JSON 文件

每个会话保存为独立的 JSON 文件:
  {WORKSPACE_DIR}/sessions/{session_id}.json
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class SessionStoreError(Exception):
    pass


class SessionStore:
    """JSON 文件会话存储"""

    def __init__(self, workspace_dir: str):
        self._sessions_dir = os.path.join(workspace_dir, "sessions")
        os.makedirs(self._sessions_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self._sessions_dir, f"{session_id}.json")

    # ── CRUD ──

    def list_sessions(self, user_id: str = "", limit: int = 50) -> list[dict]:
        """列出会话摘要 (按 updated_at 降序)"""
        sessions = []
        for fname in os.listdir(self._sessions_dir):
            if not fname.endswith(".json"):
                continue
            sid = fname[:-5]
            try:
                data = self._read_safe(sid)
                if not data:
                    continue
                if user_id and data.get("user_id") != user_id:
                    continue
                sessions.append({
                    "session_id": sid,
                    "name": data.get("name", "新对话"),
                    "user_id": data.get("user_id", ""),
                    "channel": data.get("channel", "console"),
                    "message_count": len(data.get("messages", [])),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                })
            except Exception as e:
                logger.debug("读取会话 %s 失败: %s", sid, e)
                continue

        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions[:limit]

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取完整会话 (含消息)"""
        return self._read_safe(session_id)

    def create_session(self, session_id: str, user_id: str = "",
                       channel: str = "console", name: str = "新对话") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "name": name,
            "user_id": user_id,
            "channel": channel,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        self._write(session_id, data)
        return data

    def update_session(self, session_id: str, updates: dict) -> Optional[dict]:
        data = self._read_safe(session_id)
        if not data:
            return None
        data.update(updates)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(session_id, data)
        return data

    def delete_session(self, session_id: str) -> bool:
        path = self._path(session_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    # ── 消息操作 ──

    def add_message(self, session_id: str, role: str, content: str,
                    metadata: dict = None) -> Optional[dict]:
        data = self._read_safe(session_id)
        if not data:
            return None
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            msg["metadata"] = metadata
        data.setdefault("messages", []).append(msg)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(session_id, data)
        return msg

    def get_messages(self, session_id: str) -> list[dict]:
        data = self._read_safe(session_id)
        return data.get("messages", []) if data else []

    def clear_messages(self, session_id: str) -> bool:
        data = self._read_safe(session_id)
        if not data:
            return False
        data["messages"] = []
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(session_id, data)
        return True

    # ── 内部 ──

    def _read_safe(self, session_id: str) -> Optional[dict]:
        path = self._path(session_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取会话文件 %s 失败: %s", path, e)
            return None

    def _write(self, session_id: str, data: dict):
        path = self._path(session_id)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError as e:
            raise SessionStoreError(f"写入会话文件失败: {e}") from e
