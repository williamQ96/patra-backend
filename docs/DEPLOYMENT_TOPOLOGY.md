# PATRA Backend Deployment Topology

## Canonical backend repository

Use `patra-knowledge-base` / `patra-backend` as the only long-term backend codebase. Deploy two pods from the same image:

- `patrabackend`: stable backend
- `patradev-backend`: development backend

`patrabackend` points only at `patradb`. `patradev-backend` points at both `patradb` and `patradev-db`: the primary catalog remains in `patradb`, while sensitive dev snapshots use `patradev-db`.

## Route gating

The backend now gates dev-only routes by environment flags:

- `ENABLE_ASK_PATRA`
- `ENABLE_AUTOMATED_INGESTION`
- `ENABLE_DOMAIN_EXPERIMENTS`

Stable backend should leave these off. Dev backend should enable them.

## Stable backend env

```json
{
  "DATABASE_URL": "<patradb-url>",
  "DB_BOOTSTRAP_SCHEMA_ENABLED": "false",
  "TAPIS_AUTH_VALIDATION_ENABLED": "true",
  "TAPIS_JWKS_URL": "https://icicleai.tapis.io/v3/oauth2/jwks",
  "TAPIS_ISSUER": "https://icicleai.tapis.io/v3/tokens",
  "TAPIS_AUDIENCE": "",
  "TAPIS_USERNAME_CLAIM": "tapis/username",
  "TAPIS_TOKEN_LEEWAY_SECONDS": "60",
  "ALLOW_UNVERIFIED_TAPIS_TOKEN_DEV_ONLY": "false",
  "ENABLE_ASK_PATRA": "false",
  "ENABLE_AUTOMATED_INGESTION": "false",
  "ENABLE_DOMAIN_EXPERIMENTS": "false"
}
```

## Dev backend env

```json
{
  "DATABASE_URL": "<patradb-url>",
  "SENSITIVE_DATABASE_URL": "<patradev-db-url>",
  "DB_BOOTSTRAP_SCHEMA_ENABLED": "true",
  "ASSET_BACKUP_STORAGE": "database",
  "TAPIS_AUTH_VALIDATION_ENABLED": "true",
  "TAPIS_JWKS_URL": "https://icicleai.tapis.io/v3/oauth2/jwks",
  "TAPIS_ISSUER": "https://icicleai.tapis.io/v3/tokens",
  "TAPIS_AUDIENCE": "",
  "TAPIS_USERNAME_CLAIM": "tapis/username",
  "TAPIS_TOKEN_LEEWAY_SECONDS": "60",
  "ALLOW_UNVERIFIED_TAPIS_TOKEN_DEV_ONLY": "false",
  "ENABLE_ASK_PATRA": "true",
  "ENABLE_AUTOMATED_INGESTION": "true",
  "ENABLE_DOMAIN_EXPERIMENTS": "true",
  "ASK_PATRA_LLM_API_BASE": "https://litellm.pods.tacc.tapis.io",
  "ASK_PATRA_LLM_MODEL": "llama3.3-70b-instruct",
  "ASK_PATRA_TAPIS_TOKEN": "<optional service token>"
}
```

## Shared tables

These belong to the shared product surface and can be read/written by both stable and dev backends:

- `model_cards`
- `datasheets`
- `submission_queue`
- `tickets`
- `ticket_comments`
- `users` / actor profile tables
- shared audit / changelog / version lineage tables

## Dev-only tables

These support experimental workflows and should only be written by `patradev-backend`:

- `scraper_jobs`
- `automated_ingestion_artifacts`
- `camera_trap_events`
- `camera_trap_power`
- `digital_ag_events`
- `digital_ag_power`

Ask Patra currently stores conversation memory and prompt files on a mounted volume rather than in PostgreSQL.

## Tapis authentication

The backend prefers `Authorization: Bearer <token>` and supports
`X-Tapis-Token` only for compatibility. It verifies signing keys through the
configured JWKS endpoint and derives username/admin status server-side.
`X-Patra-Username` and `X-Patra-Role` are ignored.

The ICICLE production tenant publishes its RS256 signing key at
`https://icicleai.tapis.io/v3/oauth2/jwks`. Current ICICLE access tokens use
issuer `https://icicleai.tapis.io/v3/tokens` and do not carry an audience
claim, so `TAPIS_AUDIENCE` is left empty. Reconfirm these values with the
tenant operator if the issuer configuration changes. Authentication fails
closed when validation is enabled but JWKS verification cannot be performed.

The unverified development mode requires both:

```env
TAPIS_AUTH_VALIDATION_ENABLED=false
ALLOW_UNVERIFIED_TAPIS_TOKEN_DEV_ONLY=true
```

It still requires a structurally valid, time-valid JWT and must never be used
for production or shared deployments.

## Database rules

- `patrabackend` must not receive `SENSITIVE_DATABASE_URL`.
- `patrabackend` sets `DB_BOOTSTRAP_SCHEMA_ENABLED=false`; schema changes are a
  separate reviewed operation and never an incidental effect of a pod restart.
- `patradev-backend` must receive both `DATABASE_URL` and `SENSITIVE_DATABASE_URL`.
- `ASSET_BACKUP_STORAGE=database` keeps sensitive asset backup snapshots in `patradev-db` instead of local JSON files.
- Schema migrations must be forward compatible.
- Dev-only workflows must write isolated tables, not shared catalog tables.
- Promotion from dev-only state into shared catalog tables must be explicit.
