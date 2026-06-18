from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Mapping

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAudienceError,
    InvalidIssuedAtError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWKClientError,
)

DEFAULT_USERNAME_CLAIM = "tapis/username"
DEFAULT_TOKEN_LEEWAY_SECONDS = 60
DEFAULT_JWKS_CACHE_SECONDS = 300
ALLOWED_ASYMMETRIC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class TapisAuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TapisAuthConfigurationError(TapisAuthError):
    pass


class TapisTokenValidationError(TapisAuthError):
    pass


@dataclass(frozen=True)
class TapisAuthSettings:
    validation_enabled: bool
    jwks_url: str
    issuer: str | None
    audience: tuple[str, ...]
    username_claim: str
    leeway_seconds: int
    allow_unverified_dev_only: bool

    @classmethod
    def from_env(cls) -> "TapisAuthSettings":
        return cls(
            validation_enabled=_env_flag("TAPIS_AUTH_VALIDATION_ENABLED", default=True),
            jwks_url=os.getenv("TAPIS_JWKS_URL", "").strip(),
            issuer=_optional_env("TAPIS_ISSUER"),
            audience=_csv_env("TAPIS_AUDIENCE"),
            username_claim=os.getenv("TAPIS_USERNAME_CLAIM", DEFAULT_USERNAME_CLAIM).strip()
            or DEFAULT_USERNAME_CLAIM,
            leeway_seconds=_positive_int_env(
                "TAPIS_TOKEN_LEEWAY_SECONDS",
                DEFAULT_TOKEN_LEEWAY_SECONDS,
            ),
            allow_unverified_dev_only=_env_flag(
                "ALLOW_UNVERIFIED_TAPIS_TOKEN_DEV_ONLY",
                default=False,
            ),
        )


@dataclass(frozen=True)
class VerifiedTapisIdentity:
    username: str
    subject: str | None
    claims: Mapping[str, Any]
    token: str
    verified: bool


