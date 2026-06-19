"""Experiment data endpoints for supported Patra knowledge domains."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
import asyncpg

from rest_server.database import get_pool
from rest_server.models import (
    DeploymentDetail,
    ExperimentDetail,
    ExperimentImage,
    ExperimentListItem,
    ExperimentSummary,
    ExperimentUser,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])

DOMAIN_TABLES = {
    "animal-ecology": {
        "events": "camera_trap_events",
        "power": "camera_trap_power",
    },
    "digital-ag": {
        "events": "digital_ag_events",
        "power": "digital_ag_power",
    },
}

LEGACY_TABLES = {
    "events": "events",
    "power": "power_summary",
}


def _resolve_tables(domain: str) -> tuple[str, str]:
    tables = DOMAIN_TABLES.get(domain)
    if not tables:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {domain}")
    return tables["events"], tables["power"]


async def _resolve_source(conn, domain: str, source_type: str) -> tuple[str, str | None]:
    """Prefer a populated domain table, otherwise read the legacy domain table.

    Production historically stored all experiment domains in ``events`` and
    ``power_summary`` with a ``domain`` discriminator. Newer schemas split
    those records into domain-specific tables. During migration, an empty split
    table must not hide the intact legacy rows.
    """
    events_table, power_table = _resolve_tables(domain)
    configured_table = events_table if source_type == "events" else power_table
    has_domain_rows = await conn.fetchval(
        f"SELECT EXISTS (SELECT 1 FROM {configured_table} LIMIT 1)"
    )
    if has_domain_rows:
        return configured_table, None
    return LEGACY_TABLES[source_type], domain


def _add_domain_filter(
    filters: list[str],
    params: list[object],
    source_domain: str | None,
) -> None:
    if source_domain is not None:
        params.append(source_domain)
        filters.append(f"domain = ${len(params)}")


def _float(value):
    return float(value) if value is not None else None


@router.get("/{domain}/users", response_model=list[ExperimentUser])
async def list_experiment_users(
    domain: str = Path(...),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        events_table, source_domain = await _resolve_source(conn, domain, "events")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"""
            SELECT DISTINCT user_id, user_id AS username
            FROM {events_table}
            {where}
            ORDER BY user_id
        """
        rows = await conn.fetch(query, *params)
    return [ExperimentUser(user_id=row["user_id"], username=row["username"]) for row in rows]


@router.get("/{domain}/users/{user_id}/summary", response_model=list[ExperimentSummary])
async def get_user_experiment_summary(
    domain: str = Path(...),
    user_id: str = Path(...),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        events_table, source_domain = await _resolve_source(conn, domain, "events")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        params.append(user_id)
        filters.append(f"user_id = ${len(params)}")
        query = f"""
            SELECT
                experiment_id,
                user_id,
                model_id,
                device_id,
                MIN(image_receiving_timestamp) AS start_at,
                MAX(total_images) AS total_images,
                SUM(CASE WHEN image_decision = 'Save' THEN 1 ELSE 0 END) AS saved_images,
                MAX(precision) AS precision,
                MAX(recall) AS recall,
                MAX(f1_score) AS f1_score
            FROM {events_table}
            WHERE {' AND '.join(filters)}
            GROUP BY experiment_id, user_id, model_id, device_id
            ORDER BY MIN(image_receiving_timestamp) DESC
        """
        rows = await conn.fetch(query, *params)

    return [
        ExperimentSummary(
            experiment_id=row["experiment_id"],
            user_id=row["user_id"],
            model_id=row["model_id"],
            device_id=row["device_id"],
            start_at=row["start_at"].isoformat() if row["start_at"] else None,
            total_images=row["total_images"],
            saved_images=int(row["saved_images"]),
            precision=_float(row["precision"]),
            recall=_float(row["recall"]),
            f1_score=_float(row["f1_score"]),
        )
        for row in rows
    ]


@router.get("/{domain}/users/{user_id}/list", response_model=list[ExperimentListItem])
async def list_user_experiments(
    domain: str = Path(...),
    user_id: str = Path(...),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        events_table, source_domain = await _resolve_source(conn, domain, "events")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        params.append(user_id)
        filters.append(f"user_id = ${len(params)}")
        query = f"""
            SELECT DISTINCT
                experiment_id,
                MIN(image_receiving_timestamp) AS start_at,
                device_id,
                model_id
            FROM {events_table}
            WHERE {' AND '.join(filters)}
            GROUP BY experiment_id, device_id, model_id
            ORDER BY MIN(image_receiving_timestamp) DESC
        """
        rows = await conn.fetch(query, *params)

    return [
        ExperimentListItem(
            experiment_id=row["experiment_id"],
            start_at=row["start_at"].isoformat() if row["start_at"] else None,
            device_id=row["device_id"],
            model_id=row["model_id"],
        )
        for row in rows
    ]


@router.get("/{domain}/{experiment_id}", response_model=ExperimentDetail)
async def get_experiment_detail(
    domain: str = Path(...),
    experiment_id: str = Path(...),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        events_table, source_domain = await _resolve_source(conn, domain, "events")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        params.append(experiment_id)
        filters.append(f"experiment_id = ${len(params)}")
        query = f"""
            SELECT *
            FROM {events_table}
            WHERE {' AND '.join(filters)}
            ORDER BY image_count DESC
            LIMIT 1
        """
        row = await conn.fetchrow(query, *params)
    if not row:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return ExperimentDetail(
        experiment_id=row["experiment_id"],
        model_id=row["model_id"],
        device_id=row["device_id"],
        start_at=row["image_receiving_timestamp"].isoformat() if row["image_receiving_timestamp"] else None,
        total_images=row["total_images"],
        total_predictions=row["total_predictions"],
        total_ground_truth_objects=row["total_ground_truth_objects"],
        true_positives=row["true_positives"],
        false_positives=row["false_positives"],
        false_negatives=row["false_negatives"],
        precision=_float(row["precision"]),
        recall=_float(row["recall"]),
        f1_score=_float(row["f1_score"]),
        map_50=_float(row["map_50"]),
        map_50_95=_float(row["map_50_95"]),
        mean_iou=_float(row["mean_iou"]),
    )


@router.get("/{domain}/{experiment_id}/images", response_model=list[ExperimentImage])
async def get_experiment_images(
    domain: str = Path(...),
    experiment_id: str = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        events_table, source_domain = await _resolve_source(conn, domain, "events")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        params.append(experiment_id)
        filters.append(f"experiment_id = ${len(params)}")
        params.extend([limit, skip])
        query = f"""
            SELECT
                image_name, ground_truth, label, probability,
                image_decision, flattened_scores,
                image_receiving_timestamp, image_scoring_timestamp
            FROM {events_table}
            WHERE {' AND '.join(filters)}
            ORDER BY image_receiving_timestamp ASC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        rows = await conn.fetch(query, *params)

    return [
        ExperimentImage(
            image_name=row["image_name"],
            ground_truth=row["ground_truth"],
            label=row["label"],
            probability=_float(row["probability"]),
            image_decision=row["image_decision"],
            flattened_scores=row["flattened_scores"],
            image_receiving_timestamp=row["image_receiving_timestamp"].isoformat() if row["image_receiving_timestamp"] else None,
            image_scoring_timestamp=row["image_scoring_timestamp"].isoformat() if row["image_scoring_timestamp"] else None,
        )
        for row in rows
    ]


