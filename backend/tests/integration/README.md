# Integration tests (real PostgreSQL)

Not a mirror of the fast suite — `tests/` (SQLite, `pytest`) covers business
logic and is what runs on every save. This small suite exists only for
things that SQLite cannot catch:

- **Foreign keys**: SQLite doesn't enforce them unless `PRAGMA
  foreign_keys=ON` is set, and the fast suite's engine doesn't set it.
- **`VARCHAR(n)` length limits**: Postgres enforces them; SQLite has no such
  concept and accepts any length.
- The custom `GUID` type and Alembic migrations against the real dialect
  they're written for, not SQLite's fallback.

## Running

```bash
docker compose up -d postgres   # or any reachable Postgres with matching creds
cd backend
pytest -m integration
```

Excluded from a plain `pytest` run (see `../../pytest.ini`) since it needs a
real database. If Postgres isn't reachable, the suite skips with a message
telling you how to start it — it doesn't fail the run.

Reuses `docker-compose.yml`'s `postgres` service and credentials
(`sourcelya`/`sourcelya`, `localhost:5432`) rather than standing up separate
test infrastructure. Override with `INTEGRATION_DATABASE_URL` if needed.
**It truncates every app table before each test** — never point this at a
database with data you care about.

## What's deliberately not here

A `secure_token_hash` check: that column belongs to `ComplianceRequest`,
which doesn't exist until FASE 3. Adding a test for a table that doesn't
exist yet would just be decoration — this suite will get a
`ComplianceRequest`-focused test once that table does.
