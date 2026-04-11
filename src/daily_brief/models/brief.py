from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl

SourceType = Literal["paper", "repo", "post", "thread", "news", "forum_post", "sports_update"]


class Engagement(BaseModel):
    score: float | None = None
    stars: int | None = None
    comments: int | None = None
    likes: int | None = None
    reposts: int | None = None


class BriefItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str | None = None
    source: str
    source_item_id: str | None = None
    source_type: SourceType
    title: str
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_text: str | None = None
    content_html: str | None = None
    summary_short: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    language: str | None = "en"
    engagement: Engagement = Field(default_factory=Engagement)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_ref: str | None = None
    fingerprint_exact: str = ""
    fingerprint_fuzzy: str | None = None
    embedding_ref: str | None = None
    relevance_score: float | None = None
    importance_score: float | None = None
    novelty_score: float | None = None
    final_score: float | None = None
    why_it_matters: str | None = None
    cluster_id: str | None = None
    section: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.canonical_url:
            self.canonical_url = self.url
        if not self.fingerprint_exact:
            self.fingerprint_exact = self.compute_fingerprint()

    def compute_fingerprint(self) -> str:
        value = f"{str(self.canonical_url or self.url).lower()}::{self.title.strip().lower()}"
        return sha256(value.encode("utf-8")).hexdigest()
