from __future__ import annotations

from daily_brief.sources.rss import parse_rss_feed

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Agent systems in production</title>
      <link>https://example.com/agent-systems</link>
      <guid>rss-1</guid>
      <description>Operational lessons from building agent systems.</description>
      <pubDate>Tue, 08 Apr 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_feed_normalizes_item() -> None:
    items = parse_rss_feed(
        RSS_XML, "https://example.com/rss.xml", run_id="run-1", keywords=["agent"]
    )

    assert len(items) == 1
    assert items[0].source == "rss"
    assert items[0].metadata["fetch"]["feed_url"] == "https://example.com/rss.xml"
    assert items[0].title == "Agent systems in production"
