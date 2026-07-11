from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

from app.schemas.chat import AnalysisResult
from app.schemas.dataset import ColumnSchema


TEXT_PANDASAI_ERROR = "PandasAI 分析失败，请检查 LLM 配置或稍后重试。"
TEXT_TABLE_SUMMARY = "PandasAI 返回了表格结果。"


class PandasAIServiceError(RuntimeError):
    pass


class PandasAIService:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.model = model or os.getenv("PANDASAI_LLM_MODEL", "openai/qwen-plus")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = api_base or os.getenv("OPENAI_BASE_URL")

    def analyze(
        self,
        dataframe: pd.DataFrame,
        question: str,
        schema: list[ColumnSchema],
    ) -> AnalysisResult:
        deterministic_result = self._try_deterministic_answer(dataframe, question)
        if deterministic_result:
            return deterministic_result

        try:
            self._configure_llm()
            from pandasai import Agent

            agent = Agent(dataframe)
            response = agent.chat(self._build_prompt(question, schema))
            return self._normalize_response(response, question=question)
        except Exception as exc:
            raise PandasAIServiceError(TEXT_PANDASAI_ERROR) from exc

    def _configure_llm(self) -> None:
        import pandasai as pai

        try:
            from pandasai_litellm import LiteLLM
        except ImportError:
            from pandasai_litellm.litellm import LiteLLM

        params: dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base

        pai.config.set({"llm": LiteLLM(model=self.model, **params)})

    def _build_prompt(self, question: str, schema: list[ColumnSchema]) -> str:
        fields = ", ".join(f"{column.name}({column.dtype})" for column in schema)
        return (
            "请基于给定 DataFrame 回答用户问题。"
            "所有结论必须来自真实数据计算结果。"
            "字段识别时请区分 ID 字段和分类字段，客户ID/订单ID不能当作客户类型。"
            f"字段信息：{fields}\n"
            f"用户问题：{question}"
        )

    def _normalize_response(self, response: Any, question: str = "") -> AnalysisResult:
        value = getattr(response, "value", response)
        result_type = self._detect_type(value)
        normalized_value = self._normalize_value(value)
        summary = str(value) if result_type != "dataframe" else self._summarize_table(normalized_value, question)
        return AnalysisResult(type=result_type, value=normalized_value, summary=summary)

    def _detect_type(self, value: Any) -> str:
        if isinstance(value, pd.DataFrame):
            return "dataframe"
        if isinstance(value, (int, float)):
            return "number"
        return "text"

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, pd.DataFrame):
            cleaned = value.astype(object).where(pd.notna(value), None)
            return cleaned.to_dict(orient="records")
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return value

    def _try_deterministic_answer(self, dataframe: pd.DataFrame, question: str) -> AnalysisResult | None:
        if dataframe.empty:
            return None

        normalized = question.lower()
        if self._is_region_decline_question(normalized):
            return self._answer_region_decline(dataframe)
        if self._is_top_product_question(normalized):
            return self._answer_top_dimension(
                dataframe=dataframe,
                dimension_candidates=["产品", "商品", "品类", "product", "item", "sku"],
                dimension_label="产品",
                question=question,
            )
        if self._is_top_region_question(normalized):
            return self._answer_top_dimension(
                dataframe=dataframe,
                dimension_candidates=["地区", "区域", "省份", "城市", "region", "area", "city"],
                dimension_label="地区",
                question=question,
            )
        return None

    def _is_top_product_question(self, normalized: str) -> bool:
        return self._has_top_intent(normalized) and any(keyword in normalized for keyword in ["产品", "商品", "品类", "product"])

    def _is_top_region_question(self, normalized: str) -> bool:
        return self._has_top_intent(normalized) and any(keyword in normalized for keyword in ["地区", "区域", "城市", "region", "area", "city"])

    def _has_top_intent(self, normalized: str) -> bool:
        return any(keyword in normalized for keyword in ["最高", "最多", "top", "前", "largest", "highest"])

    def _is_region_decline_question(self, normalized: str) -> bool:
        has_region = any(keyword in normalized for keyword in ["地区", "区域", "城市", "region", "area", "city"])
        has_decline = any(keyword in normalized for keyword in ["下降", "下滑", "减少", "回落", "decline", "drop", "decrease"])
        has_compare = any(keyword in normalized for keyword in ["哪个", "哪一个", "最多", "最大", "most", "largest"])
        return has_region and has_decline and has_compare

    def _answer_top_dimension(
        self,
        *,
        dataframe: pd.DataFrame,
        dimension_candidates: list[str],
        dimension_label: str,
        question: str,
    ) -> AnalysisResult | None:
        dimension_column = self._find_column(dataframe, dimension_candidates)
        sales_column = self._find_column(dataframe, ["销售额", "销售", "金额", "收入", "sales", "amount", "revenue"])
        if not dimension_column or not sales_column:
            return None

        working = dataframe[[dimension_column, sales_column]].copy()
        working[sales_column] = pd.to_numeric(working[sales_column], errors="coerce")
        grouped = (
            working.dropna(subset=[dimension_column, sales_column])
            .groupby(dimension_column, as_index=False)[sales_column]
            .sum()
            .sort_values(sales_column, ascending=False)
        )
        if grouped.empty:
            return None

        limit = self._extract_limit(question, default=3)
        top = grouped.head(limit)
        records = top.astype(object).where(pd.notna(top), None).to_dict(orient="records")
        names = "、".join(str(row[dimension_column]) for _, row in top.iterrows())
        details = "；".join(
            f"{row[dimension_column]}：{self._format_number(row[sales_column])}" for _, row in top.iterrows()
        )
        summary = f"销售额最高的{self._format_chinese_limit(limit)}个{dimension_label}是{names}。{details}。"
        return AnalysisResult(type="dataframe", value=records, summary=summary)

    def _answer_region_decline(self, dataframe: pd.DataFrame) -> AnalysisResult | None:
        date_column = self._find_column(dataframe, ["月份", "月", "日期", "时间", "date", "month", "time"])
        region_column = self._find_column(dataframe, ["地区", "区域", "省份", "城市", "region", "area", "city"])
        sales_column = self._find_column(dataframe, ["销售额", "销售", "金额", "收入", "sales", "amount", "revenue"])
        if not date_column or not region_column or not sales_column:
            return None

        working = dataframe[[date_column, region_column, sales_column]].copy()
        working[sales_column] = pd.to_numeric(working[sales_column], errors="coerce")
        parsed_date = pd.to_datetime(working[date_column], errors="coerce")
        if parsed_date.notna().any():
            working["period"] = parsed_date.dt.to_period("M").astype(str)
        else:
            working["period"] = working[date_column].astype(str)
        grouped = (
            working.dropna(subset=["period", region_column, sales_column])
            .groupby(["period", region_column], as_index=False)[sales_column]
            .sum()
            .sort_values(["period", region_column])
        )
        if grouped["period"].nunique() < 2:
            return None

        rows: list[dict[str, Any]] = []
        for region, region_rows in grouped.groupby(region_column):
            region_rows = region_rows.sort_values("period").reset_index(drop=True)
            for index in range(1, len(region_rows)):
                previous = float(region_rows.loc[index - 1, sales_column])
                current = float(region_rows.loc[index, sales_column])
                change = current - previous
                rows.append(
                    {
                        "地区": region,
                        "起始期间": region_rows.loc[index - 1, "period"],
                        "结束期间": region_rows.loc[index, "period"],
                        "起始销售额": previous,
                        "结束销售额": current,
                        "变化额": change,
                        "变化率": change / previous if previous else None,
                    }
                )
        if not rows:
            return None

        rows.sort(key=lambda row: row["变化额"])
        top_decline = rows[0]
        direction = "下降" if top_decline["变化额"] < 0 else "增长最少"
        ratio = top_decline["变化率"]
        ratio_text = self._format_percent(ratio) if ratio is not None else "-"
        summary = (
            f"{top_decline['起始期间']} 到 {top_decline['结束期间']}，"
            f"{direction}最多的地区是{top_decline['地区']}，"
            f"销售额变化 {self._format_number(top_decline['变化额'])}，变化率 {ratio_text}。"
        )
        return AnalysisResult(type="dataframe", value=rows[:10], summary=summary)

    def _summarize_table(self, value: Any, question: str = "") -> str:
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                keys = list(first.keys())
                if len(keys) >= 2:
                    limit = min(len(value), self._extract_limit(question, default=min(3, len(value))))
                    name_key = keys[0]
                    value_key = keys[1]
                    details = "；".join(
                        f"{row.get(name_key)}：{self._format_number(row.get(value_key))}" for row in value[:limit]
                    )
                    return f"已得到表格结果，前{limit}项为：{details}。"
        return TEXT_TABLE_SUMMARY

    def _extract_limit(self, question: str, default: int = 3) -> int:
        match = re.search(r"(?:top\s*|前)?(\d+)", question.lower())
        if match:
            return max(1, min(20, int(match.group(1))))
        chinese_numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        for text, number in chinese_numbers.items():
            if text in question:
                return number
        return default

    def _format_chinese_limit(self, limit: int) -> str:
        mapping = {1: "一", 2: "两", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
        return mapping.get(limit, str(limit))

    def _find_column(self, dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
        lowered = {str(column).lower(): str(column) for column in dataframe.columns}
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for lowered_name, original_name in lowered.items():
                if candidate_lower in lowered_name:
                    return original_name
        return None

    def _format_number(self, value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if pd.isna(number):
            return "-"
        return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"

    def _format_percent(self, value: float) -> str:
        if pd.isna(value):
            return "-"
        return f"{value * 100:.1f}%"
