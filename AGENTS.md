# Daily Brief Agent

## Current Project Snapshot
This repo is a Python 3.11+ local-first Daily Brief Agent. It is already scaffolded and runnable end-to-end as a deterministic batch pipeline:

`collect -> normalize -> store raw -> dedupe -> rank -> summarize -> render -> send -> record run state`

Current implementation status:
- source plugins implemented for `arxiv`, `github` tracked repo events, `hackernews`, `rss`, and local `file`
- aggregation implemented: dedup, ranking, topic grouping, structured brief assembly, markdown rendering
- summarization implemented with provider abstraction plus `extractive` and `openai_compatible` adapters
- email delivery implemented with polished HTML + plaintext rendering, `console`, `gmail_api`, and `smtp` senders
- scheduling implemented with APScheduler plus CLI/manual execution
- run history persisted in SQLite
- duplicate-send protection implemented for the same local target date unless forced
- raw payload persistence supported for replay/debugging
- structured JSON logging implemented
- tests, `ruff`, and `mypy` are currently passing

Validation state at last pass:
- `conda run -n brief ruff check src tests` passed
- `conda run -n brief mypy src` passed
- `conda run -n brief pytest` passed
- current test count: `18`

## Purpose
Build a production-ready automated Daily Brief Agent that aggregates morning updates, normalizes them into a shared schema, deduplicates/ranks them, summarizes them with a pluggable LLM layer, renders an HTML email digest, and sends it through Gmail or another delivery backend.

## Product Goal
Every morning, generate a concise, high-signal digest covering:
- arXiv new papers
- GitHub tracked repo updates
- Hacker News and RSS-based tech/news feeds
- future sources such as Twitter/X, GradCafe/forums, NBA

## Architecture
Use a deterministic batch pipeline, not a multi-agent workflow engine.

Current major packages under `src/daily_brief/`:
- `sources/`: live connectors and source registry
- `aggregation/`: dedup, ranking, topicing, brief assembly
- `summarization/`: provider abstraction, prompt builder, adapters
- `rendering/`: HTML/text/markdown rendering
- `delivery/`: console preview, Gmail API, SMTP, subject generation
- `orchestration/`: execution options, pipeline, scheduler integration
- `storage/`: SQLite schema, migration shim, repository layer
- `config/`: typed settings via `pydantic-settings`
- `logging/`: structured JSON logging
- `models/`: normalized models such as `BriefItem`, `DailyBrief`, `Digest`, `RunRecord`
- `utils/`: HTTP fetcher, raw capture, URL validation

## Key Data Models
### `BriefItem`
Normalized content model used across all sources.

Important fields:
- `source`
- `source_item_id`
- `source_type`
- `title`
- `url`
- `canonical_url`
- `published_at`
- `summary_short`
- `tags`
- `topics`
- `engagement`
- `metadata`
- `raw_ref`
- `fingerprint_exact`
- `relevance_score`
- `importance_score`
- `novelty_score`
- `final_score`
- `why_it_matters`
- `section`

### `DailyBrief`
Machine-readable structured brief produced after aggregation and summarization.

Important fields:
- `run_id`
- `subject`
- `generated_at`
- `overview`
- `sections`
- `markdown_body`

### `Digest`
Email-renderable artifact.

Important fields:
- `run_id`
- `subject`
- `timezone_name`
- `overview`
- `sections`
- `html_body`
- `text_body`

### `RunRecord`
Operational run metadata persisted to SQLite.

Important fields:
- `id`
- `target_date`
- `timezone_name`
- `mode`
- `dry_run`
- `force_send`
- `status`
- `item_count`
- `started_at`
- `completed_at`
- `error_message`

## Implemented Source Connectors
### arXiv
- configurable categories
- keyword filtering
- Atom parsing
- raw payload capture

### GitHub
- stable MVP path uses tracked repository events, not trending scraping
- supports tracked repos and optional `GITHUB_TOKEN`
- normalizes release/push/issue/pull-request events

### Hacker News
- supports `top` and `new` story lists
- keyword filtering
- per-item raw payload capture

### RSS
- supports multiple feeds
- supports RSS and Atom
- keyword filtering

### File Source
- local sample/demo source
- useful for dry runs and integration tests

## Aggregation Rules
### Dedup
- source IDs when available
- normalized URL comparison
- title similarity fallback

