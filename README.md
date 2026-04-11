# Daily Brief Agent

Production-oriented Python scaffold for a Daily Brief Agent. The project is now orchestrated as an explicit LangGraph workflow:

`ingest -> clean/dedup -> heuristic rank -> LLM evaluate -> select -> plan -> summarize sections -> render -> deliver -> persist artifacts`

The scaffold is runnable locally today with:
- typed settings via `pydantic-settings`
- structured JSON logging
- SQLite persistence
- LangGraph Graph API orchestration with typed shared state
- APScheduler-based scheduling
- a normalized `BriefItem` data model
- source, reasoning, and delivery abstractions
- working source plugins for arXiv, GitHub tracked repos, Hacker News, RSS, plus a local demo file source
- a console/outbox sender

## Quickstart

```bash
conda run -n brief python -m pip install -e ".[dev]"
cp .env.example .env
conda run -n brief daily-brief init-db
conda run -n brief daily-brief dry-run
conda run -n brief daily-brief preview-email
conda run -n brief daily-brief doctor
conda run -n brief daily-brief show-graph
conda run -n brief daily-brief list-runs --limit 5
```

If you want an AI-focused live-source setup, start from [`config/example.ai-focused.env`](/home/chillinfree/MorningBrief/config/example.ai-focused.env) instead of the minimal `.env.example`.

## What is implemented

Fully implemented:
- project packaging and `src/` layout
- typed settings and environment loading
- SQLAlchemy SQLite storage
- run state persistence
- LangGraph workflow with explicit nodes and conditional routing
- normalized `BriefItem` model
- source registry and source interfaces
- deterministic file-backed source implementation
- arXiv connector with category and keyword filtering
- GitHub tracked repo updates connector using stable repository events, with optional token support
- Hacker News top/new story connector with keyword filtering
- RSS/Atom feed connector with multiple feed support
- deterministic ranking, cleaning, and dedupe stages
- structured reasoning with extractive and OpenAI-compatible providers
- local file-backed LangGraph checkpoint persistence
- HTML and text rendering
- console/outbox, Feishu, Gmail API, and SMTP delivery adapters
- `doctor` CLI command for demo/readiness checks
- CLI entrypoint
- APScheduler entrypoint
- pytest smoke coverage

Stubbed behind interfaces:
- Gmail API sender
- production LLM providers

## Local setup

### 1. Create and activate the environment

Conda activation in a one-shot shell should be done with `conda run`, not `conda activate`.

```bash
conda run -n brief python --version
```

### 2. Install the project

```bash
conda run -n brief python -m pip install -e ".[dev]"
```

### 3. Create the environment file

```bash
cp .env.example .env
```

The defaults are safe for a local run. No secrets are required for the console sender and file-backed demo source.
External source connectors can be enabled in `.env` once you are ready to fetch live data.

AI-focused example:

```bash
cp config/example.ai-focused.env .env
```

### 4. Initialize the database

```bash
conda run -n brief daily-brief init-db
```

### 5. Run one manual digest

```bash
conda run -n brief daily-brief run-now
```

This will:
- load sample items from `data/sample_brief_items.json`
- execute the LangGraph morning-brief workflow
- persist a run and normalized items in SQLite
- render an HTML digest
- write the email preview to `var/outbox/`
- save stage-by-stage JSON artifacts under `runs/<date>_<timestamp>_<run_id>/`
- update `runs/checkpoints/workflow.pkl` with LangGraph checkpoint state
- print structured logs to stdout

### 5a. Fetch live normalized items without sending email

```bash
conda run -n brief python scripts/fetch_demo.py
```

### 5b. Preview the email without sending

```bash
conda run -n brief daily-brief preview-email
```

This writes HTML and plaintext previews to `var/outbox/`.

### 6. Start the scheduler

```bash
conda run -n brief daily-brief schedule
```

By default it runs on the configured cron schedule in `.env`.

## Common commands

```bash
conda run -n brief daily-brief show-config
conda run -n brief daily-brief init-db
conda run -n brief daily-brief doctor
conda run -n brief daily-brief run-now
conda run -n brief daily-brief run-now --dry-run
conda run -n brief daily-brief run-now --force
conda run -n brief daily-brief dry-run
conda run -n brief daily-brief backfill-date 2026-04-01 --dry-run
conda run -n brief daily-brief show-graph
conda run -n brief daily-brief send-test-email
conda run -n brief daily-brief list-runs --limit 10
conda run -n brief daily-brief schedule
conda run -n brief pytest
```

