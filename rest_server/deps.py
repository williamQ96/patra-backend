import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Mapping

from fastapi import Header, HTTPException, Request

from rest_server.tapis_auth import (
    TapisAuthConfigurationError,
    TapisTokenValidationError,
    get_tapis_verifier,
)

log = logging.getLogger(__name__)

TAPIS_TOKEN_HEADER = "X-Tapis-Token"
AUTHORIZATION_HEADER = "Authorization"
ASSET_INGEST_ORG_HEADER = "X-Asset-Org"
ASSET_INGEST_KEY_HEADER = "X-Asset-Api-Key"
ASSET_INGEST_KEYS_ENV = "PATRA_ASSET_INGEST_KEYS_JSON"
PATRA_USERNAME_HEADER = "X-Patra-Username"
PATRA_ROLE_HEADER = "X-Patra-Role"
PATRA_ADMIN_USERS_ENV = "PATRA_ADMIN_USERS"
DEFAULT_ADMIN_USERS = frozenset({"williamq96"})


@dataclass(frozen=True)
class AssetIngestPrincipal:
    organization: str


@dataclass(frozen=True)
class PatraActor:
    username: str | None
    role: str = "guest"
    auth_type: str = "guest"
    subject: str | None = None
    claims: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)
    token: str | None = field(default=None, repr=False, compare=False)

    @property
    def is_authenticated(self) -> bool:
        return self.auth_type != "guest"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_include_private(request: Request) -> bool:
    """Return private records only for a server-validated Tapis identity."""
    return get_request_actor(request).is_authenticated


@lru_cache(maxsize=1)
def get_admin_users() -> set[str]:
    configured = os.getenv(PATRA_ADMIN_USERS_ENV, "").strip()
    values = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return set(DEFAULT_ADMIN_USERS) | values


def get_request_actor(request: Request) -> PatraActor:
    cached_actor = getattr(request.state, "patra_actor", None)
    if isinstance(cached_actor, PatraActor):
        return cached_actor

    token, credential_source = _extract_tapis_credential(request)
    claimed_username = (request.headers.get(PATRA_USERNAME_HEADER) or "").strip()
    claimed_role = (request.headers.get(PATRA_ROLE_HEADER) or "").strip()

    if not token:
        if claimed_username or claimed_role:
            log.warning("Ignoring client-supplied Patra identity headers without a validated token")
        actor = PatraActor(username=None)
        request.state.patra_actor = actor
        return actor

    try:
        identity = get_tapis_verifier().validate(token)
    except TapisTokenValidationError as exc:
        log.warning(
            "Rejected Tapis credential from %s (%s)",
            credential_source,
            exc.code,
        )
        raise HTTPException(status_code=401, detail="Invalid Tapis access token") from exc
    except TapisAuthConfigurationError as exc:
        log.error("Tapis authentication is unavailable (%s)", exc.code)
        raise HTTPException(status_code=503, detail="Tapis authentication is not configured") from exc

    if claimed_username and claimed_username.lower() != identity.username.lower():
        log.warning("Ignoring client identity header that does not match the validated Tapis token")
    if claimed_role:
        log.warning("Ignoring client role header; roles are derived server-side")

    normalized_username = identity.username.lower()
    actor = PatraActor(
        username=identity.username,
        role="admin" if normalized_username in get_admin_users() else "user",
        auth_type="tapis" if identity.verified else "tapis_unverified_dev",
        subject=identity.subject,
        claims=identity.claims,
        token=identity.token,
    )
    request.state.patra_actor = actor
    return actor


def require_authenticated_actor(request: Request) -> PatraActor:
    actor = get_request_actor(request)
    if not actor.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return actor


def require_admin_actor(request: Request) -> PatraActor:
    actor = require_authenticated_actor(request)
    if not actor.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return actor


@lru_cache(maxsize=1)
def get_asset_ingest_keys() -> dict[str, str]:
    raw = os.getenv(ASSET_INGEST_KEYS_ENV, "").strip()
    if not raw:
        return {}
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{ASSET_INGEST_KEYS_ENV} must be valid JSON") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"{ASSET_INGEST_KEYS_ENV} must be a JSON object")
    normalized: dict[str, str] = {}
    for org, secret in config.items():
        if not isinstance(org, str) or not isinstance(secret, str) or not org.strip() or not secret.strip():
            raise RuntimeError(f"{ASSET_INGEST_KEYS_ENV} entries must map non-empty strings to non-empty strings")
        normalized[org.strip()] = secret.strip()
    return normalized


def _extract_tapis_credential(request: Request) -> tuple[str | None, str | None]:
    authorization = (request.headers.get(AUTHORIZATION_HEADER) or "").strip()
    if authorization:
        scheme, separator, value = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not value.strip():
            raise HTTPException(status_code=401, detail="Authorization header must use Bearer authentication")
        return value.strip(), "authorization"

    compatibility_token = (request.headers.get(TAPIS_TOKEN_HEADER) or "").strip()
    if compatibility_token:
        return compatibility_token, "x-tapis-token"
    return None, None


def _extract_asset_api_key(authorization: str | None, x_asset_api_key: str | None) -> str | None:
    if x_asset_api_key:
        return x_asset_api_key.strip()
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _matches_configured_secret(presented: str, configured: str) -> bool:
    if configured.startswith("sha256:"):
        presented_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
        return hmac.compare_digest(presented_hash, configured.removeprefix("sha256:"))
    return hmac.compare_digest(presented, configured)


def require_asset_ingest_principal(
    request: Request,
    x_asset_org: str | None = Header(default=None, alias=ASSET_INGEST_ORG_HEADER),
    x_asset_api_key: str | None = Header(default=None, alias=ASSET_INGEST_KEY_HEADER),
    x_tapis_token: str | None = Header(default=None, alias=TAPIS_TOKEN_HEADER),
    authorization: str | None = Header(default=None),
) -> AssetIngestPrincipal:
    has_asset_api_key_context = bool((x_asset_org or "").strip() or (x_asset_api_key or "").strip())
    if (x_tapis_token or "").strip() or ((authorization or "").strip() and not has_asset_api_key_context):
        actor = require_authenticated_actor(request)
        return AssetIngestPrincipal(organization="tapis")

    try:
        configured_keys = get_asset_ingest_keys()
    except RuntimeError as exc:
        log.error("Asset ingest auth config invalid: %s", exc)
        raise HTTPException(status_code=503, detail="Asset ingest API is not configured")
    if not configured_keys:
        raise HTTPException(status_code=503, detail="Asset ingest API is not configured")
    organization = (x_asset_org or "").strip()
    presented_key = _extract_asset_api_key(authorization, x_asset_api_key)
    if not organization or not presented_key:
        raise HTTPException(status_code=401, detail="Missing asset ingest credentials")
    configured_secret = configured_keys.get(organization)
    if not configured_secret or not _matches_configured_secret(presented_key, configured_secret):
        raise HTTPException(status_code=401, detail="Invalid asset ingest credentials")
    return AssetIngestPrincipal(organization=organization)
