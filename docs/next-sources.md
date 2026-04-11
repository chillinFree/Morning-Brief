# Next Sources To Add

## Twitter/X

Recommended approach:
- Prefer official API access if you already have stable credentials and usage limits that fit a daily batch job.
- If official access is unavailable, do not hardwire brittle scraping into the main pipeline.
- Introduce a dedicated `twitter_x.py` connector behind the existing source interface and keep raw payload persistence on by default.

Implementation shape:
- ingest from curated lists, saved searches, or selected accounts
- normalize posts and threads into `BriefItem` with `source_type="post"` or `source_type="thread"`
- store repost/like/reply counts in `engagement`
- add topic and keyword filtering before ranking

Main risks:
- API policy churn
- rate limits
- scraping fragility
- authentication complexity

## GradCafe / forums

Recommended approach:
- Start with RSS or structured endpoints if any exist
- otherwise isolate HTML parsing in a dedicated forum connector and treat it as low-trust input

Implementation shape:
- fetch category pages or search-result pages
- normalize into `BriefItem` with `source_type="forum_post"`
- capture thread title, post excerpt, forum name, and canonical thread URL
- add aggressive dedupe because forum topics recur frequently

Main risks:
- inconsistent HTML
- bot protection / anti-scraping measures
- legal / terms-of-service considerations
- low-signal chatter without strong filtering

## NBA data sources

Recommended approach:
- Prefer official or stable sports APIs over ad hoc scraping
- split scoreboard/game results from commentary/news feeds

Implementation shape:
- one connector for scoreboard / schedules / standings
- one connector for NBA news or team-specific RSS feeds
- normalize into `BriefItem` with `source_type="sports_update"`
- use team/player keywords plus your configured interests for ranking

Main risks:
- schedule / score freshness
- API quotas
- inconsistent metadata across providers

Recommended first additions:
1. team-focused scoreboard updates
2. playoff seeding / standings summaries
3. selected team news feeds
