from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"))

    database_url: str = "sqlite+aiosqlite:///./data/keyleaks.db"
    github_tokens: str = ""  # 逗号分隔的多个 GitHub Token
    poll_interval: int = 60  # seconds
    max_commits_per_event: int = 5
    api_page_size: int = 20

    # JWT 认证
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    # 管理员账号
    admin_username: str = "admin"
    admin_password: str = "admin123"

    @property
    def token_list(self) -> list[str]:
        """解析逗号分隔的 Token 列表，过滤空值"""
        if not self.github_tokens:
            return []
        return [t.strip() for t in self.github_tokens.split(",") if t.strip()]


settings = Settings()
