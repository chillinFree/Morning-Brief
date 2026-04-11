from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from daily_brief.config.settings import SummarizerConfig
from daily_brief.llm.base import WorkflowReasoner
from daily_brief.llm.prompts import (
    build_brief_planning_prompt,
    build_item_evaluation_prompt,
    build_section_summary_prompt,
)
from daily_brief.llm.schemas import EditorialPlan, ItemEvaluation, SectionPlan, SectionSummary
from daily_brief.models.brief import BriefItem

ParsedModel = TypeVar("ParsedModel", bound=BaseModel)


class OpenAICompatibleWorkflowReasoner(WorkflowReasoner):
    def __init__(self, config: SummarizerConfig) -> None:
        if not config.api_key:
            raise ValueError("SUMMARIZER_API_KEY is required for openai_compatible reasoning.")
        headers = {"Authorization": f"Bearer {config.api_key}"}
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.request_timeout_seconds,
            headers=headers,
        )
        self._config = config

    def evaluate_item(self, item: BriefItem) -> ItemEvaluation:
        prompt = build_item_evaluation_prompt(item)
        payload = self._invoke_json(
            system_prompt=(
                "You are an editorial analyst for a daily morning brief. "
                "Return strict JSON only."
            ),
            user_prompt=prompt,
            schema=ItemEvaluation,
        )
        if payload.item_id != item.id:
            payload.item_id = item.id
        return payload

    def plan_brief(
        self,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
        min_sections: int,
        max_sections: int,
    ) -> EditorialPlan:
        prompt = build_brief_planning_prompt(items, evaluations, min_sections, max_sections)
        return self._invoke_json(
            system_prompt=(
                "You are an editor planning a daily briefing. "
                "Group items into coherent sections and return strict JSON only."
            ),
            user_prompt=prompt,
            schema=EditorialPlan,
        )

    def summarize_section(
        self,
        section: SectionPlan,
        items: list[BriefItem],
        evaluations: list[ItemEvaluation],
    ) -> SectionSummary:
        prompt = build_section_summary_prompt(section, items, evaluations)
        payload = self._invoke_json(
            system_prompt=(
                "You write concise section summaries for a daily morning brief. "
                "Return strict JSON only."
            ),
            user_prompt=prompt,
            schema=SectionSummary,
        )
        if not payload.item_ids:
            payload.item_ids = [item.id for item in items]
        if payload.name != section.name:
            payload.name = section.name
        return payload

    def _invoke_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[ParsedModel],
    ) -> ParsedModel:
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self._config.model,
                "temperature": self._config.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("OpenAI-compatible response did not return a string content payload.")
        return schema.model_validate(json.loads(content))
