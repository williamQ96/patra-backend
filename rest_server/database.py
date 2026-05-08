import asyncio
import logging
import os
import ssl
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import asyncpg
from fastapi import HTTPException

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_sensitive_pool: asyncpg.Pool | None = None

_MAX_RETRIES = 5
_RETRY_DELAY_S = 3
_SCHEMA_FILE = Path(__file__).resolve().parents[1] / "db" / "bootstrap_schema.sql"


_TAPIS_PODS_SUFFIX = ".pods.icicleai.tapis.io"
_TAPIS_PG_PORT = 443


def _build_connection_options(raw_url: str) -> tuple[str, ssl.SSLContext | bool, bool]:
    """Normalise asyncpg connection options for the active PostgreSQL backend.

    Tapis Pods exposes PostgreSQL behind a 443 endpoint. If the host looks
    like a Tapis pod and the port is 5432, rewrite it to 443.

    asyncpg doesn't reliably consume the ``sslmode`` query-string parameter
    the way libpq/psycopg2 does, so we strip it and pass ``ssl`` explicitly.
    """
    parsed = urlparse(raw_url)

    host = parsed.hostname or ""
    port = parsed.port
    is_tapis_pod = host.endswith(_TAPIS_PODS_SUFFIX)
    if is_tapis_pod and port in (5432, None):
        netloc = parsed.netloc.replace(f":{port}", f":{_TAPIS_PG_PORT}", 1) if port else f"{parsed.netloc}:{_TAPIS_PG_PORT}"
        parsed = parsed._replace(netloc=netloc)
        log.info("Tapis Pods host detected; rewriting port %s to %s", port, _TAPIS_PG_PORT)

    qs = parse_qs(parsed.query)
    sslmode = qs.pop("sslmode", [None])[0]

    clean_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    if sslmode in ("require", "prefer"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return clean_url, ctx, False
    if sslmode in ("verify-ca", "verify-full"):
        return clean_url, ssl.create_default_context(), False
    return clean_url, False, False


async def _create_pool_from_url(url: str, *, label: str) -> asyncpg.Pool:
    dsn, ssl_arg, direct_tls = _build_connection_options(url)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn,
                ssl=ssl_arg,
                direct_tls=direct_tls,
                min_size=1,
                max_size=10,
                command_timeout=60,
                timeout=30,
            )
            await ensure_schema(pool)
            log.info("%s database pool ready (attempt %d)", label, attempt)
            return pool
        except (OSError, asyncpg.PostgresError, TimeoutError) as exc:
            if attempt == _MAX_RETRIES:
                raise
            log.warning(
                "%s DB connection attempt %d/%d failed (%s), retrying in %ds ...",
                label, attempt, _MAX_RETRIES, exc, _RETRY_DELAY_S,
            )
            await asyncio.sleep(_RETRY_DELAY_S)
    raise RuntimeError("Unreachable")


async def init_pool() -> asyncpg.Pool:
    """Create primary connection pool with retries. Called during app lifespan startup."""
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")

    _pool = await _create_pool_from_url(url, label="Primary")
    return _pool


async def init_sensitive_pool() -> asyncpg.Pool | None:
    """Create optional isolated pool for sensitive dev-only records."""
    global _sensitive_pool
    url = os.getenv("SENSITIVE_DATABASE_URL") or os.getenv("DEV_DATABASE_URL")
    if not url:
        _sensitive_pool = None
        log.info("Sensitive database pool disabled")
        return None

    _sensitive_pool = await _create_pool_from_url(url, label="Sensitive")
    return _sensitive_pool


async def ensure_schema(pool: asyncpg.Pool) -> None:
    if not _SCHEMA_FILE.exists():
        raise RuntimeError(f"Bootstrap schema file not found: {_SCHEMA_FILE}")

    sql = _SCHEMA_FILE.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(sql)
    log.info("Database schema bootstrap ensured")


async def close_pool() -> None:
    """Close connection pools. Called during app lifespan shutdown."""
    global _pool, _sensitive_pool
    if _sensitive_pool:
        await _sensitive_pool.close()
        _sensitive_pool = None
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """FastAPI dependency: returns the primary connection pool."""
    if _pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    return _pool


def get_sensitive_pool() -> asyncpg.Pool:
    """Return isolated sensitive-data pool, falling back to primary pool."""
    return _sensitive_pool or get_pool()


def has_sensitive_pool() -> bool:
    return _sensitive_pool is not None
