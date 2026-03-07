from fastapi import APIRouter, Depends, HTTPException, Query

import asyncpg

from api_server.database import get_pool
from api_server.deps import get_include_private
from api_server.models import DatasheetDetail, DatasheetSummary

router = APIRouter(tags=["datasheets"])


@router.get("/datasheets", response_model=list[DatasheetSummary])
async def list_datasheets(
    pool: asyncpg.Pool = Depends(get_pool),
    include_private: bool = Depends(get_include_private),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List all datasheets. JWT bearer shows private; unauthenticated shows only public."""
    where = "" if include_private else " WHERE is_private = false"
    query = f"""
        SELECT identifier, title, creator, category
        FROM datasheets
        {where}
        ORDER BY identifier
        LIMIT $1 OFFSET $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit, skip)
    return [
        DatasheetSummary(
            identifier=r["identifier"],
            title=r["title"],
            creator=r["creator"],
            category=r["category"],
        )
        for r in rows
    ]


@router.get("/datasheet/{identifier}", response_model=DatasheetDetail)
async def get_datasheet(
    identifier: int,
    pool: asyncpg.Pool = Depends(get_pool),
    include_private: bool = Depends(get_include_private),
):
    """Get a single datasheet by identifier. Returns 404 if private and caller has no JWT."""
    query = """
        SELECT identifier, creator, title, publisher, publication_year,
               resource_type, size, format, version, rights, description,
               geo_location, category, is_private, updated_at,
               alternate_identifier, related_identifier,
               model_card_id, dataset_schema_id
        FROM datasheets
        WHERE identifier = $1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, identifier)
    if not row:
        raise HTTPException(status_code=404, detail="Datasheet not found")
    if row["is_private"] and not include_private:
        raise HTTPException(status_code=404, detail="Datasheet not found")
    return DatasheetDetail(
        identifier=row["identifier"],
        creator=row["creator"],
        title=row["title"],
        publisher=row["publisher"],
        publication_year=row["publication_year"],
        resource_type=row["resource_type"],
        size=row["size"],
        format=row["format"],
        version=row["version"],
        rights=row["rights"],
        description=row["description"],
        geo_location=row["geo_location"],
        category=row["category"],
        is_private=row["is_private"],
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
        alternate_identifier=row["alternate_identifier"],
        related_identifier=row["related_identifier"],
        model_card_id=row["model_card_id"],
        dataset_schema_id=row["dataset_schema_id"],
    )
