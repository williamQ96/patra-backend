from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from rest_server.deps import require_authenticated_actor
from rest_server.tapis_auth import (
    TapisAuthConfigurationError,
    TapisAuthSettings,
    TapisTokenValidationError,
    TapisTokenVerifier,
)
from tests.conftest import (
    StaticTestJwksClient,
    TEST_TAPIS_AUDIENCE,
    TEST_TAPIS_ISSUER,
    make_test_tapis_token,
)


@pytest.fixture()
def verifier() -> TapisTokenVerifier:
    return TapisTokenVerifier(
        TapisAuthSettings(
            validation_enabled=True,
            jwks_url="https://jwks.example.test/keys",
            issuer=TEST_TAPIS_ISSUER,
            audience=(TEST_TAPIS_AUDIENCE,),
            username_claim="tapis/username",
            leeway_seconds=60,
            allow_unverified_dev_only=False,
        ),
        jwks_client=StaticTestJwksClient(),
    )


@pytest.fixture()
def auth_client() -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected(actor=Depends(require_authenticated_actor)):
        return {
            "username": actor.username,
            "role": actor.role,
            "auth_type": actor.auth_type,
            "subject": actor.subject,
        }

    return TestClient(app)


def test_valid_signed_token_is_accepted(verifier):
    identity = verifier.validate(make_test_tapis_token("verified-user"))
    assert identity.username == "verified-user"
    assert identity.subject == "verified-user@tacc"
    assert identity.verified is True


@pytest.mark.parametrize(
    ("token", "code"),
    [
        ("not-a-jwt", "invalid_token"),
        (make_test_tapis_token(expires_in_seconds=-10), "expired_token"),
        (make_test_tapis_token(expires_in_seconds=30), "near_expiry_token"),
        (make_test_tapis_token(issuer="https://wrong-issuer.example"), "invalid_issuer"),
        (make_test_tapis_token(audience="wrong-audience"), "invalid_audience"),
    ],
)
def test_invalid_tokens_are_rejected(verifier, token, code):
    with pytest.raises(TapisTokenValidationError) as exc_info:
        verifier.validate(token)
    assert exc_info.value.code == code


def test_token_signed_by_an_untrusted_key_is_rejected(verifier):
    untrusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_test_tapis_token("forged-user", private_key=untrusted_key)

    with pytest.raises(TapisTokenValidationError) as exc_info:
        verifier.validate(token)
    assert exc_info.value.code == "invalid_signature"


@pytest.mark.parametrize("claim", ["nbf", "iat"])
def test_future_time_claims_are_rejected(verifier, claim):
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = make_test_tapis_token(extra_claims={claim: future})

    with pytest.raises(TapisTokenValidationError) as exc_info:
        verifier.validate(token)
    assert exc_info.value.code == "immature_token"


def test_validation_fails_closed_without_jwks_configuration():
    with pytest.raises(TapisAuthConfigurationError) as exc_info:
        TapisTokenVerifier(
            TapisAuthSettings(
                validation_enabled=True,
                jwks_url="",
                issuer=None,
                audience=(),
                username_claim="tapis/username",
                leeway_seconds=60,
                allow_unverified_dev_only=False,
            )
        )
    assert exc_info.value.code == "missing_jwks_url"


def test_missing_token_is_rejected_on_protected_route(auth_client):
    response = auth_client.get("/protected")
    assert response.status_code == 401


def test_authorization_bearer_is_preferred_and_identity_headers_cannot_impersonate(auth_client):
    alice_token = make_test_tapis_token("alice")
    admin_compatibility_token = make_test_tapis_token("williamq96")
    response = auth_client.get(
        "/protected",
        headers={
            "Authorization": f"Bearer {alice_token}",
            "X-Tapis-Token": admin_compatibility_token,
            "X-Patra-Username": "williamq96",
            "X-Patra-Role": "admin",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice",
        "role": "user",
        "auth_type": "tapis",
        "subject": "alice@tacc",
    }


def test_x_tapis_token_remains_a_valid_compatibility_fallback(auth_client):
    response = auth_client.get(
        "/protected",
        headers={"X-Tapis-Token": make_test_tapis_token("compat-user")},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "compat-user"


def test_malformed_token_is_rejected_without_logging_raw_token(auth_client, caplog):
    raw_token = "malformed-sensitive-token-value"
    with caplog.at_level(logging.WARNING):
        response = auth_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {raw_token}"},
        )

    assert response.status_code == 401
    assert raw_token not in caplog.text
    assert "invalid_token" in caplog.text


def test_development_only_unverified_fallback_is_disabled_by_default():
    verifier = TapisTokenVerifier(
        TapisAuthSettings(
            validation_enabled=False,
            jwks_url="",
            issuer=None,
            audience=(),
            username_claim="tapis/username",
            leeway_seconds=60,
            allow_unverified_dev_only=False,
        )
    )

    with pytest.raises(TapisAuthConfigurationError) as exc_info:
        verifier.validate(make_test_tapis_token("dev-user"))
    assert exc_info.value.code == "validation_disabled"
