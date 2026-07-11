from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.dataset import ColumnSchema
from app.services.dataset_store import DatasetNotFoundError, DatasetParseError, DatasetStore
from app.services.session_store import SessionStore


TEXT_REPORT_TITLE = "数据分析报告"
TEXT_EMPTY_REPORT = "暂无可用数据集。请先上传 CSV 或 XLSX 文件后再生成报告。"
TEXT_REPORT_SUMMARY = "已生成完整 Markdown 报告。"
REPORT_KEYWORDS = ("生成完整报告", "生成分析报告", "分析报告", "生成报告", "报告")
REPORT_ENGLISH_KEYWORDS = ("generate report", "full report", "analysis report")


@dataclass(frozen=True)
class BusinessColumns:
    date: str | None
    sales: str | None
    profit: str | None
    quantity: str | None
    unit_price: str | None
    product: str | None
    region: str | None
    channel: str | None
    payment_method: str | None
    customer_type: str | None
    customer_id: str | None
    order_id: str | None


def is_report_request(message: str) -> bool:
    normalized = message.strip().lower()
    return any(keyword in message for keyword in REPORT_KEYWORDS) or any(
        keyword in normalized for keyword in REPORT_ENGLISH_KEYWORDS
    )


class ReportService:
    def __init__(
        self,
        session_store: SessionStore | None = None,
        dataset_store: DatasetStore | None = None,
        base_dir: Path | None = None,
    ) -> None:
        self.session_store = session_store or SessionStore(base_dir=base_dir)
        self.dataset_store = dataset_store or DatasetStore(base_dir=base_dir)

    def generate_markdown(self, session_id: str, dataset_id: str | None = None) -> str:
        resolved_dataset_id = dataset_id or self._latest_dataset_id(session_id)
        if not resolved_dataset_id:
            return self._empty_report()

        try:
            dataframe = self.dataset_store.load_dataframe(resolved_dataset_id)
            schema = self.dataset_store.load_schema(resolved_dataset_id)
        except (DatasetNotFoundError, DatasetParseError):
            return self._empty_report()

        columns = self._detect_business_columns(dataframe)
        return "\n".join(
            [
                f"# {TEXT_REPORT_TITLE}",
                "",
                "## 数据概览",
                "",
                *self._format_overview(resolved_dataset_id, dataframe, columns),
                "",
                "## 核心指标",
                "",
                *self._format_core_metrics(dataframe, columns),
                "",
                "## 销售趋势分析",
                "",
                *self._format_sales_trend(dataframe, columns),
                "",
                "## 产品表现分析",
                "",
                *self._format_dimension_performance(dataframe, columns.product, columns, "产品"),
                "",
                "## 地区表现分析",
                "",
                *self._format_dimension_performance(dataframe, columns.region, columns, "地区"),
                "",
                "## 渠道与客户结构",
                "",
                *self._format_channel_customer(dataframe, columns),
                "",
                "## 异常与风险提示",
                "",
                *self._format_anomalies(dataframe, columns),
                "",
                "## 业务建议",
                "",
                *self._format_recommendations(dataframe, schema, columns),
                "",
                "## 字段与数据质量附录",
                "",
                *self._format_quality_appendix(dataframe, schema),
                "",
            ]
        )

    def _empty_report(self) -> str:
        return "\n".join([f"# {TEXT_REPORT_TITLE}", "", "## 数据概览", "", TEXT_EMPTY_REPORT, ""])

    def _format_overview(self, dataset_id: str, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        detected = [
            label
            for label, column in [
                ("日期", columns.date),
                ("销售额", columns.sales),
                ("利润", columns.profit),
                ("数量", columns.quantity),
                ("单价", columns.unit_price),
                ("产品", columns.product),
                ("地区", columns.region),
                ("渠道", columns.channel),
                ("支付方式", columns.payment_method),
                ("客户类型", columns.customer_type),
                ("客户ID", columns.customer_id),
                ("订单ID", columns.order_id),
            ]
            if column
        ]
        detected_text = "、".join(detected) if detected else "暂未识别到明确业务字段"
        return [
            f"- 数据集 ID：`{dataset_id}`",
            f"- 原始记录数：{self._format_number(len(dataframe))}",
            f"- 字段数：{self._format_number(len(dataframe.columns))}",
            f"- 已识别业务字段：{detected_text}",
        ]

    def _format_core_metrics(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        lines = [f"- 总记录数：{self._format_number(len(dataframe))}"]
        sales = self._numeric_series(dataframe, columns.sales)
        profit = self._numeric_series(dataframe, columns.profit)
        quantity = self._numeric_series(dataframe, columns.quantity)

        if sales is not None:
            total_sales = sales.sum()
            lines.append(f"- 总销售额：{self._format_number(total_sales)}")
            lines.append(f"- 平均单条销售额：{self._format_number(sales.mean(), decimals=2)}")
            lines.append(f"- 最高单条销售额：{self._format_number(sales.max())}")
            lines.append(f"- 最低单条销售额：{self._format_number(sales.min())}")
        else:
            lines.append("- 未识别到销售额字段，无法计算销售总额。")

        if profit is not None:
            total_profit = profit.sum()
            lines.append(f"- 总利润：{self._format_number(total_profit)}")
            if sales is not None and sales.sum() != 0:
                lines.append(f"- 整体利润率：{self._format_percent(total_profit / sales.sum())}")
        else:
            lines.append("- 未识别到利润字段，无法计算利润率。")

        if quantity is not None:
            lines.append(f"- 总数量：{self._format_number(quantity.sum())}")
            if sales is not None and quantity.sum() != 0:
                lines.append(f"- 平均单件销售额：{self._format_number(sales.sum() / quantity.sum(), decimals=2)}")
        if columns.unit_price:
            unit_price = self._numeric_series(dataframe, columns.unit_price)
            if unit_price is not None:
                lines.append(f"- 平均单价：{self._format_number(unit_price.mean(), decimals=2)}")
        if columns.order_id and columns.order_id in dataframe.columns:
            lines.append(f"- 订单数：{self._format_number(dataframe[columns.order_id].nunique())}")
        return lines

    def _format_sales_trend(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        if not columns.date or not columns.sales:
            return ["- 未识别到日期或销售额字段，无法计算月度销售趋势。"]

        trend = self._monthly_sales(dataframe, columns)
        if trend.empty:
            return ["- 日期或销售额字段有效值不足，无法形成趋势分析。"]

        first_value = float(trend.iloc[0]["sales"])
        last_value = float(trend.iloc[-1]["sales"])
        change = last_value - first_value
        change_ratio = change / first_value if first_value else 0
        best = trend.loc[trend["sales"].idxmax()]
        worst = trend.loc[trend["sales"].idxmin()]
        direction = "上升" if change > 0 else "下降" if change < 0 else "持平"

        lines = [
            f"- 从 {trend.iloc[0]['month']} 到 {trend.iloc[-1]['month']}，销售额整体{direction}，变化额为 {self._format_number(change)}，变化率为 {self._format_percent(change_ratio)}。",
            f"- 销售额最高月份是 {best['month']}，销售额 {self._format_number(best['sales'])}。",
            f"- 销售额最低月份是 {worst['month']}，销售额 {self._format_number(worst['sales'])}。",
        ]

        if len(trend) >= 2:
            trend = trend.copy()
            trend["mom"] = trend["sales"].pct_change()
            valid_mom = trend.dropna(subset=["mom"])
            strongest = valid_mom.loc[valid_mom["mom"].idxmax()]
            weakest = valid_mom.loc[valid_mom["mom"].idxmin()]
            lines.append(f"- 环比增长最明显的月份是 {strongest['month']}，环比 {self._format_percent(strongest['mom'])}。")
            lines.append(f"- 环比压力最大的月份是 {weakest['month']}，环比 {self._format_percent(weakest['mom'])}。")
        return lines

    def _format_dimension_performance(
        self,
        dataframe: pd.DataFrame,
        dimension_column: str | None,
        columns: BusinessColumns,
        label: str,
    ) -> list[str]:
        if not dimension_column or not columns.sales:
            return [f"- 未识别到{label}或销售额字段，无法计算{label}表现。"]

        sales = self._numeric_series(dataframe, columns.sales)
        if sales is None:
            return [f"- 销售额字段有效值不足，无法计算{label}表现。"]

        working = dataframe[[dimension_column]].copy()
        working["sales"] = sales
        if columns.profit:
            working["profit"] = self._numeric_series(dataframe, columns.profit)
        grouped = working.dropna(subset=[dimension_column, "sales"]).groupby(dimension_column, as_index=False).sum(numeric_only=True)
        if grouped.empty:
            return [f"- {label}字段有效值不足，无法计算排名。"]

        grouped = grouped.sort_values("sales", ascending=False)
        total_sales = grouped["sales"].sum()
        leader = grouped.iloc[0]
        lines = [
            f"- {label}销售额最高的是 {leader[dimension_column]}，销售额 {self._format_number(leader['sales'])}，贡献占比 {self._format_percent(leader['sales'] / total_sales if total_sales else 0)}。",
            f"- {label}销售额 Top 3：{self._format_top_items(grouped, dimension_column, 'sales')}。",
        ]
        if "profit" in grouped.columns:
            profit_grouped = grouped.sort_values("profit", ascending=False)
            profit_leader = profit_grouped.iloc[0]
            lines.append(f"- {label}利润最高的是 {profit_leader[dimension_column]}，利润 {self._format_number(profit_leader['profit'])}。")
        if len(grouped) > 1:
            tail = grouped.iloc[-1]
            spread = (leader["sales"] - tail["sales"]) / total_sales if total_sales else 0
            if spread < 0.05:
                lines.append(f"- {label}销售额最高与最低占比差距小于 5%，当前差异不宜过度解读为结构性问题。")
            else:
                lines.append(f"- {label}销售额最低的是 {tail[dimension_column]}，销售额 {self._format_number(tail['sales'])}，可作为后续观察对象。")
        return lines

    def _format_channel_customer(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        lines: list[str] = []
        lines.extend(self._format_share_by_dimension(dataframe, columns.channel, columns.sales, "渠道"))
        lines.extend(self._format_share_by_dimension(dataframe, columns.payment_method, columns.sales, "支付方式"))
        lines.extend(self._format_share_by_dimension(dataframe, columns.customer_type, columns.sales, "客户类型"))
        lines.extend(self._format_customer_value(dataframe, columns))
        return lines or ["- 未识别到渠道、支付方式、客户类型或客户 ID 字段，暂不输出结构分析。"]

    def _format_customer_value(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        if not columns.customer_id or columns.customer_id not in dataframe.columns:
            return []
        sales = self._numeric_series(dataframe, columns.sales)
        if sales is None:
            return [f"- 客户价值分析：识别到客户 ID 字段 `{columns.customer_id}`，但缺少有效销售额，暂不计算客户贡献。"]

        working = dataframe[[columns.customer_id]].copy()
        working["sales"] = sales
        grouped = working.dropna(subset=[columns.customer_id, "sales"]).groupby(columns.customer_id, as_index=False).agg(
            sales=("sales", "sum"),
            orders=("sales", "size"),
        )
        if grouped.empty:
            return []
        grouped = grouped.sort_values("sales", ascending=False)
        total_sales = grouped["sales"].sum()
        top_count = max(1, int(len(grouped) * 0.1))
        top_sales = grouped.head(top_count)["sales"].sum()
        repeat_customers = grouped[grouped["orders"] > 1]
        return [
            f"- 客户价值分析：Top 10% 客户贡献销售额 {self._format_number(top_sales)}，占比 {self._format_percent(top_sales / total_sales if total_sales else 0)}。",
            f"- 复购客户数：{self._format_number(len(repeat_customers))}，最高价值客户为 {grouped.iloc[0][columns.customer_id]}（{self._format_number(grouped.iloc[0]['sales'])}）。",
        ]

    def _format_anomalies(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> list[str]:
        sales = self._numeric_series(dataframe, columns.sales)
        if sales is None or sales.dropna().empty:
            return ["- 未识别到有效销售额字段，无法检测销售异常。"]

        max_index = sales.idxmax()
        min_index = sales.idxmin()
        max_context = self._record_context(dataframe.loc[max_index], columns)
        min_context = self._record_context(dataframe.loc[min_index], columns)
        lines = [
            f"- 最高单条销售额为 {self._format_number(sales.loc[max_index])}，对应记录：{max_context}。",
            f"- 最低单条销售额为 {self._format_number(sales.loc[min_index])}，对应记录：{min_context}。",
        ]

        mean = sales.mean()
        std = sales.std()
        if pd.notna(std) and std > 0:
            threshold = mean + 2 * std
            outliers = sales[sales > threshold]
            if not outliers.empty:
                lines.append(f"- 检测到 {self._format_number(len(outliers))} 条高销售额异常记录，阈值为 {self._format_number(threshold, decimals=2)}。")
            else:
                lines.append("- 未发现明显高销售额异常记录。")
        return lines

    def _format_recommendations(self, dataframe: pd.DataFrame, schema: list[ColumnSchema], columns: BusinessColumns) -> list[str]:
        recommendations = []
        if columns.product and columns.sales:
            recommendations.append("- 围绕销售额最高的产品复盘定价、渠道和支付方式分布，提炼可复制的增长策略。")
        if columns.region and columns.sales:
            region_spread = self._dimension_share_spread(dataframe, columns.region, columns.sales)
            if region_spread is not None and region_spread < 0.05:
                recommendations.append("- 地区销售占比差距小于 5%，建议先补充活动、门店覆盖或样本周期信息，再判断是否存在区域问题。")
            else:
                recommendations.append("- 对销售额最低地区进行原因拆解时，应结合渠道覆盖、活动投入和产品组合，避免只凭单期排名下结论。")
        if columns.date and columns.sales:
            month_count = len(self._monthly_sales(dataframe, columns))
            if month_count <= 3:
                recommendations.append("- 当前时间跨度仅覆盖 3 个月或更少，建议补充更多月份数据，以区分季节性波动和趋势性变化。")
            else:
                recommendations.append("- 将月度趋势作为后续监控指标，跟踪环比波动较大的月份并关联活动或供应变化。")
        if columns.payment_method:
            recommendations.append("- 支付方式已识别，可进一步对比不同支付方式的销售额、客单价和复购表现。")
        if columns.profit and columns.sales:
            recommendations.append("- 同时关注销售额和利润率，避免只追求规模而忽略盈利质量。")
        if any(column.missing_count > 0 for column in schema):
            recommendations.append("- 存在缺失字段，建议在正式决策前确认缺失来源并完成清洗。")
        else:
            recommendations.append("- 当前数据完整性较好，可直接用于演示、汇报和进一步建模。")
        return recommendations

    def _format_quality_appendix(self, dataframe: pd.DataFrame, schema: list[ColumnSchema]) -> list[str]:
        total_cells = dataframe.shape[0] * dataframe.shape[1]
        missing_cells = int(dataframe.isna().sum().sum())
        duplicate_rows = int(dataframe.duplicated().sum())
        missing_ratio = missing_cells / total_cells if total_cells else 0
        duplicate_ratio = duplicate_rows / len(dataframe) if len(dataframe) else 0
        quality_score = max(0, round(100 - min(60, missing_ratio * 100) - min(40, duplicate_ratio * 100)))

        lines = [
            f"- 数据质量评分：{quality_score}%",
            f"- 缺失单元格：{self._format_number(missing_cells)}（{self._format_percent(missing_ratio)}）",
            f"- 重复行：{self._format_number(duplicate_rows)}（{self._format_percent(duplicate_ratio)}）",
            "",
            "| 字段 | 类型 | 非空值 | 缺失值 | 缺失率 |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
        for column in schema:
            lines.append(
                f"| {column.name} | {column.dtype} | {self._format_number(column.non_null_count)} | "
                f"{self._format_number(column.missing_count)} | {self._format_percent(column.missing_ratio)} |"
            )
        return lines

    def _detect_business_columns(self, dataframe: pd.DataFrame) -> BusinessColumns:
        return BusinessColumns(
            date=self._find_column(dataframe, ["日期", "时间", "月份", "月", "date", "time", "month"]),
            sales=self._find_column(dataframe, ["销售额", "销售", "金额", "收入", "sales", "amount", "revenue"]),
            profit=self._find_column(dataframe, ["利润", "毛利", "profit"]),
            quantity=self._find_column(dataframe, ["数量", "销量", "quantity", "qty", "sales_count"]),
            unit_price=self._find_column(dataframe, ["单价", "价格", "unit_price", "price"]),
            product=self._find_column(dataframe, ["产品", "商品", "品类", "product", "item", "sku"]),
            region=self._find_column(dataframe, ["地区", "区域", "省份", "城市", "region", "area", "city"]),
            channel=self._find_column(dataframe, ["渠道", "来源", "channel", "source"]),
            payment_method=self._find_column(dataframe, ["支付方式", "支付渠道", "付款方式", "payment", "pay_method"]),
            customer_type=self._find_column(dataframe, ["客户类型", "客户类别", "客户分群", "客群", "customer_type", "segment"]),
            customer_id=self._find_column(dataframe, ["客户id", "客户ID", "customer_id", "customer id", "cust_id"]),
            order_id=self._find_column(dataframe, ["订单id", "订单ID", "订单号", "order_id", "order id"]),
        )

    def _monthly_sales(self, dataframe: pd.DataFrame, columns: BusinessColumns) -> pd.DataFrame:
        if not columns.date or not columns.sales:
            return pd.DataFrame(columns=["month", "sales"])
        working = dataframe[[columns.date, columns.sales]].copy()
        working["sales"] = pd.to_numeric(working[columns.sales], errors="coerce")
        parsed_date = pd.to_datetime(working[columns.date], errors="coerce")
        if parsed_date.notna().any():
            working["month"] = parsed_date.dt.to_period("M").astype(str)
        else:
            working["month"] = working[columns.date].astype(str)
        return (
            working.dropna(subset=["month", "sales"])
            .groupby("month", as_index=False)["sales"]
            .sum()
            .sort_values("month")
        )

    def _format_share_by_dimension(
        self,
        dataframe: pd.DataFrame,
        dimension_column: str | None,
        sales_column: str | None,
        label: str,
    ) -> list[str]:
        if not dimension_column:
            return []
        if sales_column:
            sales = self._numeric_series(dataframe, sales_column)
            if sales is not None:
                working = dataframe[[dimension_column]].copy()
                working["sales"] = sales
                grouped = working.dropna(subset=[dimension_column, "sales"]).groupby(dimension_column, as_index=False)["sales"].sum()
                if not grouped.empty:
                    grouped = grouped.sort_values("sales", ascending=False)
                    top = grouped.iloc[0]
                    total = grouped["sales"].sum()
                    return [
                        f"- {label}销售额最高的是 {top[dimension_column]}，销售额 {self._format_number(top['sales'])}，占比 {self._format_percent(top['sales'] / total if total else 0)}。",
                        f"- {label}结构 Top 3：{self._format_top_items(grouped, dimension_column, 'sales')}。",
                    ]
        counts = dataframe[dimension_column].dropna().astype(str).value_counts().head(3)
        if counts.empty:
            return []
        return [f"- {label}记录数 Top 3：{'、'.join(f'{name}({count})' for name, count in counts.items())}。"]

    def _dimension_share_spread(self, dataframe: pd.DataFrame, dimension_column: str | None, sales_column: str | None) -> float | None:
        if not dimension_column or not sales_column:
            return None
        sales = self._numeric_series(dataframe, sales_column)
        if sales is None:
            return None
        working = dataframe[[dimension_column]].copy()
        working["sales"] = sales
        grouped = working.dropna(subset=[dimension_column, "sales"]).groupby(dimension_column, as_index=False)["sales"].sum()
        total = grouped["sales"].sum()
        if grouped.empty or not total:
            return None
        shares = grouped["sales"] / total
        return float(shares.max() - shares.min())

    def _record_context(self, row: pd.Series, columns: BusinessColumns) -> str:
        parts = []
        for label, column in [
            ("日期", columns.date),
            ("订单ID", columns.order_id),
            ("产品", columns.product),
            ("地区", columns.region),
            ("渠道", columns.channel),
            ("支付方式", columns.payment_method),
            ("客户类型", columns.customer_type),
            ("客户ID", columns.customer_id),
        ]:
            if column and column in row.index:
                parts.append(f"{label}={row[column]}")
        return "；".join(parts) if parts else "无额外维度信息"

    def _format_top_items(self, dataframe: pd.DataFrame, name_column: str, value_column: str, limit: int = 3) -> str:
        items = []
        for _, row in dataframe.head(limit).iterrows():
            items.append(f"{row[name_column]}({self._format_number(row[value_column])})")
        return "、".join(items)

    def _latest_dataset_id(self, session_id: str) -> str | None:
        history = self.session_store.get_history(session_id)
        for turn in reversed(history):
            if self._is_report_turn(turn):
                continue
            dataset_id = turn.get("dataset_id")
            if dataset_id:
                return str(dataset_id)
        return None

    def _is_report_turn(self, turn: dict[str, Any]) -> bool:
        values = [
            str(turn.get("message") or ""),
            str(turn.get("resolved_message") or ""),
            str(turn.get("result_summary") or ""),
        ]
        return any(is_report_request(value) or TEXT_REPORT_SUMMARY in value for value in values)

    def _numeric_series(self, dataframe: pd.DataFrame, column: str | None) -> pd.Series | None:
        if not column or column not in dataframe.columns:
            return None
        series = pd.to_numeric(dataframe[column], errors="coerce")
        return series if series.notna().any() else None

    def _find_column(self, dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
        lowered = {str(column).lower(): str(column) for column in dataframe.columns}
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for lowered_name, original_name in lowered.items():
                if candidate_lower == lowered_name or candidate_lower in lowered_name:
                    return original_name
        return None

    def _format_number(self, value: Any, decimals: int = 0) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if pd.isna(number):
            return "-"
        if decimals:
            return f"{number:,.{decimals}f}"
        return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"

    def _format_percent(self, value: float) -> str:
        if pd.isna(value):
            return "-"
        return f"{value * 100:.2f}%"
