from typing import Optional

from pydantic import BaseModel


# --- Model Cards (matches rest_server MCReconstructor output) ---


class ModelCardSummary(BaseModel):
    """List endpoint: mc_id, name, categories, author, version, short_description."""

    mc_id: int
    name: str
    categories: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    short_description: Optional[str] = None


class AIModel(BaseModel):
    """Nested model from models table. model_id is integer per schema."""

    model_id: int
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    location: Optional[str] = None
    license: Optional[str] = None
    framework: Optional[str] = None
    model_type: Optional[str] = None
    test_accuracy: Optional[float] = None


class ModelCardDetail(BaseModel):
    """Detail endpoint: matches reconstruct() format. external_id is integer per schema."""

    external_id: int
    name: str
    version: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    keywords: Optional[str] = None
    author: Optional[str] = None
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    input_type: Optional[str] = None
    categories: Optional[str] = None
    citation: Optional[str] = None
    foundational_model: Optional[str] = None
    ai_model: Optional[AIModel] = None


# --- Datasheets ---


class DatasheetSummary(BaseModel):
    """List endpoint."""

    identifier: int
    title: str
    creator: Optional[str] = None
    category: Optional[str] = None


class DatasheetDetail(BaseModel):
    """Detail endpoint: all datasheet columns."""

    identifier: int
    creator: Optional[str] = None
    title: str
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    resource_type: Optional[str] = None
    size: Optional[str] = None
    format: Optional[str] = None
    version: Optional[str] = None
    rights: Optional[str] = None
    description: Optional[str] = None
    geo_location: Optional[str] = None
    category: Optional[str] = None
    is_private: bool = False
    updated_at: Optional[str] = None
    alternate_identifier: Optional[str] = None
    related_identifier: Optional[str] = None
    model_card_id: Optional[int] = None
    dataset_schema_id: Optional[int] = None
