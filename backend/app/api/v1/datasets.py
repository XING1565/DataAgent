from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.dataset import DatasetUploadResponse
from app.services.agent_event_store import AgentEventStore
from app.services.dataset_store import DatasetParseError, DatasetStore, UnsupportedFileTypeError


router = APIRouter(prefix="/datasets", tags=["datasets"])
dataset_store = DatasetStore()
agent_event_store = AgentEventStore()


@router.post("", response_model=DatasetUploadResponse)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetUploadResponse:
    try:
        response = await dataset_store.create_from_upload(file)
        agent_event_store.append_event(
            type="dataset_uploaded",
            title="数据集上传完成",
            summary=f"{response.filename} · {response.rows} 行 x {response.columns} 列",
            status="success",
            dataset_id=response.dataset_id,
            metadata={
                "filename": response.filename,
                "rows": response.rows,
                "columns": response.columns,
                "missing_cells": response.quality_summary.missing_cells,
                "duplicate_rows": response.quality_summary.duplicate_rows,
            },
        )
        return response
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatasetParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
