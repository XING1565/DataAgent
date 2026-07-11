import pandas as pd

from app.services.pandasai_service import PandasAIService, TEXT_TABLE_SUMMARY


def test_pandasai_service_answers_top_product_without_generic_table_summary() -> None:
    service = PandasAIService()
    dataframe = pd.DataFrame(
        {
            "产品": ["A", "B", "C", "A"],
            "销售额": [300, 200, 100, 50],
        }
    )

    result = service.analyze(dataframe, "销售额最高的三个产品是什么", [])

    assert result.type == "dataframe"
    assert result.summary != TEXT_TABLE_SUMMARY
    assert "销售额最高的三个产品是A、B、C" in result.summary
    assert "A：350" in result.summary


def test_pandasai_service_answers_region_decline_follow_up_directly() -> None:
    service = PandasAIService()
    dataframe = pd.DataFrame(
        {
            "月份": ["2025-01", "2025-02", "2025-01", "2025-02"],
            "地区": ["华东", "华东", "华北", "华北"],
            "销售额": [1000, 700, 800, 760],
        }
    )

    result = service.analyze(dataframe, "在上一轮销售趋势分析中，按地区比较销售额下降幅度，哪个地区下降最多", [])

    assert result.type == "dataframe"
    assert "下降最多的地区是华东" in result.summary
    assert result.value[0]["地区"] == "华东"
    assert result.value[0]["变化额"] == -300
