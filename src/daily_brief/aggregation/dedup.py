from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from daily_brief.aggregation.types import AggregationResult, DedupeCluster
from daily_brief.config.settings import RankingConfig
from daily_brief.models.brief import BriefItem

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "src",
}


def deduplicate_items(items: list[BriefItem], config: RankingConfig) -> AggregationResult:
    clusters: list[DedupeCluster] = []
    deduped: list[BriefItem] = []
    for item in items:
        normalized_url = normalize_url(str(item.canonical_url or item.url))
        item.metadata.setdefault("dedupe", {})["normalized_url"] = normalized_url
        matched_cluster: DedupeCluster | None = None
        for cluster in clusters:
            if is_duplicate(item, cluster.representative, config):
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append(DedupeCluster(representative=item))
            deduped.append(item)
            continue
        chosen = _pick_representative(matched_cluster.representative, item)
        duplicate = (
            item if chosen is matched_cluster.representative else matched_cluster.representative
        )
        chosen.metadata.setdefault("dedupe", {})["duplicates"] = sorted(
            {
                *chosen.metadata.get("dedupe", {}).get("duplicates", []),
                duplicate.id,
            }
        )
        matched_cluster.representative = chosen
        matched_cluster.duplicates.append(duplicate)
        if chosen is item:
            deduped = [chosen if existing.id == duplicate.id else existing for existing in deduped]
    return AggregationResult(items=deduped, clusters=clusters)


def is_duplicate(left: BriefItem, right: BriefItem, config: RankingConfig) -> bool:
    left_ids = _source_identity_keys(left)
    right_ids = _source_identity_keys(right)
    if left_ids & right_ids:
        return True

    if normalize_url(str(left.canonical_url or left.url)) == normalize_url(
        str(right.canonical_url or right.url)
    ):
        return True

    similarity = title_similarity(left.title, right.title)
    same_topic_hint = (
        left.section and right.section and left.section == right.section
    ) or left.source_type == right.source_type
    return similarity >= config.title_similarity_threshold and bool(same_topic_hint)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key not in TRACKING_PARAMS
    ]
    normalized_path = parsed.path.rstrip("/") or "/"
    normalized_netloc = parsed.netloc.lower().removeprefix("www.")
    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            normalized_netloc,
            normalized_path,
            "",
            urlencode(sorted(query_pairs)),
            "",
        )
    )


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(
        a=" ".join(left.lower().split()), b=" ".join(right.lower().split())
    ).ratio()


def _source_identity_keys(item: BriefItem) -> set[str]:
    keys: set[str] = set()
    if item.source_item_id:
        keys.add(f"{item.source}:{item.source_item_id}")
    source_id = item.metadata.get("source_id")
    if isinstance(source_id, str) and source_id:
        keys.add(f"{item.source}:{source_id}")
    return keys


def _pick_representative(left: BriefItem, right: BriefItem) -> BriefItem:
    left_score = _representative_quality(left)
    right_score = _representative_quality(right)
    return left if left_score >= right_score else right


def _representative_quality(item: BriefItem) -> float:
    summary_len = len(item.summary_short or item.content_text or "")
    engagement = float(item.engagement.score or 0.0) + float(item.engagement.comments or 0) / 50.0
    return summary_len / 400.0 + engagement
