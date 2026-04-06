import datetime

from pydantic import BaseModel, ConfigDict


class LeakResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    raw_key: str
    repo_url: str
    repo_owner: str
    repo_name: str
    file_path: str
    leak_introduced_at: datetime.datetime | None
    leak_detected_at: datetime.datetime
    key_status: str = "unchecked"
    validated_at: datetime.datetime | None = None
    verified_provider: str = ""
    verified_url: str = ""


class LeakListResponse(BaseModel):
    leaks: list[LeakResponse]
    total: int
    has_more: bool


class StatsResponse(BaseModel):
    total_leaks: int
    today_leaks: int
    total_repos: int
    total_events_scanned: int
    total_repos_scanned: int


class WeeklyItem(BaseModel):
    date: str
    count: int


class LeaderboardItem(BaseModel):
    repo_owner: str
    leak_count: int


class ProviderDailyItem(BaseModel):
    date: str
    provider: str
    count: int


class BalanceInfo(BaseModel):
    currency: str
    total_balance: str
    granted_balance: str
    topped_up_balance: str


class BalanceResponse(BaseModel):
    is_available: bool
    balance_infos: list[BalanceInfo]


class ValidateResultSummary(BaseModel):
    valid: int = 0
    invalid: int = 0
    unchecked: int = 0


class ValidateAllResponse(BaseModel):
    validated: int
    results: ValidateResultSummary