@router.get("/{domain}/{experiment_id}/power", response_model=DeploymentDetail | None)
async def get_experiment_power(
    domain: str = Path(...),
    experiment_id: str = Path(...),
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        power_table, source_domain = await _resolve_source(conn, domain, "power")
        filters: list[str] = []
        params: list[object] = []
        _add_domain_filter(filters, params, source_domain)
        params.append(experiment_id)
        filters.append(f"experiment_id = ${len(params)}")
        query = f"SELECT * FROM {power_table} WHERE {' AND '.join(filters)}"
        row = await conn.fetchrow(query, *params)
    if not row:
        return None

    return DeploymentDetail(
        experiment_id=row["experiment_id"],
        image_generating_plugin_cpu_power_consumption=_float(row["image_generating_plugin_cpu_power_consumption"]),
        image_generating_plugin_gpu_power_consumption=_float(row["image_generating_plugin_gpu_power_consumption"]),
        power_monitor_plugin_cpu_power_consumption=_float(row["power_monitor_plugin_cpu_power_consumption"]),
        power_monitor_plugin_gpu_power_consumption=_float(row["power_monitor_plugin_gpu_power_consumption"]),
        image_scoring_plugin_cpu_power_consumption=_float(row["image_scoring_plugin_cpu_power_consumption"]),
        image_scoring_plugin_gpu_power_consumption=_float(row["image_scoring_plugin_gpu_power_consumption"]),
        total_cpu_power_consumption=_float(row["total_cpu_power_consumption"]),
        total_gpu_power_consumption=_float(row["total_gpu_power_consumption"]),
    )
