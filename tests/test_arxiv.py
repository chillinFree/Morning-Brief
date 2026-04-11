from __future__ import annotations

from daily_brief.sources.arxiv import parse_arxiv_feed

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2404.00001v1</id>
    <updated>2026-04-08T07:00:00Z</updated>
    <published>2026-04-08T07:00:00Z</published>
    <title> Efficient Agents for Research </title>
    <summary> A paper about reliable agent systems. </summary>
    <author><name>A. Researcher</name></author>
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" />
  </entry>
</feed>
"""


def test_parse_arxiv_feed_normalizes_item() -> None:
    items = parse_arxiv_feed(ARXIV_XML, run_id="run-1", categories=["cs.AI"], keywords=["agent"])

    assert len(items) == 1
    item = items[0]
    assert item.source == "arxiv"
    assert item.source_item_id == "2404.00001v1"
    assert item.title == "Efficient Agents for Research"
    assert item.metadata["arxiv"]["primary_category"] == "cs.AI"
