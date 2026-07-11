from __future__ import annotations

from typing import TYPE_CHECKING

from app.data_sources.file_source import FileDataSource

if TYPE_CHECKING:
    from app.services.dataset_store import DatasetStore


class DataSourceRegistry:
    def __init__(self, dataset_store: "DatasetStore") -> None:
        self.dataset_store = dataset_store

    def get(self, dataset_id: str) -> FileDataSource:
        return FileDataSource(dataset_id=dataset_id, dataset_store=self.dataset_store)
