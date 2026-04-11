from __future__ import annotations

from daily_brief.sources.github import parse_github_events


def test_parse_github_release_and_push_events() -> None:
    events = [
        {
            "id": "1",
            "type": "ReleaseEvent",
            "repo": {"name": "example/repo"},
            "actor": {"login": "maintainer"},
            "created_at": "2026-04-08T07:00:00Z",
            "payload": {
                "release": {
                    "tag_name": "v1.2.0",
                    "name": "Stable Release",
                    "html_url": "https://github.com/example/repo/releases/tag/v1.2.0",
                }
            },
        },
        {
            "id": "2",
            "type": "PushEvent",
            "repo": {"name": "example/repo"},
            "actor": {"login": "maintainer"},
            "created_at": "2026-04-08T08:00:00Z",
            "payload": {
                "size": 2,
                "commits": [
                    {
                        "sha": "abcdef123456",
                        "message": "Improve inference throughput",
                        "url": "https://api.github.com/repos/example/repo/commits/abcdef123456",
                    }
                ],
            },
        },
    ]

    items = parse_github_events(
        "example/repo", events, run_id="run-1", keywords=["release", "inference"]
    )

    assert len(items) == 2
    assert items[0].source == "github"
    assert items[0].metadata["github"]["event_type"] == "ReleaseEvent"
    assert items[1].summary_short == "Improve inference throughput"
