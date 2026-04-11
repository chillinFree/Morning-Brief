# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Brief Agent — a deterministic batch pipeline that collects, normalizes, ranks, summarizes, and delivers a morning digest email. Python 3.11+, `src/` layout, packaged with Hatchling.

Pipeline stages: `collect -> normalize -> store raw -> dedupe -> rank -> summarize -> render -> send -> record run state`

## Common Commands

All commands run inside the `brief` conda environment:

```bash
# Install (editable, with dev deps)
conda run -n brief python -m pip install -e ".[dev]"

# Lint
conda run -n brief ruff check src tests

# Type check
conda run -n brief mypy src

# Run all tests
conda run -n brief pytest

# Run a single test file
conda run -n brief pytest tests/test_hackernews.py

# Run a specific test by name
conda run -n brief pytest tests/test_pipeline.py::test_run_persists_items -v

# CLI commands
conda run -n brief daily-brief init-db
conda run -n brief daily-brief dry-run
conda run -n brief daily-brief run-now
conda run -n brief daily-brief run-now --force
conda run -n brief daily-brief preview-email
conda run -n brief daily-brief list-runs --limit 10
conda run -n brief daily-brief schedule
```

## Architecture

Entry points:
- `daily-brief` CLI → `src/daily_brief/cli.py` (Typer app)
- `daily-brief-scheduler` → `src/daily_brief/scheduler_entry.py`

The core orchestrator is `DailyBriefPipeline` in `src/daily_brief/orchestration/pipeline.py`. It wires together source, summarizer, and sender via registry factories (`build_source`, `build_summarizer`, `build_sender`).

### Package layout under `src/daily_brief/`

| Package | Purpose |
|---|---|
| `config/` | `AppSettings` — typed pydantic-settings loaded from `.env` and env vars. All config groups (app, database, source, ranking, summarizer, email) are nested models. |
| `sources/` | `BriefSource` ABC with `fetch()` method. Implementations: `file`, `arxiv`, `github`, `hackernews`, `rss`. Registry in `sources/registry.py`. |
| `aggregation/` | Dedup, ranking, topic grouping, brief assembly (`build_daily_brief`). |
| `summarization/` | `BriefSummarizer` ABC. Adapters: `extractive` (default, deterministic), `openai_compatible`. Registry in `summarization/registry.py`. |
| `rendering/` | HTML + plaintext email rendering from `DailyBrief` → `Digest`. |
| `delivery/` | `EmailSender` ABC. Implementations: `console` (writes to `var/outbox/`), `gmail_api`, `smtp`. Registry in `delivery/registry.py`. |
| `orchestration/` | `DailyBriefPipeline` and `ExecutionOptions`. The pipeline manages the full run lifecycle including retry, duplicate-send protection, and run state persistence. |
| `storage/` | SQLAlchemy SQLite. Tables: `runs`, `brief_items`, `digests`, `deliveries`. Repository pattern via `BriefRepository`. Migration shim in `storage/sqlite.py` (Alembic planned). |
| `models/` | Core data models: `BriefItem`, `DailyBrief`, `Digest`, `RunRecord`, `BriefSection`. |

### Key patterns

- **Registry pattern**: Sources, summarizers, and senders each use a registry function (`build_source`, `build_summarizer`, `build_sender`) that reads settings and returns the correct implementation.
- **Settings**: All config is environment-driven via pydantic-settings. Each config group is a separate `BaseSettings` class with prefixed env vars (e.g., `SOURCE_ARXIV_ENABLED`, `EMAIL_PROVIDER`).
- **Duplicate-send protection**: Non-dry-run deliveries for the same target date are blocked unless `--force` is passed.
- **Retry**: Fetch and send operations use `tenacity` with exponential backoff, gated by retryable error classifiers.

## Configuration

Env-driven via `.env` file and environment variables. See `.env.example` for defaults and `config/example.ai-focused.env` for a live-source setup.

Key env groups: `APP_*`, `SOURCE_*`, `RANKING_*`, `SUMMARIZER_*`, `EMAIL_*`, `GMAIL_*`, `SMTP_*`.

Secrets policy: secrets only in `.env` or environment variables. `.env`, `credentials.json`, and `var/` are gitignored.

## Linting & Formatting

- `ruff` with line length 100, target Python 3.11
- Enabled rules: `E`, `F`, `I`, `B`, `UP`, `N` (E501 ignored)
- `mypy --strict`

## Storage

SQLite at `var/daily_brief.db` by default. Raw payloads optionally persisted to `var/raw/`. Email previews written to `var/outbox/`.
