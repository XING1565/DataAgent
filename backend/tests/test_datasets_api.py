from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.v1 import datasets
from app.main import app
from app.services.agent_event_store import AgentEventStore
from app.services.dataset_store import DatasetStore


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_dataset_store(tmp_path: Path) -> None:
    original_store = datasets.dataset_store
    original_event_store = datasets.agent_event_store
    base_dir = tmp_path / "data"
    datasets.dataset_store = DatasetStore(base_dir=base_dir)
    datasets.agent_event_store = AgentEventStore(base_dir=base_dir)
    try:
        yield
    finally:
        datasets.dataset_store = original_store
        datasets.agent_event_store = original_event_store


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_xlsx_returns_dataset_summary(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "sales.xlsx"
    dataframe = pd.DataFrame({"product": ["A", "B"], "amount": [1200, 800]})
    dataframe.to_excel(xlsx_path, index=False)

    with xlsx_path.open("rb") as file:
        response = client.post(
            "/api/v1/datasets",
            files={"file": ("sales.xlsx", file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["filename"] == "sales.xlsx"
    assert body["rows"] == 2
    assert body["columns"] == 2
    assert body["preview"] == [{"product": "A", "amount": 1200}, {"product": "B", "amount": 800}]
    assert body["schema"][0]["name"] == "product"
    events = datasets.agent_event_store.get_events()
    assert events[0].type == "dataset_uploaded"
    assert events[0].dataset_id == body["dataset_id"]


def test_upload_txt_returns_friendly_error() -> None:
    response = client.post(
        "/api/v1/datasets",
        files={"file": ("sales.txt", b"not tabular", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "不支持的文件格式，请上传 CSV 或 XLSX 文件。"}


def test_upload_corrupted_xlsx_returns_friendly_error() -> None:
    response = client.post(
        "/api/v1/datasets",
        files={"file": ("sales.xlsx", b"not really an xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "文件解析失败，请确认文件内容是有效的 CSV 或 XLSX 数据。"}
