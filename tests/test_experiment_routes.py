from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from rest_server.routes.experiments import (
    get_experiment_detail,
    get_experiment_power,
    list_experiment_users,
)


class FakeExperimentConnection:
    def __init__(self, *, split_table_has_rows: bool, rows=None, row=None):
        self.split_table_has_rows = split_table_has_rows
        self.rows = rows or []
        self.row = row
        self.queries = []

    async def fetchval(self, query, *args):
        self.queries.append(("fetchval", query, args))
        return self.split_table_has_rows

    async def fetch(self, query, *args):
        self.queries.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query, *args):
        self.queries.append(("fetchrow", query, args))
        return self.row


class FakeExperimentPool:
    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


@pytest.mark.asyncio
async def test_animal_ecology_users_fall_back_to_legacy_events():
    connection = FakeExperimentConnection(
        split_table_has_rows=False,
        rows=[{"user_id": "alice", "username": "alice"}],
    )

    result = await list_experiment_users(
        domain="animal-ecology",
        pool=FakeExperimentPool(connection),
    )

    assert result[0].username == "alice"
    _, query, args = connection.queries[-1]
    assert "FROM events" in query
    assert "domain = $1" in query
    assert args == ("animal-ecology",)


@pytest.mark.asyncio
async def test_populated_domain_table_is_preferred():
    connection = FakeExperimentConnection(
        split_table_has_rows=True,
        rows=[{"user_id": "alice", "username": "alice"}],
    )

    await list_experiment_users(
        domain="animal-ecology",
        pool=FakeExperimentPool(connection),
    )

    _, query, args = connection.queries[-1]
    assert "FROM camera_trap_events" in query
    assert "domain =" not in query
    assert args == ()


@pytest.mark.asyncio
async def test_legacy_experiment_detail_is_scoped_to_requested_domain():
    timestamp = datetime(2026, 6, 17, tzinfo=timezone.utc)
    connection = FakeExperimentConnection(
        split_table_has_rows=False,
        row={
            "experiment_id": "exp-1",
            "model_id": "model-1",
            "device_id": "device-1",
            "image_receiving_timestamp": timestamp,
            "total_images": 12,
            "total_predictions": 12,
            "total_ground_truth_objects": 6,
            "true_positives": 5,
            "false_positives": 1,
            "false_negatives": 1,
            "precision": Decimal("0.8"),
            "recall": Decimal("0.7"),
            "f1_score": Decimal("0.75"),
            "map_50": Decimal("0.9"),
            "map_50_95": Decimal("0.6"),
            "mean_iou": Decimal("0.5"),
        },
    )

    result = await get_experiment_detail(
        domain="animal-ecology",
        experiment_id="exp-1",
        pool=FakeExperimentPool(connection),
    )

    assert result.experiment_id == "exp-1"
    _, query, args = connection.queries[-1]
    assert "FROM events" in query
    assert "domain = $1" in query
    assert "experiment_id = $2" in query
    assert args == ("animal-ecology", "exp-1")


@pytest.mark.asyncio
async def test_legacy_power_lookup_is_scoped_to_requested_domain():
    connection = FakeExperimentConnection(
        split_table_has_rows=False,
        row={
            "experiment_id": "exp-1",
            "image_generating_plugin_cpu_power_consumption": Decimal("1"),
            "image_generating_plugin_gpu_power_consumption": Decimal("2"),
            "power_monitor_plugin_cpu_power_consumption": Decimal("3"),
            "power_monitor_plugin_gpu_power_consumption": Decimal("4"),
            "image_scoring_plugin_cpu_power_consumption": Decimal("5"),
            "image_scoring_plugin_gpu_power_consumption": Decimal("6"),
            "total_cpu_power_consumption": Decimal("9"),
            "total_gpu_power_consumption": Decimal("12"),
        },
    )

    result = await get_experiment_power(
        domain="animal-ecology",
        experiment_id="exp-1",
        pool=FakeExperimentPool(connection),
    )

    assert result.experiment_id == "exp-1"
    _, query, args = connection.queries[-1]
    assert "FROM power_summary" in query
    assert "domain = $1" in query
    assert "experiment_id = $2" in query
    assert args == ("animal-ecology", "exp-1")
