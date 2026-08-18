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
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = "ParseStream-Free/1.0"
    subreddits: List[str] = Field(default_factory=lambda: ["all"])

    @field_validator("subreddits", mode="before")
    @classmethod
    def parse_subreddits(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or ["all"]


class HackerNewsSettings(BaseSettings):
    enabled: bool = True
    base_url: str = "https://hacker-news.firebaseio.com/v0"


class OpenCodeZenSettings(BaseSettings):
    enabled: bool = True
    base_url: str = "https://opencode.ai/zen/v1"
    api_key: str = "sk-j96hBGcr8kZU2iwLohSWnMaCuIAmWpDp8IZN59wnp6RFnyFMEomHIpVDgTWia57y"
    model: str = "deepseek-v4-flash-free"
    timeout_seconds: int = 60


class OllamaSettings(BaseSettings):
    host: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    timeout_seconds: int = 120
    intent_prompt: str = ""
    reply_prompt: str = ""


class LLMSettings(BaseSettings):
    provider: str = "opencode_zen"  # 'opencode_zen', 'ollama', 'auto'
    model: str = "deepseek-v4-flash-free"
    opencode_zen: OpenCodeZenSettings = Field(default_factory=OpenCodeZenSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    intent_prompt: str = ""
    reply_prompt: str = ""


class SendGridSettings(BaseSettings):
    api_key: str = ""
    from_email: str = ""
    to_email: str = ""


class NtfySettings(BaseSettings):
    topic: str = ""
    server: str = "https://ntfy.sh"


class AlertSettings(BaseSettings):
    sendgrid: SendGridSettings = Field(default_factory=SendGridSettings)
    ntfy: NtfySettings = Field(default_factory=NtfySettings)
    min_confidence: float = 0.7
    alert_tags: List[str] = Field(default_factory=lambda: ["buy-intent", "pain-point", "competitor-complaint"])
    digest_frequency: str = "hourly"


class AppSettings(BaseSettings):
    poll_interval_minutes: int = 15
    process_interval_minutes: int = 5
    max_mentions_per_poll: int = 50
    database_path: str = "data/parsestream.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    reddit: RedditSettings = Field(default_factory=RedditSettings)
    hackernews: HackerNewsSettings = Field(default_factory=HackerNewsSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Settings":
        config_file = Path(path)
        if not config_file.exists():
            config_file = PROJECT_ROOT / path

        data = {}
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as e:
                data = {}

        # Expand environment variables in string values
        def expand_env(obj):
            if isinstance(obj, str):
                return os.path.expandvars(obj)
            elif isinstance(obj, dict):
                return {k: expand_env(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [expand_env(item) for item in obj]
            return obj

        data = expand_env(data)
        return cls(**data)


# Global settings instance
settings = Settings.from_yaml()