## Automated execution

### Local scheduled execution

The built-in scheduler uses `APP_TIMEZONE`, `APP_DIGEST_HOUR`, and `APP_DIGEST_MINUTE`.

```bash
conda run -n brief daily-brief schedule
```

### Local cron

Recommended for a single-machine setup.

```cron
0 8 * * * cd /home/chillinfree/MorningBrief && /home/chillinfree/workspace/anaconda3/bin/conda run -n brief daily-brief run-now >> /home/chillinfree/MorningBrief/var/cron.log 2>&1
```

### Duplicate-send protection

- A successful non-dry-run delivery for the same local target date will block subsequent sends.
- Use `--force` to override.
- Dry runs never count as sent deliveries.

Examples:

```bash
conda run -n brief daily-brief run-now
conda run -n brief daily-brief run-now --force
conda run -n brief daily-brief backfill-date 2026-04-01 --force
```

## Deployment recommendations

### Local cron

Best first choice if this machine is reliably on every morning.

- Lowest operational overhead
- Uses the same SQLite DB and local preview/outbox paths
- Easiest to debug

### GitHub Actions

Viable if you move to API-backed sources and avoid local-only credentials.

- Good for scheduled one-shot runs
- Easy secret management for API tokens
- Bad fit for Gmail OAuth desktop flow and local filesystem state

Recommendation:
- Use it only after moving delivery to SMTP or service-compatible auth and after relocating SQLite to durable storage

### Cloud deployment

Best long-term shape: one scheduled container job.

Recommended targets:
- Cloud Run Jobs
- GitHub Actions with external DB/storage
- Railway cron service
- Fly.io machine or scheduled app

Recommended upgrades before cloud:
- move SQLite to Postgres
- move raw payloads/outbox artifacts to object storage
- use managed secrets
- use Gmail API token management or SMTP credentials that fit non-interactive execution

## Project layout

```text
src/daily_brief/
  cli.py
  scheduler_entry.py
  main.py
  config/
  delivery/
  graph/
  llm/
  logging/
  models/
  orchestration/
  ranking/
  rendering/
  scheduling/
  sources/
  storage/
  summarization/
  utils/
```

## Notes

- The default sender is `console`, which writes rendered emails to `var/outbox/`.
- Every workflow run also saves intermediate state snapshots and final artifacts under `runs/`.
- LangGraph checkpoints are persisted locally at `runs/checkpoints/workflow.pkl`.
- The default enabled source is `file`, which reads `data/sample_brief_items.json`.
- GitHub "trending" is intentionally not the MVP path. The stable first implementation uses tracked repository events instead.
- Secrets must be supplied only through environment variables when external providers are added.
- `.env`, `credentials.json`, and `var/` are ignored by default via [`.gitignore`](/home/chillinfree/MorningBrief/.gitignore).

## Gmail API setup

The Gmail sender uses OAuth desktop credentials and stores the refresh token locally.

1. In Google Cloud, enable the Gmail API.
2. Configure the OAuth consent screen.
3. Create an OAuth client for a Desktop app.
4. Download the client JSON and place it at `credentials.json` or set `GMAIL_CREDENTIALS_FILE`.
5. Set `EMAIL_PROVIDER=gmail_api` in `.env`.
6. Run `conda run -n brief daily-brief preview-email` once if you want to inspect the output first.
7. Run `conda run -n brief daily-brief run-once`. The first Gmail send opens a local OAuth flow and writes a token file to `var/gmail_token.json` by default.

Relevant Google docs:
- Gmail Python quickstart: https://developers.google.com/workspace/gmail/api/quickstart/python
- Sending mail with Gmail API: https://developers.google.com/workspace/gmail/api/guides/sending
- `users.messages.send` reference: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send

## Next sources

Planned source-integration notes are in [`docs/next-sources.md`](/home/chillinfree/MorningBrief/docs/next-sources.md), covering:
- Twitter/X
- GradCafe / forums
- NBA data sources
