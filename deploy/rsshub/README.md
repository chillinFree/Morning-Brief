# RSSHub for Daily Brief (X / Twitter)

Self-hosted [RSSHub](https://docs.rsshub.app) instance used to turn X (Twitter)
accounts/lists into RSS feeds that the Daily Brief `rss` source can ingest.

WeChat Official Accounts do NOT use this — see the main project notes for
wechat2rss instead.

## 1. Prerequisites

Install Docker Desktop for Mac: https://www.docker.com/products/docker-desktop/
Then confirm the daemon is running:

```bash
docker info
```

## 2. Configure secrets

```bash
cp deploy/rsshub/.env.example deploy/rsshub/.env
# edit deploy/rsshub/.env and set TWITTER_AUTH_TOKEN
```

`TWITTER_AUTH_TOKEN` is the `auth_token` cookie from a logged-in (ideally
throwaway) X account. X aggressively blocks unauthenticated access, so this is
required for Twitter routes to work.

## 3. Start RSSHub

```bash
docker compose -f deploy/rsshub/docker-compose.yml up -d
```

It will listen on http://localhost:1200.

## 4. Verify

```bash
# Should return an RSS/XML document
curl -s "http://localhost:1200/twitter/user/OpenAI" | head -n 20
```

## 5. Wire feeds into the brief

Add the RSSHub feed URLs to `SOURCE_RSS_FEEDS` in the project `.env`, e.g.:

```
SOURCE_RSS_FEEDS=...existing feeds...,http://localhost:1200/twitter/user/OpenAI,http://localhost:1200/twitter/user/sama
```

Useful routes:
- User timeline: `/twitter/user/:username`
- List: `/twitter/list/:id`
- Keyword search: `/twitter/keyword/:keyword`

Full route docs: https://docs.rsshub.app/routes/social-media#twitter

## Stop / logs

```bash
docker compose -f deploy/rsshub/docker-compose.yml logs -f rsshub
docker compose -f deploy/rsshub/docker-compose.yml down
```