### Ranking
Configurable, AI-focused defaults currently prefer:
- AI research
- open-source / GitHub
- tech news

Current topic buckets:
- `AI research`
- `Open-source / GitHub`
- `Tech news`
- `Applications / grad-related`
- `Sports / NBA`
- `General`

### Summarization
Current providers:
- `extractive`
- `openai_compatible`

Prompt template exists and the summarizer interface is provider-agnostic.

## Email Delivery
Current senders:
- `console`
- `gmail_api`
- `smtp`

Current email capabilities:
- responsive HTML email
- plain-text fallback
- executive summary at top
- timestamp + timezone
- empty-section graceful handling
- per-item title, source, short summary, why-it-matters, link
- local preview written to disk before sending when configured

## Scheduling And Execution
Supported execution modes:
- manual
- scheduled
- backfill
- preview
- test

Implemented operational behavior:
- local scheduled execution via APScheduler
- one-shot manual execution
- configurable timezone and send time
- fetch/send retry with exponential backoff
- duplicate-send protection for same target date
- persistent run history in SQLite

## Important CLI Commands
Initialize:
```bash
conda run -n brief daily-brief init-db
```

Manual run:
```bash
conda run -n brief daily-brief run-now
```

Dry run:
```bash
conda run -n brief daily-brief dry-run
```

Preview email:
```bash
conda run -n brief daily-brief preview-email
```

Send test email:
```bash
conda run -n brief daily-brief send-test-email
```

Backfill:
```bash
conda run -n brief daily-brief backfill-date 2026-04-01 --dry-run
```

List runs:
```bash
conda run -n brief daily-brief list-runs --limit 10
```

Start scheduler:
```bash
conda run -n brief daily-brief schedule
```

## Config Notes
Main config is environment-driven via `.env`.

Useful files:
- [`.env.example`](/home/chillinfree/MorningBrief/.env.example): minimal/default config
- [`config/example.ai-focused.env`](/home/chillinfree/MorningBrief/config/example.ai-focused.env): AI-focused live-source example

Important env groups:
- `APP_*`: timezone, digest time, retries, scheduler grace window
- `SOURCE_*`: source enable/disable and source-specific settings
- `RANKING_*`: scoring weights, topic keywords, limits
- `SUMMARIZER_*`: provider/model/API settings
- `EMAIL_*`: sender/recipient and preview behavior
- `GMAIL_*`: Gmail OAuth files/user id
- `SMTP_*`: SMTP fallback settings

Secrets policy:
- keep secrets only in `.env` or external environment variables
- do not commit `.env`
- do not commit `credentials.json`
- `var/` is ignored

## Storage
Current storage is SQLite plus local raw payload files.

Persisted tables:
- `runs`
- `brief_items`
- `digests`
- `deliveries`

Operational note:
- `storage/sqlite.py` contains a lightweight runtime migration shim for older `runs` table schemas
- long term, Alembic should replace this

## Documentation
Primary operator docs:
- [`README.md`](/home/chillinfree/MorningBrief/README.md)

Future-source guide:
- [`docs/next-sources.md`](/home/chillinfree/MorningBrief/docs/next-sources.md)

That guide already covers:
- Twitter/X
- GradCafe/forums
- NBA data sources

## Quality Status
Current strengths:
- clear modular boundaries
- typed settings and typed models
- solid local-first operator workflow
- tested source parsing and integration paths
- tested pipeline persistence paths
- tested delivery rendering and subject generation

Known pragmatic shortcuts still in repo:
- runtime migration shim instead of Alembic
- SQLite instead of Postgres
- no OpenTelemetry/Sentry yet
- no true semantic dedupe/embeddings yet
- Gmail desktop OAuth is not ideal for headless cloud execution

## Recommended Next Steps
Highest-value next improvements:
1. replace runtime DB patching with Alembic migrations
2. add a `doctor` CLI command for config/source/email readiness checks
3. add Dockerfile and one cloud scheduled-job deployment example
4. add the next real source connector from `docs/next-sources.md`
5. move to Postgres + object storage before serious cloud deployment

## Definition Of Success
The project is currently successful when a single local command can:
- collect from enabled sources
- normalize and persist items
- deduplicate/rank/summarize into a structured brief
- render HTML/text email output
- preview or send the digest
- persist run and delivery history
- avoid duplicate sends for the same day
- leave enough logs and state behind for debugging
