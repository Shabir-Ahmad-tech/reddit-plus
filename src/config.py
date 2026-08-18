import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RedditSettings(BaseSettings):
    client_id: str = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    client_secret: str = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    user_agent: str = Field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "RedditPlus/2.0"))
    subreddits: List[str] = Field(default_factory=lambda: ["all"])
    poll_interval_seconds: int = 600
    rate_limit_per_minute: int = 60

    @field_validator("subreddits", mode="before")
    @classmethod
    def parse_subreddits(cls, v):
        if isinstance(v, str):
            return [s.strip().lower().replace("r/", "") for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip().lower().replace("r/", "") for s in v if str(s).strip()]
        return ["all"]


class OpenCodeZenSettings(BaseSettings):
    enabled: bool = True
    base_url: str = Field(default_factory=lambda: os.getenv("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1"))
    api_key: str = Field(default_factory=lambda: os.getenv("OPENCODE_ZEN_API_KEY", os.getenv("LLM_API_KEY", "")))
    model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-v4-flash-free"))
    timeout_seconds: int = 60


class OllamaSettings(BaseSettings):
    host: str = Field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    timeout_seconds: int = 120
    intent_prompt: str = ""
    reply_prompt: str = ""


class LLMSettings(BaseSettings):
    provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "opencode_zen"))  # 'opencode_zen', 'ollama', 'auto'
    model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-v4-flash-free"))
    opencode_zen: OpenCodeZenSettings = Field(default_factory=OpenCodeZenSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)


class AlertSettings(BaseSettings):
    email: Optional[str] = Field(default_factory=lambda: os.getenv("ALERT_EMAIL"))
    sendgrid_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("SENDGRID_API_KEY"))
    from_email: str = Field(default_factory=lambda: os.getenv("FROM_EMAIL", "alerts@redditplus.local"))
    ntfy_topic: Optional[str] = Field(default_factory=lambda: os.getenv("NTFY_TOPIC"))
    ntfy_server: str = Field(default_factory=lambda: os.getenv("NTFY_SERVER", "https://ntfy.sh"))
    webhook_url: Optional[str] = Field(default_factory=lambda: os.getenv("WEBHOOK_URL"))
    min_intent_confidence: float = 0.65
    min_opportunity_score: int = 70
    tags_to_alert: List[str] = Field(
        default_factory=lambda: [
            "buy-intent",
            "pain-point",
            "competitor-complaint",
            "seeking-alternatives",
        ]
    )
    frequency: str = "immediate"  # 'immediate', 'hourly', 'daily'


class DatabaseSettings(BaseSettings):
    url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/data/reddit_plus.db"))
    echo: bool = False


class AppSettings(BaseSettings):
    app_name: str = "Reddit Plus"
    version: str = "2.0.0"
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"))
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    reddit: RedditSettings = Field(default_factory=RedditSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings() -> Settings:
    """Load settings from environment and optional config.yaml defaults."""
    config_path = PROJECT_ROOT / "config.yaml"
    settings_obj = Settings()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_yaml = yaml.safe_load(f) or {}

            # Populate YAML defaults if environment variable wasn't explicitly supplied
            if "reddit" in raw_yaml and isinstance(raw_yaml["reddit"], dict):
                r_yaml = raw_yaml["reddit"]
                if not os.getenv("REDDIT_CLIENT_ID") and "client_id" in r_yaml:
                    settings_obj.reddit.client_id = r_yaml["client_id"] or ""
                if not os.getenv("REDDIT_CLIENT_SECRET") and "client_secret" in r_yaml:
                    settings_obj.reddit.client_secret = r_yaml["client_secret"] or ""
                if "subreddits" in r_yaml and r_yaml["subreddits"]:
                    settings_obj.reddit.subreddits = RedditSettings.parse_subreddits(r_yaml["subreddits"])

            if "llm" in raw_yaml and isinstance(raw_yaml["llm"], dict):
                l_yaml = raw_yaml["llm"]
                if "provider" in l_yaml:
                    settings_obj.llm.provider = l_yaml["provider"]
                if "opencode_zen" in l_yaml and isinstance(l_yaml["opencode_zen"], dict):
                    zen_yaml = l_yaml["opencode_zen"]
                    if not os.getenv("OPENCODE_ZEN_API_KEY") and not os.getenv("LLM_API_KEY"):
                        # Never load hardcoded keys from defaults if placeholder
                        key = zen_yaml.get("api_key", "")
                        if key and not key.startswith("your_") and not key.startswith("sk-j96h"):
                            settings_obj.llm.opencode_zen.api_key = key
                    if "model" in zen_yaml:
                        settings_obj.llm.opencode_zen.model = zen_yaml["model"]

            if "alerts" in raw_yaml and isinstance(raw_yaml["alerts"], dict):
                a_yaml = raw_yaml["alerts"]
                if not os.getenv("NTFY_TOPIC") and "ntfy_topic" in a_yaml:
                    settings_obj.alerts.ntfy_topic = a_yaml["ntfy_topic"]
                if not os.getenv("ALERT_EMAIL") and "email" in a_yaml:
                    settings_obj.alerts.email = a_yaml["email"]
                if "min_confidence" in a_yaml:
                    settings_obj.alerts.min_intent_confidence = float(a_yaml["min_confidence"])
                if "tags" in a_yaml and a_yaml["tags"]:
                    settings_obj.alerts.tags_to_alert = a_yaml["tags"]
        except Exception:
            pass

    return settings_obj


settings = load_settings()