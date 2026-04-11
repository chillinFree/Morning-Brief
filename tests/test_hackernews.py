from __future__ import annotations

from daily_brief.sources.hackernews import parse_hn_items


def test_parse_hn_items_filters_keywords() -> None:
    payloads = [
        {
            "id": 101,
            "type": "story",
            "title": "New LLM benchmark released",
            "url": "https://example.com/benchmark",
            "by": "alice",
            "time": 1775635200,
            "score": 120,
            "descendants": 45,
        },
        {
            "id": 102,
            "type": "story",
            "title": "Unrelated startup funding story",
            "url": "https://example.com/funding",
            "by": "bob",
            "time": 1775635200,
            "score": 30,
            "descendants": 10,
        },
    ]

    items = parse_hn_items(payloads, run_id="run-1", keywords=["llm", "benchmark"])

    assert len(items) == 1
    assert items[0].source_item_id == "101"
    assert items[0].engagement.comments == 45
