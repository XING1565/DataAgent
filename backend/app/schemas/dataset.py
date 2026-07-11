from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    non_null_count: int
    missing_count: int
    missing_ratio: float


class QualitySummary(BaseModel):
    missing_cells: int
    duplicate_rows: int
    memory_usage_bytes: int


class DatasetUploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dataset_id: str
    filename: str
    rows: int
    columns: int
    columns_schema: list[ColumnSchema] = Field(alias="schema")
    preview: list[dict[str, Any]]
    quality_summary: QualitySummary
