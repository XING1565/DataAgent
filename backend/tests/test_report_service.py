from pathlib import Path

from app.services.dataset_store import DatasetStore
from app.services.report_service import ReportService, is_report_request
from app.services.session_store import SessionStore


def _create_sales_dataset(tmp_path: Path, content: str):
    base_dir = tmp_path / "data"
    dataset_store = DatasetStore(base_dir=base_dir)
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(content, encoding="utf-8")
    return base_dir, dataset_store, dataset_store.create_from_path(csv_path)


FULL_SALES_CSV = (
    "日期,产品,地区,销售额,利润,数量,渠道,客户类型\n"
    "2026-01,手机,华东,15000,3000,30,线上,企业\n"
    "2026-01,电脑,华北,20000,4200,20,线下,个人\n"
    "2026-02,手机,华东,17200,3600,34,线上,企业\n"
    "2026-02,电脑,华北,18800,3900,18,线下,个人\n"
    "2026-03,手机,华东,21500,4800,43,线上,企业\n"
    "2026-03,电脑,华北,22400,5100,22,线下,企业\n"
)


def test_report_service_generates_business_report_from_raw_data(tmp_path: Path) -> None:
    base_dir, dataset_store, dataset = _create_sales_dataset(tmp_path, FULL_SALES_CSV)
    report_service = ReportService(dataset_store=dataset_store, base_dir=base_dir)

    markdown = report_service.generate_markdown("sess_demo", dataset_id=dataset.dataset_id)

    assert markdown.startswith("# 数据分析报告")
    assert "Session ID" not in markdown
    assert "历史分析结论" not in markdown
    assert "销售趋势分析" in markdown
    assert "产品表现分析" in markdown
    assert "地区表现分析" in markdown
    assert "渠道与客户结构" in markdown
    assert "异常与风险提示" in markdown
    assert "总销售额：114,900" in markdown
    assert "总利润：24,600" in markdown
    assert "总数量：167" in markdown
    assert "整体利润率：21.41%" in markdown
    assert "产品销售额最高的是 电脑" in markdown
    assert "地区销售额最高的是 华北" in markdown
    assert "销售额整体上升" in markdown
    assert "114900.0" not in markdown


def test_report_service_handles_missing_profit_and_date_fields(tmp_path: Path) -> None:
    base_dir, dataset_store, dataset = _create_sales_dataset(
        tmp_path,
        "产品,地区,销售额,数量\n"
        "手机,华东,15000,30\n"
        "电脑,华北,20000,20\n",
    )
    report_service = ReportService(dataset_store=dataset_store, base_dir=base_dir)

    markdown = report_service.generate_markdown("sess_demo", dataset_id=dataset.dataset_id)

    assert "未识别到利润字段" in markdown
    assert "未识别到日期或销售额字段" in markdown
    assert "产品销售额最高的是 电脑" in markdown
    assert "地区销售额最高的是 华北" in markdown


def test_report_service_can_fallback_to_latest_dataset_in_session(tmp_path: Path) -> None:
    base_dir, dataset_store, dataset = _create_sales_dataset(tmp_path, FULL_SALES_CSV)
    session_store = SessionStore(base_dir=base_dir)
    report_service = ReportService(session_store=session_store, dataset_store=dataset_store)
    session_store.append_turn(
        session_id="sess_demo",
        dataset_id=dataset.dataset_id,
        message="查看月度销售趋势",
        resolved_message="查看月度销售趋势",
        result_summary="已生成按月份销售趋势图。",
        charts=[],
        warnings=[],
        errors=[],
    )

    markdown = report_service.generate_markdown("sess_demo")

    assert "总销售额：114,900" in markdown
    assert "查看月度销售趋势" not in markdown
    assert "历史分析结论" not in markdown


def test_report_service_does_not_treat_customer_id_as_customer_type(tmp_path: Path) -> None:
    base_dir, dataset_store, dataset = _create_sales_dataset(
        tmp_path,
        "日期,订单ID,客户ID,支付方式,产品,地区,单价,数量,销售额\n"
        "2025-01,ORD001,CUST6419,微信支付,手机,华东,100,2,200\n"
        "2025-01,ORD002,CUST5106,支付宝,电脑,华北,200,1,200\n"
        "2025-02,ORD003,CUST6419,微信支付,手机,华东,150,2,300\n"
        "2025-02,ORD004,CUST5668,银行卡,配件,华南,80,3,240\n"
        "2025-03,ORD005,CUST7777,花呗,手机,华东,120,2,240\n"
        "2025-03,ORD006,CUST8888,信用卡,电脑,华北,220,1,220\n",
    )
    report_service = ReportService(dataset_store=dataset_store, base_dir=base_dir)

    markdown = report_service.generate_markdown("sess_demo", dataset_id=dataset.dataset_id)

    assert "客户类型结构 Top 3：CUST" not in markdown
    assert "客户类型销售额最高的是 CUST" not in markdown
    assert "支付方式结构 Top 3" in markdown
    assert "客户价值分析" in markdown
    assert "客户ID" in markdown
    assert "订单ID" in markdown
    assert "单价" in markdown
    assert "当前时间跨度仅覆盖 3 个月或更少" in markdown


def test_report_request_detection_accepts_chinese_report_phrases() -> None:
    assert is_report_request("生成分析报告")
    assert is_report_request("报告")
    assert is_report_request("generate report")


def test_report_service_generates_empty_report(tmp_path: Path) -> None:
    report_service = ReportService(base_dir=tmp_path / "data")

    markdown = report_service.generate_markdown("missing_session")

    assert "# 数据分析报告" in markdown
    assert "暂无可用数据集" in markdown
