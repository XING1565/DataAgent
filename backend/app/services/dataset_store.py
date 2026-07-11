from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Any

import pandas as pd
from fastapi import UploadFile

from app.schemas.dataset import ColumnSchema, DatasetUploadResponse, QualitySummary


class UnsupportedFileTypeError(ValueError):
    pass


class DatasetParseError(ValueError):
    pass


class DatasetNotFoundError(ValueError):
    pass


class DatasetStore:
    supported_extensions = {".csv", ".xlsx"}

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data"
        self.uploads_dir = self.base_dir / "uploads"
        self.datasets_dir = self.base_dir / "datasets"
        self.sqlite_dir = self.base_dir / "sqlite"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_dir.mkdir(parents=True, exist_ok=True)

    async def create_from_upload(self, file: UploadFile) -> DatasetUploadResponse:
        filename = file.filename or "dataset"
        extension = Path(filename).suffix.lower()
        if extension not in self.supported_extensions:
            raise UnsupportedFileTypeError("不支持的文件格式，请上传 CSV 或 XLSX 文件。")

        dataset_id = self._generate_dataset_id()
        stored_path = self.uploads_dir / f"{dataset_id}_{self._safe_filename(filename)}"
        self._save_upload(file, stored_path)

        dataframe = self._read_dataframe(stored_path, extension)
        response = self._build_response(dataset_id, filename, dataframe)
        self._save_metadata(dataset_id, response)
        self._save_sqlite_table(dataset_id, dataframe)
        return response

    def create_from_path(self, source_path: Path) -> DatasetUploadResponse:
        filename = source_path.name
        extension = source_path.suffix.lower()
        if extension not in self.supported_extensions:
            raise UnsupportedFileTypeError("不支持的文件格式，请上传 CSV 或 XLSX 文件。")

        dataset_id = self._generate_dataset_id()
        stored_path = self.uploads_dir / f"{dataset_id}_{self._safe_filename(filename)}"
        shutil.copyfile(source_path, stored_path)

        dataframe = self._read_dataframe(stored_path, extension)
        response = self._build_response(dataset_id, filename, dataframe)
        self._save_metadata(dataset_id, response)
        self._save_sqlite_table(dataset_id, dataframe)
        return response

    def load_dataframe(self, dataset_id: str) -> pd.DataFrame:
        stored_path = self._find_dataset_file(dataset_id)
        return self._read_dataframe(stored_path, stored_path.suffix.lower())

    def sqlite_path(self, dataset_id: str) -> Path:
        return self.sqlite_dir / f"{dataset_id}.db"

    def load_schema(self, dataset_id: str) -> list[ColumnSchema]:
        metadata_path = self.datasets_dir / f"{dataset_id}.json"
        if not metadata_path.exists():
            raise DatasetNotFoundError("数据集不存在，请先上传数据文件。")

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            return [ColumnSchema(**column) for column in metadata.get("schema", [])]
        except Exception as exc:
            raise DatasetParseError("数据集元数据读取失败，请重新上传数据文件。") from exc

    def _save_upload(self, file: UploadFile, destination: Path) -> None:
        try:
            with destination.open("wb") as output:
                shutil.copyfileobj(file.file, output)
        finally:
            file.file.close()

    def _read_dataframe(self, path: Path, extension: str) -> pd.DataFrame:
        try:
            if extension == ".csv":
                return pd.read_csv(path)
            return pd.read_excel(path, sheet_name=0)
        except Exception as exc:
            raise DatasetParseError("文件解析失败，请确认文件内容是有效的 CSV 或 XLSX 数据。") from exc

    def _build_response(
        self,
        dataset_id: str,
        filename: str,
        dataframe: pd.DataFrame,
    ) -> DatasetUploadResponse:
        schema = [self._build_column_schema(dataframe, column) for column in dataframe.columns]
        preview = self._json_records(dataframe.head(10))
        quality_summary = QualitySummary(
            missing_cells=int(dataframe.isna().sum().sum()),
            duplicate_rows=int(dataframe.duplicated().sum()),
            memory_usage_bytes=int(dataframe.memory_usage(deep=True).sum()),
        )

        return DatasetUploadResponse(
            dataset_id=dataset_id,
            filename=filename,
            rows=int(dataframe.shape[0]),
            columns=int(dataframe.shape[1]),
            columns_schema=schema,
            preview=preview,
            quality_summary=quality_summary,
        )

    def _build_column_schema(self, dataframe: pd.DataFrame, column: Any) -> ColumnSchema:
        series = dataframe[column]
        row_count = len(series)
        missing_count = int(series.isna().sum())
        return ColumnSchema(
            name=str(column),
            dtype=str(series.dtype),
            non_null_count=int(series.notna().sum()),
            missing_count=missing_count,
            missing_ratio=round(missing_count / row_count, 6) if row_count else 0.0,
        )

    def _json_records(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        cleaned = dataframe.astype(object).where(pd.notna(dataframe), None)
        records = cleaned.to_dict(orient="records")
        return [{str(key): value for key, value in record.items()} for record in records]

    def _save_metadata(self, dataset_id: str, response: DatasetUploadResponse) -> None:
        metadata_path = self.datasets_dir / f"{dataset_id}.json"
        metadata_path.write_text(
            response.model_dump_json(indent=2, by_alias=True),
            encoding="utf-8",
        )

    def _save_sqlite_table(self, dataset_id: str, dataframe: pd.DataFrame) -> None:
        from app.data_sources.sqlite_source import MAIN_TABLE, SQLiteDataSource

        SQLiteDataSource(self.sqlite_path(dataset_id), name=dataset_id).initialize_from_dataframe(
            dataframe,
            table_name=MAIN_TABLE,
        )

    def _generate_dataset_id(self) -> str:
        date_part = datetime.now().strftime("%Y%m%d")
        return f"ds_{date_part}_{token_hex(4)}"

    def _safe_filename(self, filename: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._")
        return safe_name or "dataset"

    def _find_dataset_file(self, dataset_id: str) -> Path:
        matches = sorted(self.uploads_dir.glob(f"{dataset_id}_*"))
        for path in matches:
            if path.suffix.lower() in self.supported_extensions:
                return path
        raise DatasetNotFoundError("数据集不存在，请先上传数据文件。")
