import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Leak(Base):
    __tablename__ = "leaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    raw_key: Mapped[str] = mapped_column(String(512))
    repo_url: Mapped[str] = mapped_column(String(512))
    repo_owner: Mapped[str] = mapped_column(String(128), index=True)
    repo_name: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(String(512))
    leak_introduced_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    leak_detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now()
    )
    key_status: Mapped[str] = mapped_column(
        String(16), default="unchecked", server_default="unchecked"
    )
    validated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    verified_provider: Mapped[str] = mapped_column(
        String(32), default="", server_default=""
    )
    verified_url: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )

    __table_args__ = (
        Index("ix_leaks_detected", "leak_detected_at"),
        Index("ix_leaks_repo_owner_name", "repo_owner", "repo_name"),
    )


class ScanState(Base):
    __tablename__ = "scan_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_event_id: Mapped[str] = mapped_column(String(64), default="")
    etag: Mapped[str] = mapped_column(String(128), default="")
    last_event_id_events: Mapped[str] = mapped_column(String(64), default="")
    total_events_scanned: Mapped[int] = mapped_column(Integer, default=0)
    total_commits_scanned: Mapped[int] = mapped_column(Integer, default=0)


class MonitoredRepo(Base):
    """首次扫描未发现 key 的 AI 相关仓库，持续监控 24 小时"""
    __tablename__ = "monitored_repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(384), unique=True)
    repo_url: Mapped[str] = mapped_column(String(512))
    default_branch: Mapped[str] = mapped_column(String(64), default="main")
    description: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[str] = mapped_column(String(32), default="")
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now()
    )
    last_scanned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now()
    )
    scan_count: Mapped[int] = mapped_column(Integer, default=1)
    has_leak: Mapped[int] = mapped_column(Integer, default=0)
