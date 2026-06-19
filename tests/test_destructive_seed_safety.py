import pytest

from db.seed_production_like import _validate_seed_target


def test_destructive_seed_requires_explicit_database_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        _validate_seed_target(None, True, "patra_disposable")


def test_destructive_seed_is_disabled_by_default():
    with pytest.raises(RuntimeError, match="Refusing destructive seed"):
        _validate_seed_target(
            "postgresql://user:placeholder@localhost/patra_disposable",
            False,
            "patra_disposable",
        )


def test_destructive_seed_requires_expected_database():
    with pytest.raises(RuntimeError, match="SEED_EXPECTED_DATABASE is required"):
        _validate_seed_target(
            "postgresql://user:placeholder@localhost/patra_disposable",
            True,
            "",
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:placeholder@localhost/patradb",
        "postgresql://user:placeholder@patradb.pods.icicleai.tapis.io/other",
    ],
)
def test_destructive_seed_permanently_refuses_production(database_url):
    with pytest.raises(RuntimeError, match="permanently refuses"):
        _validate_seed_target(database_url, True, "patradb")


def test_destructive_seed_rejects_database_name_mismatch():
    with pytest.raises(RuntimeError, match="does not match"):
        _validate_seed_target(
            "postgresql://user:placeholder@localhost/patra_disposable",
            True,
            "another_database",
        )


def test_destructive_seed_accepts_only_matching_disposable_database():
    assert (
        _validate_seed_target(
            "postgresql://user:placeholder@localhost/patra_disposable",
            True,
            "patra_disposable",
        )
        == "patra_disposable"
    )
