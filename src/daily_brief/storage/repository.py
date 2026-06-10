from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from daily_brief.models.brief import BriefItem
from daily_brief.models.digest import Digest
from daily_brief.models.run import RunRecord
from daily_brief.storage.models import BriefItemTable, DeliveryTable, DigestTable, RunTable


class BriefRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, run: RunRecord) -> None:
        self._session.add(
            RunTable(
                id=run.id,
                target_date=run.target_date,
                timezone_name=run.timezone_name,
                mode=run.mode,
                dry_run=run.dry_run,
                force_send=run.force_send,
                started_at=run.started_at,
                completed_at=run.completed_at,
                status=run.status,
                item_count=run.item_count,
                error_message=run.error_message,
            )
        )

    def complete_run(self, run: RunRecord) -> None:
        record = self._session.get(RunTable, run.id)
        if record is None:
            raise ValueError(f"Run not found: {run.id}")
        record.target_date = run.target_date
        record.timezone_name = run.timezone_name
        record.mode = run.mode
        record.dry_run = run.dry_run
        record.force_send = run.force_send
        record.completed_at = run.completed_at
        record.status = run.status
        record.item_count = run.item_count
        record.error_message = run.error_message

    def save_items(self, items: list[BriefItem]) -> None:
        for item in items:
            self._session.add(
                BriefItemTable(
                    id=item.id,
                    run_id=item.run_id or "",
                    source=item.source,
                    source_type=item.source_type,
                    title=item.title,
                    url=str(item.url),
                    published_at=item.published_at,
                    summary_short=item.summary_short,
                    fingerprint_exact=item.fingerprint_exact,
                    section=item.section,
                    final_score=item.final_score,
                )
            )

    def save_digest(self, digest: Digest) -> None:
        self._session.add(
            DigestTable(
                id=digest.id,
                run_id=digest.run_id,
                subject=digest.subject,
                html_body=digest.html_body,
                text_body=digest.text_body,
            )
        )

    def save_delivery(self, run_id: str, provider: str, recipient: str, external_id: str) -> None:
        self._session.add(
            DeliveryTable(
                run_id=run_id,
                provider=provider,
                recipient=recipient,
                external_id=external_id,
            )
        )

    def has_sent_for_date(self, target_date: date, timezone_name: str) -> bool:
        statement = (
            select(RunTable.id)
            .join(DeliveryTable, DeliveryTable.run_id == RunTable.id)
            .where(
                RunTable.target_date == target_date,
                RunTable.timezone_name == timezone_name,
                RunTable.status == "completed",
                RunTable.dry_run.is_(False),
            )
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none() is not None

    def list_runs(self, limit: int = 20) -> list[RunTable]:
        statement = select(RunTable).order_by(RunTable.started_at.desc()).limit(limit)
        return list(self._session.execute(statement).scalars())

    def get_run(self, run_id: str) -> RunTable | None:
        return self._session.get(RunTable, run_id)

    def get_digest_by_run(self, run_id: str) -> DigestTable | None:
        statement = select(DigestTable).where(DigestTable.run_id == run_id).limit(1)
        return self._session.execute(statement).scalar_one_or_none()

    def latest_run_with_digest(self) -> RunTable | None:
        statement = (
            select(RunTable)
            .join(DigestTable, DigestTable.run_id == RunTable.id)
            .where(RunTable.status == "completed")
            .order_by(RunTable.started_at.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()
