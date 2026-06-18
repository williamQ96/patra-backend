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
  "TAPIS_AUTH_VALIDATION_ENABLED": "true",
  "TAPIS_JWKS_URL": "<operator-provided-jwks-url>",
  "TAPIS_ISSUER": "<operator-provided-issuer>",
  "TAPIS_AUDIENCE": "<operator-provided-audience>",
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
  "ASSET_BACKUP_STORAGE": "database",
  "TAPIS_AUTH_VALIDATION_ENABLED": "true",
  "TAPIS_JWKS_URL": "<operator-provided-jwks-url>",
  "TAPIS_ISSUER": "<operator-provided-issuer>",
  "TAPIS_AUDIENCE": "<operator-provided-audience>",
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

Production deployments must obtain the exact JWKS URL, issuer, and audience
from the Tapis tenant operator. Do not guess these values. Authentication fails
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
- `patradev-backend` must receive both `DATABASE_URL` and `SENSITIVE_DATABASE_URL`.
- `ASSET_BACKUP_STORAGE=database` keeps sensitive asset backup snapshots in `patradev-db` instead of local JSON files.
- Schema migrations must be forward compatible.
- Dev-only workflows must write isolated tables, not shared catalog tables.
- Promotion from dev-only state into shared catalog tables must be explicit.