class TapisTokenVerifier:
    def __init__(
        self,
        settings: TapisAuthSettings,
        *,
        jwks_client: Any | None = None,
        now: Any = time.time,
    ):
        self.settings = settings
        self._now = now
        self._jwks_client = jwks_client

        if settings.validation_enabled and not settings.jwks_url and jwks_client is None:
            raise TapisAuthConfigurationError(
                "missing_jwks_url",
                "TAPIS_JWKS_URL is required when Tapis JWT validation is enabled",
            )

        if settings.validation_enabled and self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                settings.jwks_url,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=DEFAULT_JWKS_CACHE_SECONDS,
                timeout=10,
            )

    def validate(self, token: str) -> VerifiedTapisIdentity:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise TapisTokenValidationError("missing_token", "Tapis access token is missing")

        if self.settings.validation_enabled:
            claims = self._validate_signed_token(normalized_token)
            verified = True
        elif self.settings.allow_unverified_dev_only:
            claims = self._validate_unverified_dev_token(normalized_token)
            verified = False
        else:
            raise TapisAuthConfigurationError(
                "validation_disabled",
                "Tapis JWT validation is disabled and the development-only fallback is not enabled",
            )

        self._validate_remaining_lifetime(claims)
        username, subject = self._extract_identity(claims)
        return VerifiedTapisIdentity(
            username=username,
            subject=subject,
            claims=MappingProxyType(dict(claims)),
            token=normalized_token,
            verified=verified,
        )

    def _validate_signed_token(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = str(header.get("alg") or "")
            if algorithm not in ALLOWED_ASYMMETRIC_ALGORITHMS:
                raise TapisTokenValidationError(
                    "unsupported_algorithm",
                    "Tapis token uses an unsupported signing algorithm",
                )

            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            options = self._decode_options()
            return jwt.decode(
                token,
                key=signing_key.key,
                algorithms=[algorithm],
                issuer=self.settings.issuer,
                audience=self._decode_audience(),
                leeway=self.settings.leeway_seconds,
                options=options,
            )
        except TapisTokenValidationError:
            raise
        except ExpiredSignatureError as exc:
            raise TapisTokenValidationError("expired_token", "Tapis token has expired") from exc
        except ImmatureSignatureError as exc:
            raise TapisTokenValidationError("immature_token", "Tapis token is not yet valid") from exc
        except InvalidIssuedAtError as exc:
            raise TapisTokenValidationError("invalid_iat", "Tapis token has an invalid issued-at claim") from exc
        except InvalidIssuerError as exc:
            raise TapisTokenValidationError("invalid_issuer", "Tapis token issuer is invalid") from exc
        except InvalidAudienceError as exc:
            raise TapisTokenValidationError("invalid_audience", "Tapis token audience is invalid") from exc
        except MissingRequiredClaimError as exc:
            raise TapisTokenValidationError("missing_claim", "Tapis token is missing a required claim") from exc
        except InvalidSignatureError as exc:
            raise TapisTokenValidationError("invalid_signature", "Tapis token signature is invalid") from exc
        except (DecodeError, PyJWKClientError, InvalidTokenError, ValueError, TypeError) as exc:
            raise TapisTokenValidationError("invalid_token", "Tapis token could not be verified") from exc

    def _validate_unverified_dev_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                options={
                    **self._decode_options(),
                    "verify_signature": False,
                },
                issuer=self.settings.issuer,
                audience=self._decode_audience(),
                leeway=self.settings.leeway_seconds,
            )
        except ExpiredSignatureError as exc:
            raise TapisTokenValidationError("expired_token", "Tapis token has expired") from exc
        except ImmatureSignatureError as exc:
            raise TapisTokenValidationError("immature_token", "Tapis token is not yet valid") from exc
        except InvalidIssuedAtError as exc:
            raise TapisTokenValidationError("invalid_iat", "Tapis token has an invalid issued-at claim") from exc
        except InvalidIssuerError as exc:
            raise TapisTokenValidationError("invalid_issuer", "Tapis token issuer is invalid") from exc
        except InvalidAudienceError as exc:
            raise TapisTokenValidationError("invalid_audience", "Tapis token audience is invalid") from exc
        except (DecodeError, InvalidTokenError, ValueError, TypeError) as exc:
            raise TapisTokenValidationError("invalid_token", "Tapis token is malformed") from exc

    def _decode_options(self) -> dict[str, bool | list[str]]:
        return {
            "require": ["exp"],
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_iss": bool(self.settings.issuer),
            "verify_aud": bool(self.settings.audience),
        }

    def _decode_audience(self) -> str | tuple[str, ...] | None:
        if not self.settings.audience:
            return None
        if len(self.settings.audience) == 1:
            return self.settings.audience[0]
        return self.settings.audience

    def _validate_remaining_lifetime(self, claims: Mapping[str, Any]) -> None:
        try:
            expires_at = float(claims["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TapisTokenValidationError(
                "invalid_expiry",
                "Tapis token expiry claim is invalid",
            ) from exc

        now = float(self._now())
        if expires_at <= now:
            raise TapisTokenValidationError(
                "expired_token",
                "Tapis token has expired",
            )
        if expires_at <= now + self.settings.leeway_seconds:
            raise TapisTokenValidationError(
                "near_expiry_token",
                "Tapis token is too close to expiry",
            )

    def _extract_identity(self, claims: Mapping[str, Any]) -> tuple[str, str | None]:
        claim_value = claims.get(self.settings.username_claim)
        username = claim_value.strip() if isinstance(claim_value, str) else ""
        subject_value = claims.get("sub")
        subject = subject_value.strip() if isinstance(subject_value, str) else None

        if not username and subject:
            username = subject.split("@", 1)[0].strip()
        if not username:
            raise TapisTokenValidationError(
                "missing_identity",
                "Tapis token does not identify a user",
            )
        return username, subject


@lru_cache(maxsize=1)
def get_tapis_auth_settings() -> TapisAuthSettings:
    return TapisAuthSettings.from_env()


@lru_cache(maxsize=1)
def get_tapis_verifier() -> TapisTokenVerifier:
    return TapisTokenVerifier(get_tapis_auth_settings())


def clear_tapis_auth_caches() -> None:
    get_tapis_verifier.cache_clear()
    get_tapis_auth_settings.cache_clear()


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() == "true"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    )


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed >= 0 else default
