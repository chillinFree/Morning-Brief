from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunTable(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    force_send: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)


class BriefItemTable(Base):
    __tablename__ = "brief_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    url: Mapped[str] = mapped_column(Text(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_short: Mapped[str | None] = mapped_column(Text(), nullable=True)
    fingerprint_exact: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float(), nullable=True)


class DigestTable(Base):
    __tablename__ = "digests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text(), nullable=False)
    html_body: Mapped[str] = mapped_column(Text(), nullable=False)
    text_body: Mapped[str] = mapped_column(Text(), nullable=False)


class DeliveryTable(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient: Mapped[str] = mapped_column(String(256), nullable=False)
    external_id: Mapped[str] = mapped_column(Text(), nullable=False)
