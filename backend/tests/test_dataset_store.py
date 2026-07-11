from pathlib import Path

import pandas as pd

from app.data_sources.file_source import FileDataSource
from app.services.dataset_store import DatasetNotFoundError, DatasetStore, UnsupportedFileTypeError


def test_create_from_csv_returns_schema_preview_and_quality(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "product,amount,region\nA,100,East\nB,,West\nB,,West\n",
        encoding="utf-8",
    )
    store = DatasetStore(base_dir=tmp_path / "data")

    response = store.create_from_path(csv_path)

    assert response.dataset_id.startswith("ds_")
    assert response.filename == "sales.csv"
    assert response.rows == 3
    assert response.columns == 3
    assert response.preview[0] == {"product": "A", "amount": 100.0, "region": "East"}
    assert response.preview[1]["amount"] is None
    assert response.quality_summary.missing_cells == 2
    assert response.quality_summary.duplicate_rows == 1

    amount_schema = next(column for column in response.columns_schema if column.name == "amount")
    assert amount_schema.non_null_count == 1
    assert amount_schema.missing_count == 2
    assert amount_schema.missing_ratio == 0.666667
    assert store.sqlite_path(response.dataset_id).exists()


def test_create_from_xlsx_preview_is_limited_to_ten_rows(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "sales.xlsx"
    dataframe = pd.DataFrame({"product": [f"P{i}" for i in range(12)], "amount": range(12)})
    dataframe.to_excel(xlsx_path, index=False)
    store = DatasetStore(base_dir=tmp_path / "data")

    response = store.create_from_path(xlsx_path)

    assert response.rows == 12
    assert len(response.preview) == 10
    assert response.preview[0] == {"product": "P0", "amount": 0}
    assert response.preview[-1] == {"product": "P9", "amount": 9}
    assert store.sqlite_path(response.dataset_id).exists()


def test_load_dataframe_by_dataset_id(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,amount\nA,100\nB,200\n", encoding="utf-8")
    store = DatasetStore(base_dir=tmp_path / "data")
    created = store.create_from_path(csv_path)

    dataframe = store.load_dataframe(created.dataset_id)

    assert dataframe.to_dict(orient="records") == [
        {"product": "A", "amount": 100},
        {"product": "B", "amount": 200},
    ]


def test_file_data_source_lists_main_table_and_executes_sql(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,amount\nA,100\nB,200\nC,300\n", encoding="utf-8")
    store = DatasetStore(base_dir=tmp_path / "data")
    created = store.create_from_path(csv_path)
    source = FileDataSource(created.dataset_id, store)

    count_df, count_error = source.execute_query("SELECT COUNT(*) AS cnt FROM main_table")
    rows_df, rows_error = source.execute_query("SELECT * FROM main_table LIMIT 3")

    assert source.list_tables() == ["main_table"]
    assert count_error == ""
    assert int(count_df.iloc[0]["cnt"]) == 3
    assert rows_error == ""
    assert len(rows_df) == 3


def test_file_data_source_invalid_sql_returns_error_string(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("product,amount\nA,100\n", encoding="utf-8")
    store = DatasetStore(base_dir=tmp_path / "data")
    created = store.create_from_path(csv_path)
    source = FileDataSource(created.dataset_id, store)

    dataframe, error = source.execute_query("SELECT missing_column FROM main_table")

    assert dataframe.empty
    assert error


def test_load_dataframe_missing_dataset_raises_friendly_error(tmp_path: Path) -> None:
    store = DatasetStore(base_dir=tmp_path / "data")

    try:
        store.load_dataframe("ds_missing")
    except DatasetNotFoundError as exc:
        assert str(exc) == "数据集不存在，请先上传数据文件。"
    else:
        raise AssertionError("DatasetNotFoundError was not raised")


def test_unsupported_file_type_raises_friendly_error(tmp_path: Path) -> None:
    txt_path = tmp_path / "sales.txt"
    txt_path.write_text("hello", encoding="utf-8")
    store = DatasetStore(base_dir=tmp_path / "data")

    try:
        store.create_from_path(txt_path)
    except UnsupportedFileTypeError as exc:
        assert str(exc) == "不支持的文件格式，请上传 CSV 或 XLSX 文件。"
    else:
        raise AssertionError("UnsupportedFileTypeError was not raised")
