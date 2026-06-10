from __future__ import annotations

import json
import logging
import re
import smtplib
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from html import unescape
from typing import Any, Literal

import httpx
from pydantic import ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from daily_brief.aggregation.dedup import deduplicate_items
from daily_brief.aggregation.diversity import interleave_by_key, source_channel
from daily_brief.aggregation.explanations import explain_why_it_matters
from daily_brief.aggregation.ranking import score_items
from daily_brief.aggregation.topicing import TOPIC_GENERAL, assign_topic
from daily_brief.config.settings import RankingConfig
from daily_brief.delivery.subject import generate_subject_line
from daily_brief.graph.context import WorkflowDependencies
from daily_brief.graph.state import DeliveryResult, MorningBriefState, StageTrace
from daily_brief.llm.extractive import ExtractiveWorkflowReasoner
from daily_brief.llm.schemas import EditorialPlan, ItemEvaluation, SectionPlan, SectionSummary
from daily_brief.models.brief import BriefItem
from daily_brief.models.briefing import BriefSection, DailyBrief
from daily_brief.rendering.markdown import render_markdown_brief
from daily_brief.rendering.renderer import render_digest
from daily_brief.sources.base import SourceFetchContext

logger = logging.getLogger(__name__)

StageWork = Callable[[], tuple[dict[str, Any], dict[str, Any]]]

_LOW_SIGNAL_MARKERS = {
    "who is hiring",
    "who wants to be hired",
    "weekly discussion",
    "monthly discussion",
}


