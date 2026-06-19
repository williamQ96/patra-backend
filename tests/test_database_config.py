import ssl

import pytest

from rest_server import database


def test_build_connection_options_rewrites_tapis_pods_to_443_without_direct_tls():
    dsn, ssl_arg, direct_tls = database._build_connection_options(
        "postgresql://user:pass@patradb.pods.icicleai.tapis.io:5432/patradb?sslmode=require"
    )

    assert dsn == "postgresql://user:pass@patradb.pods.icicleai.tapis.io:443/patradb"
    assert isinstance(ssl_arg, ssl.SSLContext)
    assert direct_tls is False


def test_build_connection_options_uses_regular_tls_for_non_pod_hosts():
    dsn, ssl_arg, direct_tls = database._build_connection_options(
        "postgresql://user:pass@localhost:5432/patradb?sslmode=require"
    )

    assert dsn == "postgresql://user:pass@localhost:5432/patradb"
    assert isinstance(ssl_arg, ssl.SSLContext)
    assert direct_tls is False


@pytest.mark.asyncio
async def test_init_pool_disables_direct_tls_for_tapis_pods(monkeypatch):
    captured = {}
    fake_pool = object()

    async def fake_create_pool(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_pool

    async def fake_ensure_schema(pool):
        captured["schema_pool"] = pool

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@patradb.pods.icicleai.tapis.io:5432/patradb?sslmode=require",
    )
    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(database, "ensure_schema", fake_ensure_schema)
    database._pool = None

    pool = await database.init_pool()

    assert pool is fake_pool
    assert captured["args"] == ("postgresql://user:pass@patradb.pods.icicleai.tapis.io:443/patradb",)
    assert captured["kwargs"]["direct_tls"] is False
    assert isinstance(captured["kwargs"]["ssl"], ssl.SSLContext)
    assert captured["schema_pool"] is fake_pool

    database._pool = None


@pytest.mark.asyncio
async def test_init_sensitive_pool_uses_separate_database_url(monkeypatch):
    captured = {}
    fake_pool = object()

    async def fake_create_pool(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_pool

    async def fake_ensure_schema(pool):
        captured["schema_pool"] = pool

    monkeypatch.setenv(
        "SENSITIVE_DATABASE_URL",
        "postgresql://user:pass@patradb.pods.icicleai.tapis.io:5432/patradev-db?sslmode=require",
    )
    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(database, "ensure_schema", fake_ensure_schema)
    database._sensitive_pool = None

    pool = await database.init_sensitive_pool()

    assert pool is fake_pool
    assert captured["args"] == ("postgresql://user:pass@patradb.pods.icicleai.tapis.io:443/patradev-db",)
    assert captured["kwargs"]["direct_tls"] is False
    assert isinstance(captured["kwargs"]["ssl"], ssl.SSLContext)
    assert captured["schema_pool"] is fake_pool

    database._sensitive_pool = None


@pytest.mark.asyncio
async def test_schema_bootstrap_can_be_disabled_for_production(monkeypatch):
    fake_pool = object()
    schema_calls = []

    async def fake_create_pool(*args, **kwargs):
        return fake_pool

    async def fake_ensure_schema(pool):
        schema_calls.append(pool)

    monkeypatch.setenv("DB_BOOTSTRAP_SCHEMA_ENABLED", "false")
    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(database, "ensure_schema", fake_ensure_schema)

    pool = await database._create_pool_from_url(
        "postgresql://user:pass@localhost:5432/patradb",
        label="Production",
    )

    assert pool is fake_pool
    assert schema_calls == []


def test_get_sensitive_pool_falls_back_to_primary(monkeypatch):
    fake_pool = object()
    database._pool = fake_pool
    database._sensitive_pool = None

    assert database.get_sensitive_pool() is fake_pool

    database._pool = None
