# WeWe RSS for Daily Brief (WeChat Official Accounts)

Self-hosted [WeWe RSS](https://github.com/cooderl/wewe-rss) instance that turns
WeChat Official Accounts (公众号) into RSS feeds the Daily Brief `rss` source can
ingest. Works by subscribing through a 微信读书 (WeChat Reading) account.

## 1. Start the service

```bash
docker compose -f deploy/wewe-rss/docker-compose.yml up -d
```

It listens on http://localhost:4000. The login/UI auth code defaults to
`morningbrief2026` (override with the `WEWE_AUTH_CODE` env var if you like).

## 2. Log in and bind a 微信读书 account  (MANUAL — requires you)

1. Open http://localhost:4000 and enter the auth code (`morningbrief2026`).
2. Go to **账号管理 (Accounts)** → **添加账号 (Add account)**.
3. Scan the QR code with the WeChat app on your phone.
   - Use a **secondary** WeChat account if possible — this drives the
     subscription via 微信读书 and carries a small account risk, similar to the
     X token setup.
4. Once bound, the account shows as online.

## 3. Add Official Accounts

1. Go to **订阅源 (Feeds)** → **添加 (Add)**.
2. Search the Official Account name (公众号) and subscribe.
3. Each subscription exposes an RSS/Atom URL, e.g.:
   - `http://localhost:4000/feeds/<feed_id>.atom`
   - `http://localhost:4000/feeds/<feed_id>.rss`

## 4. Wire feeds into the brief

Append the feed URLs to `SOURCE_RSS_FEEDS` in the project `.env`, then run the
brief. The `/feeds` endpoints do not require the auth code.

## Manage

```bash
docker compose -f deploy/wewe-rss/docker-compose.yml ps
docker compose -f deploy/wewe-rss/docker-compose.yml logs -f
docker compose -f deploy/wewe-rss/docker-compose.yml down
```

## Notes

- Keep the container running (and Docker Desktop open) for feeds to refresh.
- WeChat rate-limits aggressively; WeWe RSS spaces out updates (`UPDATE_DELAY_TIME`)
  to avoid being throttled. Don't add a huge number of accounts at once.
- If the bound 微信读书 session expires, re-bind it in 账号管理.
