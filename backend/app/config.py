from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "OpportunityRadar"
    debug: bool = False

    supabase_jwt_secret: str
    admin_user_ids: list[str] = []
    auto_create_tables: bool = True

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"

    sendgrid_api_key: Optional[str] = None
    from_email: str = "hello@opportunityradar.com"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str

    scraper_internshala_enabled: bool = True
    scraper_linkedin_enabled: bool = True
    scraper_wellfound_enabled: bool = True
    scraper_interval_hours: int = 6

    digest_day: str = "sunday"
    digest_time: str = "10:00"
    digest_timezone: str = "UTC"

    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    @property
    def allowed_origins(self) -> list[str]:
        return list(dict.fromkeys([*self.cors_origins, self.frontend_url.rstrip("/")]))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
