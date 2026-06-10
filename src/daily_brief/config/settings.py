from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from daily_brief.config.paths import daily_brief_home, resolve_under_home

_ENV_FILE = ".env"


def _rebase_sqlite_url(url: str, home: Path) -> str:
    prefix = "sqlite:///"
    if url.startswith(prefix):
        db_path = Path(url.removeprefix(prefix))
        if not db_path.is_absolute():
            return prefix + str(resolve_under_home(db_path, home))
    return url


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    raise TypeError(f"Unsupported list value: {type(value)!r}")


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=_ENV_FILE,
        extra="ignore",
        populate_by_name=True,
    )

    env: str = "local"
    timezone: str = "America/New_York"
    digest_hour: int = 8
    digest_minute: int = 0
    max_items: int = 10
    scheduler_misfire_grace_seconds: int = 1800
    fetch_retries: int = 2
    send_retries: int = 1


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    url: str = Field(default="sqlite:///var/daily_brief.db", alias="DATABASE_URL")
    raw_payload_dir: Path = Field(default=Path("var/raw"), alias="RAW_PAYLOAD_DIR")
    outbox_dir: Path = Field(default=Path("var/outbox"), alias="OUTBOX_DIR")


class LoggingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    level: str = Field(default="INFO", alias="LOG_LEVEL")
    json_logs: bool = Field(default=True, alias="LOG_JSON")


class HttpConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    max_retries: int = Field(default=2, alias="HTTP_MAX_RETRIES")
    user_agent: str = Field(default="daily-brief-agent/0.1", alias="HTTP_USER_AGENT")
    persist_raw_payloads: bool = Field(default=False, alias="HTTP_PERSIST_RAW_PAYLOADS")


class FileSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=True, alias="SOURCE_FILE_ENABLED")
    path: Path = Field(default=Path("data/sample_brief_items.json"), alias="SOURCE_FILE_PATH")


class ArxivSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="SOURCE_ARXIV_ENABLED")
    categories: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["cs.AI", "cs.LG"],
        alias="SOURCE_ARXIV_CATEGORIES",
    )
    keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="SOURCE_ARXIV_KEYWORDS"
    )
    max_results: int = Field(default=10, alias="SOURCE_ARXIV_MAX_RESULTS")

    @field_validator("categories", "keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class GitHubSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="SOURCE_GITHUB_ENABLED")
    tracked_repos: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        alias="SOURCE_GITHUB_TRACKED_REPOS",
    )
    keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="SOURCE_GITHUB_KEYWORDS"
    )
    events_per_repo: int = Field(default=5, alias="SOURCE_GITHUB_EVENTS_PER_REPO")
    token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    @field_validator("tracked_repos", "keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class GitHubTrendingSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="SOURCE_GITHUB_TRENDING_ENABLED")
    keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="SOURCE_GITHUB_TRENDING_KEYWORDS"
    )
    max_results: int = Field(default=3, alias="SOURCE_GITHUB_TRENDING_MAX_RESULTS")
    token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    @field_validator("keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class HackerNewsSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="SOURCE_HN_ENABLED")
    story_lists: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["top", "new"],
        alias="SOURCE_HN_LISTS",
    )
    keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="SOURCE_HN_KEYWORDS"
    )
    max_stories: int = Field(default=20, alias="SOURCE_HN_MAX_STORIES")

    @field_validator("story_lists", "keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class RssSourceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="SOURCE_RSS_ENABLED")
    feeds: Annotated[list[str], NoDecode] = Field(default_factory=list, alias="SOURCE_RSS_FEEDS")
    keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="SOURCE_RSS_KEYWORDS"
    )
    max_items_per_feed: int = Field(default=10, alias="SOURCE_RSS_MAX_ITEMS_PER_FEED")

    @field_validator("feeds", "keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class SourceConfig(BaseModel):
    file: FileSourceConfig = Field(default_factory=FileSourceConfig)
    arxiv: ArxivSourceConfig = Field(default_factory=ArxivSourceConfig)
    github: GitHubSourceConfig = Field(default_factory=GitHubSourceConfig)
    github_trending: GitHubTrendingSourceConfig = Field(default_factory=GitHubTrendingSourceConfig)
    hackernews: HackerNewsSourceConfig = Field(default_factory=HackerNewsSourceConfig)
    rss: RssSourceConfig = Field(default_factory=RssSourceConfig)


class SummarizerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    provider: str = Field(default="extractive", alias="SUMMARIZER_PROVIDER")
    max_items: int = Field(default=5, alias="SUMMARIZER_MAX_ITEMS")
    model: str = Field(default="gpt-4o-mini", alias="SUMMARIZER_MODEL")
    base_url: str = Field(default="https://api.openai.com/v1", alias="SUMMARIZER_BASE_URL")
    api_key: str | None = Field(default=None, alias="SUMMARIZER_API_KEY")
    temperature: float = Field(default=0.2, alias="SUMMARIZER_TEMPERATURE")
    request_timeout_seconds: float = Field(default=30.0, alias="SUMMARIZER_REQUEST_TIMEOUT_SECONDS")


class RankingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    recency_weight: float = Field(default=0.3, alias="RANKING_RECENCY_WEIGHT")
    engagement_weight: float = Field(default=0.15, alias="RANKING_ENGAGEMENT_WEIGHT")
    source_quality_weight: float = Field(default=0.2, alias="RANKING_SOURCE_QUALITY_WEIGHT")
    keyword_affinity_weight: float = Field(default=0.2, alias="RANKING_KEYWORD_AFFINITY_WEIGHT")
    topic_affinity_weight: float = Field(default=0.15, alias="RANKING_TOPIC_AFFINITY_WEIGHT")
    title_similarity_threshold: float = Field(
        default=0.92, alias="RANKING_TITLE_SIMILARITY_THRESHOLD"
    )
    max_items_per_topic: int = Field(default=5, alias="RANKING_MAX_ITEMS_PER_TOPIC")
    max_total_items: int = Field(default=15, alias="RANKING_MAX_TOTAL_ITEMS")
    priority_keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "llm",
            "reasoning",
            "agents",
            "inference",
            "alignment",
            "benchmark",
        ],
        alias="RANKING_PRIORITY_KEYWORDS",
    )
    grad_keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "phd",
            "graduate",
            "grad school",
            "statement of purpose",
            "admission",
        ],
        alias="RANKING_GRAD_KEYWORDS",
    )
    sports_keywords: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["nba", "warriors", "lakers", "playoffs", "finals"],
        alias="RANKING_SPORTS_KEYWORDS",
    )

    @field_validator("priority_keywords", "grad_keywords", "sports_keywords", mode="before")
    @classmethod
    def parse_lists(cls, value: Any) -> list[str]:
        return _parse_list(value)


class EmailConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    provider: str = Field(default="console", alias="EMAIL_PROVIDER")
    sender: str = Field(default="daily-brief@example.com", alias="EMAIL_FROM")
    recipients: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["you@example.com"], alias="EMAIL_TO"
    )
    subject_prefix: str = Field(default="[Daily Brief]", alias="EMAIL_SUBJECT_PREFIX")
    preview_before_send: bool = Field(default=True, alias="EMAIL_PREVIEW_BEFORE_SEND")
    reply_to: str | None = Field(default=None, alias="EMAIL_REPLY_TO")
    gmail_credentials_file: Path = Field(
        default=Path("credentials.json"), alias="GMAIL_CREDENTIALS_FILE"
    )
    gmail_token_file: Path = Field(default=Path("var/gmail_token.json"), alias="GMAIL_TOKEN_FILE")
    gmail_user_id: str = Field(default="me", alias="GMAIL_USER_ID")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    @field_validator("recipients", mode="before")
    @classmethod
    def parse_recipients(cls, value: Any) -> list[str]:
        return _parse_list(value)


class FeishuConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="FEISHU_ENABLED")
    webhook_url: str | None = Field(default=None, alias="FEISHU_WEBHOOK_URL")
    secret: str | None = Field(default=None, alias="FEISHU_SECRET")
    message_type: str = Field(default="interactive", alias="FEISHU_MESSAGE_TYPE")


class WorkflowConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", populate_by_name=True)

    artifact_root: Path = Field(default=Path("runs"), alias="WORKFLOW_ARTIFACT_ROOT")
    checkpoint_enabled: bool = Field(default=True, alias="WORKFLOW_CHECKPOINT_ENABLED")
    checkpoint_path: Path = Field(
        default=Path("runs/checkpoints/workflow.pkl"),
        alias="WORKFLOW_CHECKPOINT_PATH",
    )
    candidate_limit: int = Field(default=12, alias="WORKFLOW_CANDIDATE_LIMIT")
    min_selected_items: int = Field(default=4, alias="WORKFLOW_MIN_SELECTED_ITEMS")
    max_selected_items: int = Field(default=8, alias="WORKFLOW_MAX_SELECTED_ITEMS")
    include_threshold: float = Field(default=0.62, alias="WORKFLOW_INCLUDE_THRESHOLD")
    fallback_include_threshold: float = Field(
        default=0.48, alias="WORKFLOW_FALLBACK_INCLUDE_THRESHOLD"
    )
    planning_min_sections: int = Field(default=2, alias="WORKFLOW_PLANNING_MIN_SECTIONS")
    planning_max_sections: int = Field(default=4, alias="WORKFLOW_PLANNING_MAX_SECTIONS")
    llm_max_retries: int = Field(default=2, alias="WORKFLOW_LLM_MAX_RETRIES")


class AppSettings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    source: SourceConfig = Field(default_factory=SourceConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    summarizer: SummarizerConfig = Field(default_factory=SummarizerConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> AppSettings:
        home = daily_brief_home()
        env_path = home / _ENV_FILE
        # Load the resolved home's .env so a pip/pipx install run from any
        # directory still picks up the user's configuration. Real environment
        # variables keep precedence (override=False).
        if env_path.is_file():
            load_dotenv(env_path, override=False)
        settings = cls(
            app=AppConfig(),
            database=DatabaseConfig(),
            logging=LoggingConfig(),
            http=HttpConfig(),
            source=SourceConfig(
                file=FileSourceConfig(),
                arxiv=ArxivSourceConfig(),
                github=GitHubSourceConfig(),
                github_trending=GitHubTrendingSourceConfig(),
                hackernews=HackerNewsSourceConfig(),
                rss=RssSourceConfig(),
            ),
            ranking=RankingConfig(),
            summarizer=SummarizerConfig(),
            email=EmailConfig(),
            feishu=FeishuConfig(),
            workflow=WorkflowConfig(),
        )
        settings._rebase_paths(home)
        return settings

    def _rebase_paths(self, home: Path) -> None:
        """Root relative local-state paths under ``home`` (absolute paths untouched)."""
        self.database.url = _rebase_sqlite_url(self.database.url, home)
        self.source.file.path = resolve_under_home(self.source.file.path, home)
        self.database.raw_payload_dir = resolve_under_home(self.database.raw_payload_dir, home)
        self.database.outbox_dir = resolve_under_home(self.database.outbox_dir, home)
        self.workflow.artifact_root = resolve_under_home(self.workflow.artifact_root, home)
        self.workflow.checkpoint_path = resolve_under_home(self.workflow.checkpoint_path, home)
        self.email.gmail_credentials_file = resolve_under_home(
            self.email.gmail_credentials_file, home
        )
        self.email.gmail_token_file = resolve_under_home(self.email.gmail_token_file, home)