class MorningBriefNodes:
    def __init__(self, dependencies: WorkflowDependencies) -> None:
        self._dependencies = dependencies
        self._fallback_reasoner = ExtractiveWorkflowReasoner()

    def ingest_sources(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            context = SourceFetchContext(
                run_id=state["run_id"],
                max_items=self._dependencies.settings.app.max_items,
                raw_payload_dir=self._dependencies.settings.database.raw_payload_dir,
                persist_raw_payloads=self._dependencies.settings.http.persist_raw_payloads,
            )
            items = self._fetch_items(context)
            for item in items:
                item.run_id = state["run_id"]
            update = {"ingested_items": items}
            snapshot = {
                "run_id": state["run_id"],
                "item_count": len(items),
                "sources": sorted({item.source for item in items}),
                "items": items,
            }
            return update, snapshot

        return self._run_stage(state, "ingest_sources", work)

    def clean_and_dedup(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            cleaned: list[BriefItem] = []
            rejected: list[BriefItem] = []
            for item in state.get("ingested_items", []):
                normalized = _normalize_item_text(item)
                if _is_low_quality(normalized):
                    rejected.append(normalized)
                    continue
                cleaned.append(normalized)

            dedupe_result = deduplicate_items(cleaned, self._dependencies.settings.ranking)
            update = {
                "cleaned_items": dedupe_result.items,
                "rejected_items": rejected,
                "dedupe_clusters": dedupe_result.clusters,
            }
            snapshot = {
                "run_id": state["run_id"],
                "input_count": len(state.get("ingested_items", [])),
                "rejected_count": len(rejected),
                "cleaned_count": len(cleaned),
                "deduped_count": len(dedupe_result.items),
                "duplicate_cluster_count": len(
                    [cluster for cluster in dedupe_result.clusters if cluster.duplicates]
                ),
                "rejected_items": rejected,
                "deduped_items": dedupe_result.items,
            }
            return update, snapshot

        return self._run_stage(state, "clean_and_dedup", work)

    def lightweight_rank(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            scored = score_items(
                state.get("cleaned_items", []),
                self._dependencies.settings.ranking,
            )
            limit = min(
                self._dependencies.settings.workflow.candidate_limit,
                max(len(scored), 1),
            )
            # Keep the candidate pool balanced across sources (round-robin) so
            # downstream evaluation/selection can build a multi-source brief
            # instead of an arXiv-only candidate list.
            candidates = interleave_by_key(
                scored,
                key=source_channel,
                limit=limit,
            )
            update = {"candidate_items": candidates}
            snapshot = {
                "run_id": state["run_id"],
                "candidate_limit": limit,
                "scored_count": len(scored),
                "candidate_count": len(candidates),
                "top_candidates": [
                    {
                        "item_id": item.id,
                        "title": item.title,
                        "source": item.source,
                        "final_score": item.final_score,
                        "section": item.section,
                    }
                    for item in candidates
                ],
            }
            return update, snapshot

        return self._run_stage(state, "lightweight_rank", work)

    def llm_evaluate_items(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            evaluations: list[ItemEvaluation] = []
            provider = self._dependencies.settings.summarizer.provider
            for item in state.get("candidate_items", []):
                def primary(current: BriefItem = item) -> ItemEvaluation:
                    return self._dependencies.reasoner.evaluate_item(current)

                def fallback(current: BriefItem = item) -> ItemEvaluation:
                    return self._fallback_reasoner.evaluate_item(current)

                evaluation = self._reason_with_fallback(
                    primary,
                    fallback,
                )
                evaluations.append(evaluation)
            update = {"item_evaluations": evaluations}
            snapshot = {
                "run_id": state["run_id"],
                "provider": provider,
                "evaluation_count": len(evaluations),
                "evaluations": evaluations,
            }
            return update, snapshot

        return self._run_stage(state, "llm_evaluate_items", work)

    def select_items(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            threshold = self._dependencies.settings.workflow.include_threshold
            selected, rejected = _select_items_from_evaluations(
                items=state.get("candidate_items", []),
                evaluations=state.get("item_evaluations", []),
                threshold=threshold,
                limit=self._dependencies.settings.workflow.max_selected_items,
            )
            # The graph uses this flag to decide whether to take the fallback branch.
            needs_fallback = len(selected) < self._dependencies.settings.workflow.min_selected_items
            update = {
                "selected_items": selected,
                "rejected_evaluations": rejected,
                "selection_threshold": threshold,
                "needs_fallback": needs_fallback,
                "fallback_used": False,
            }
            snapshot = {
                "run_id": state["run_id"],
                "threshold": threshold,
                "selected_count": len(selected),
                "min_required": self._dependencies.settings.workflow.min_selected_items,
                "needs_fallback": needs_fallback,
                "selected_items": selected,
                "rejected_evaluations": rejected,
            }
            return update, snapshot

        return self._run_stage(state, "select_items", work)

    def route_after_selection(self, state: MorningBriefState) -> Literal["relax_selection", "plan_brief"]:
        return "relax_selection" if state.get("needs_fallback", False) else "plan_brief"

    def relax_selection(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            threshold = self._dependencies.settings.workflow.fallback_include_threshold
            selected, _ = _select_items_from_evaluations(
                items=state.get("candidate_items", []),
                evaluations=state.get("item_evaluations", []),
                threshold=threshold,
                limit=self._dependencies.settings.workflow.max_selected_items,
                allow_include_override=True,
            )
            if len(selected) < self._dependencies.settings.workflow.min_selected_items:
                ranked_candidates = interleave_by_key(
                    sorted(
                        state.get("candidate_items", []),
                        key=lambda item: item.final_score or 0.0,
                        reverse=True,
                    ),
                    key=source_channel,
                )
                selected_ids = {item.id for item in selected}
                for item in ranked_candidates:
                    if item.id in selected_ids:
                        continue
                    selected.append(item)
                    selected_ids.add(item.id)
                    if len(selected) >= self._dependencies.settings.workflow.min_selected_items:
                        break
            selected = selected[: self._dependencies.settings.workflow.max_selected_items]
            update = {
                "selected_items": selected,
                "selection_threshold": threshold,
                "needs_fallback": False,
                "fallback_used": True,
            }
            snapshot = {
                "run_id": state["run_id"],
                "fallback_threshold": threshold,
                "selected_count": len(selected),
                "selected_items": selected,
            }
            return update, snapshot

        return self._run_stage(state, "relax_selection", work)

    def plan_brief(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            selected_items = state.get("selected_items", [])
            selected_evaluations = _selected_evaluations(selected_items, state.get("item_evaluations", []))
            plan = self._reason_with_fallback(
                lambda: self._dependencies.reasoner.plan_brief(
                    selected_items,
                    selected_evaluations,
                    self._dependencies.settings.workflow.planning_min_sections,
                    self._dependencies.settings.workflow.planning_max_sections,
                ),
                lambda: self._fallback_reasoner.plan_brief(
                    selected_items,
                    selected_evaluations,
                    self._dependencies.settings.workflow.planning_min_sections,
                    self._dependencies.settings.workflow.planning_max_sections,
                ),
            )
            plan = _sanitize_plan(plan, selected_items, self._dependencies.settings.workflow.planning_max_sections)
            update = {"editorial_plan": plan}
            snapshot = {
                "run_id": state["run_id"],
                "overview": plan.overview,
                "section_count": len(plan.sections),
                "sections": plan.sections,
            }
            return update, snapshot

        return self._run_stage(state, "plan_brief", work)

    def summarize_sections(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            selected_items = state.get("selected_items", [])
            evaluation_list = _selected_evaluations(selected_items, state.get("item_evaluations", []))
            sections: list[SectionSummary] = []
            items_by_id = {item.id: item for item in selected_items}
            for section in state.get("editorial_plan", EditorialPlan(overview="", sections=[])).sections:
                section_items = [items_by_id[item_id] for item_id in section.item_ids if item_id in items_by_id]
                def primary(
                    current_section: SectionPlan = section,
                    current_items: list[BriefItem] = section_items,
                ) -> SectionSummary:
                    return self._dependencies.reasoner.summarize_section(
                        current_section,
                        current_items,
                        evaluation_list,
                    )

                def fallback(
                    current_section: SectionPlan = section,
                    current_items: list[BriefItem] = section_items,
                ) -> SectionSummary:
                    return self._fallback_reasoner.summarize_section(
                        current_section,
                        current_items,
                        evaluation_list,
                    )

                section_summary = self._reason_with_fallback(
                    primary,
                    fallback,
                )
                sections.append(section_summary)
            update = {"section_summaries": sections}
            snapshot = {
                "run_id": state["run_id"],
                "section_summary_count": len(sections),
                "sections": sections,
            }
            return update, snapshot

        return self._run_stage(state, "summarize_sections", work)

    def render_markdown(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            selected_items = state.get("selected_items", [])
            evaluation_by_id = {
                evaluation.item_id: evaluation for evaluation in state.get("item_evaluations", [])
            }
            items_by_id = {item.id: item for item in selected_items}

            sections: list[BriefSection] = []
            for section_summary in state.get("section_summaries", []):
                section_items: list[BriefItem] = []
                for item_id in section_summary.item_ids:
                    item = items_by_id.get(item_id)
                    if item is None:
                        continue
                    evaluated = evaluation_by_id.get(item_id)
                    rendered_item = item.model_copy(deep=True)
                    rendered_item.section = section_summary.name
                    if evaluated is not None:
                        rendered_item.summary_short = rendered_item.summary_short or evaluated.main_idea
                        rendered_item.why_it_matters = evaluated.why_it_matters
                        rendered_item.importance_score = evaluated.importance_score
                        rendered_item.novelty_score = evaluated.novelty_score
                    section_items.append(rendered_item)
                sections.append(
                    BriefSection(
                        name=section_summary.name,
                        summary=section_summary.summary,
                        items=section_items,
                    )
                )

            overview = state.get("editorial_plan", EditorialPlan(overview="", sections=[])).overview
            provisional_subject = f"{state['subject_prefix']} {state['target_date'].isoformat()}"
            brief = DailyBrief(
                run_id=state["run_id"],
                subject=provisional_subject,
                overview=overview or "No notable updates were selected for this run.",
                sections=sections,
                markdown_body="",
            )
            subject = generate_subject_line(
                self._dependencies.settings.email.subject_prefix,
                brief,
                state["timezone_name"],
            )
            markdown = render_markdown_brief(subject, brief.overview, sections)
            brief = brief.model_copy(update={"subject": subject, "markdown_body": markdown})
            digest = render_digest(brief, state["timezone_name"])
            update = {"brief": brief, "digest": digest, "markdown_body": markdown}
            snapshot = {
                "run_id": state["run_id"],
                "subject": subject,
                "overview": brief.overview,
                "section_count": len(sections),
                "brief": brief,
            }
            return update, snapshot

        return self._run_stage(state, "render_markdown", work)

    def deliver_output(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            digest = state["digest"]
            results: list[DeliveryResult] = []
            for target in self._dependencies.senders:
                if state.get("dry_run", False):
                    preview_path = target.sender.preview(digest)
                    results.append(
                        DeliveryResult(
                            provider=target.provider,
                            status="previewed",
                            external_id="dry-run",
                            preview_path=preview_path,
                        )
                    )
                    continue
                try:
                    external_id = self._send_digest(target.sender.send, digest)
                except Exception as exc:  # noqa: BLE001 - one bad channel must not abort the run
                    # A failing channel (e.g. an unconfigured Feishu webhook)
                    # should not crash the whole run: the digest is still
                    # rendered, persisted, and shown on the dashboard, and other
                    # channels (console/outbox) still deliver.
                    logger.warning(
                        "delivery channel failed",
                        extra={
                            "run_id": state["run_id"],
                            "provider": target.provider,
                            "stage": "deliver_output",
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                    results.append(
                        DeliveryResult(
                            provider=target.provider,
                            status="failed",
                            external_id=None,
                        )
                    )
                    continue
                results.append(
                    DeliveryResult(
                        provider=target.provider,
                        status="sent",
                        external_id=external_id,
                    )
                )
            update = {"delivery_results": results}
            snapshot = {
                "run_id": state["run_id"],
                "dry_run": state.get("dry_run", False),
                "delivery_results": results,
            }
            return update, snapshot

        return self._run_stage(state, "deliver_output", work)

    def persist_artifacts(self, state: MorningBriefState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            # Persist a demo-friendly record of both intermediate state and final outputs.
            self._dependencies.artifact_store.save_json(
                "manifest.json",
                {
                    "run_id": state["run_id"],
                    "target_date": state["target_date"],
                    "timezone_name": state["timezone_name"],
                    "mode": state["mode"],
                    "dry_run": state["dry_run"],
                    "artifact_dir": state["artifact_dir"],
                },
            )
            self._dependencies.artifact_store.save_json("state.final.json", dict(state))
            if "brief" in state:
                self._dependencies.artifact_store.save_json("brief.json", state["brief"])
                self._dependencies.artifact_store.save_text("brief.md", state["brief"].markdown_body)
            if "digest" in state:
                self._dependencies.artifact_store.save_json("digest.json", state["digest"])
                self._dependencies.artifact_store.save_text("digest.html", state["digest"].html_body)
                self._dependencies.artifact_store.save_text("digest.txt", state["digest"].text_body)
            if "delivery_results" in state:
                self._dependencies.artifact_store.save_json(
                    "delivery_results.json", state["delivery_results"]
                )
            snapshot = {
                "run_id": state["run_id"],
                "artifact_dir": state["artifact_dir"],
                "stage_history": state.get("stage_history", []),
            }
            return {}, snapshot

        return self._run_stage(state, "persist_artifacts", work)

    def _run_stage(
        self,
        state: MorningBriefState,
        stage_name: str,
        work: StageWork,
    ) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        logger.info(
            "workflow stage started",
            extra={
                "run_id": state["run_id"],
                "stage": stage_name,
                "status": "started",
            },
        )
        try:
            update, snapshot = work()
        except Exception as exc:
            logger.exception(
                "workflow stage failed",
                extra={
                    "run_id": state["run_id"],
                    "stage": stage_name,
                    "status": "failed",
                },
            )
            self._dependencies.artifact_store.save_json(
                f"{stage_name}_error.json",
                {
                    "run_id": state["run_id"],
                    "stage": stage_name,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "state": dict(state),
                },
            )
            raise

        completed_at = datetime.now(UTC)
        trace = StageTrace(
            stage=stage_name,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            details=_snapshot_details(snapshot),
        )
        stage_history = state.get("stage_history", []) + [trace]
        merged_snapshot = {
            "stage": stage_name,
            "started_at": started_at,
            "completed_at": completed_at,
            "payload": snapshot,
            "stage_history_count": len(stage_history),
        }
        self._dependencies.artifact_store.save_stage(stage_name, merged_snapshot)
        logger.info(
            "workflow stage completed",
            extra={
                "run_id": state["run_id"],
                "stage": stage_name,
                "status": "completed",
            },
        )
        update["stage_history"] = stage_history
        return update

    def _fetch_items(self, context: SourceFetchContext) -> list[BriefItem]:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._dependencies.settings.app.fetch_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception(_is_retryable_fetch_error),
        )
        def run() -> list[BriefItem]:
            return self._dependencies.source.fetch(context)

        return run()

    def _send_digest(self, send: Callable[[Any], str], digest: Any) -> str:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._dependencies.settings.app.send_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception(_is_retryable_send_error),
        )
        def run() -> str:
            return send(digest)

        return run()

    def _reason_with_fallback(
        self,
        primary: Callable[[], Any],
        fallback: Callable[[], Any],
    ) -> Any:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self._dependencies.settings.workflow.llm_max_retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception(_is_retryable_llm_error),
        )
        def primary_call() -> Any:
            return primary()

        try:
            return primary_call()
        except Exception:
            logger.warning("falling back to extractive workflow reasoning")
            return fallback()


def _normalize_item_text(item: BriefItem) -> BriefItem:
    updates = {
        "title": " ".join(item.title.split()),
        "summary_short": _compact_optional(item.summary_short),
        "content_text": _compact_optional(item.content_text),
    }
    return item.model_copy(update=updates, deep=True)


def _is_low_quality(item: BriefItem) -> bool:
    normalized_title = item.title.lower().strip()
    if len(normalized_title) < 8:
        return True
    if normalized_title in {"[deleted]", "[dead]"}:
        return True
    return any(marker in normalized_title for marker in _LOW_SIGNAL_MARKERS)


_BLOCK_TAG_RE = re.compile(r"(?i)</(?:p|div|br|li|h[1-6]|tr)\s*>|<br\s*/?>")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    # Feeds (HN, X/Twitter, RSS) embed HTML in item bodies. Convert block-level
    # tags to spaces, drop the rest, then unescape entities so the brief reads
    # as clean prose instead of leaking markup like <p>, <br>, &gt;, &#x2F;.
    text = _BLOCK_TAG_RE.sub(" ", value)
    text = _HTML_TAG_RE.sub("", text)
    return unescape(text)


def _compact_optional(value: str | None) -> str | None:
    if value is None:
        return None
    compacted = " ".join(_strip_html(value).split())
    return compacted[:600] if compacted else None


def _selected_evaluations(
    selected_items: list[BriefItem], evaluations: list[ItemEvaluation]
) -> list[ItemEvaluation]:
    selected_ids = {item.id for item in selected_items}
    return [evaluation for evaluation in evaluations if evaluation.item_id in selected_ids]


def _select_items_from_evaluations(
    items: list[BriefItem],
    evaluations: list[ItemEvaluation],
    threshold: float,
    limit: int,
    allow_include_override: bool = False,
) -> tuple[list[BriefItem], list[ItemEvaluation]]:
    evaluation_by_id = {evaluation.item_id: evaluation for evaluation in evaluations}
    rejected: list[ItemEvaluation] = []
    scored_candidates: list[tuple[float, BriefItem, ItemEvaluation]] = []

    for item in items:
        evaluation = evaluation_by_id.get(item.id)
        if evaluation is None:
            continue
        enriched_item = _apply_evaluation(item, evaluation)
        selection_score = _selection_score(enriched_item, evaluation)
        include = selection_score >= threshold and (evaluation.include or allow_include_override)
        if include or selection_score >= threshold + 0.08:
            scored_candidates.append((selection_score, enriched_item, evaluation))
        else:
            rejected.append(evaluation)

    ranked_items = [
        item for _, item, _ in sorted(scored_candidates, key=lambda row: row[0], reverse=True)
    ]
    # Interleave by source so the highest-scoring arXiv items do not fill every
    # slot; this yields a balanced multi-source selection while preserving the
    # within-source ranking order.
    selected = interleave_by_key(ranked_items, key=source_channel, limit=limit)
    return selected, rejected


def _apply_evaluation(item: BriefItem, evaluation: ItemEvaluation) -> BriefItem:
    weighted_score = round(
        0.4 * float(item.final_score or 0.0)
        + 0.35 * evaluation.importance_score
        + 0.25 * evaluation.novelty_score,
        4,
    )
    updated = item.model_copy(deep=True)
    updated.section = evaluation.category or updated.section or TOPIC_GENERAL
    updated.summary_short = updated.summary_short or evaluation.main_idea
    updated.importance_score = evaluation.importance_score
    updated.novelty_score = evaluation.novelty_score
    updated.final_score = weighted_score
    updated.why_it_matters = evaluation.why_it_matters or explain_why_it_matters(updated)
    return updated


def _selection_score(item: BriefItem, evaluation: ItemEvaluation) -> float:
    return round(
        0.45 * evaluation.importance_score
        + 0.25 * evaluation.novelty_score
        + 0.30 * float(item.final_score or 0.0),
        4,
    )


def _sanitize_plan(plan: EditorialPlan, items: list[BriefItem], max_sections: int) -> EditorialPlan:
    valid_ids = {item.id for item in items}
    sections: list[SectionPlan] = []
    used_ids: set[str] = set()
    for section in plan.sections[:max_sections]:
        item_ids = [item_id for item_id in section.item_ids if item_id in valid_ids and item_id not in used_ids]
        if not item_ids:
            continue
        used_ids.update(item_ids)
        sections.append(
            SectionPlan(
                name=section.name,
                angle=section.angle,
                item_ids=item_ids,
                audience_focus=section.audience_focus,
            )
        )

    if not sections and items:
        grouped: OrderedDict[str, list[str]] = OrderedDict()
        for item in items:
            grouped.setdefault(item.section or assign_topic(item, _default_ranking_config()), []).append(item.id)
        sections = [
            SectionPlan(
                name=name,
                angle=f"{name} items worth scanning first.",
                item_ids=item_ids,
                audience_focus="general technical readers",
            )
            for name, item_ids in grouped.items()
        ]

    return EditorialPlan(overview=plan.overview, sections=sections)


def _default_ranking_config() -> RankingConfig:
    return RankingConfig()


def _snapshot_details(snapshot: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for key in ("item_count", "candidate_count", "selected_count", "section_count", "dry_run", "needs_fallback"):
        if key in snapshot:
            details[key] = snapshot[key]
    return details


def _is_retryable_fetch_error(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.HTTPError, TimeoutError, OSError))


def _is_retryable_llm_error(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (httpx.HTTPError, TimeoutError, OSError, json.JSONDecodeError, ValidationError),
    )


def _is_retryable_send_error(exc: BaseException) -> bool:
    if isinstance(exc, (smtplib.SMTPException, TimeoutError, OSError, httpx.HTTPError)):
        return True
    return exc.__class__.__name__ == "HttpError"
