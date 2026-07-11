from __future__ import annotations

from app.tools.data_tools import DataAgentTools

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - import guard for optional server entrypoint
    raise RuntimeError("FastMCP is not installed. Run `pip install -r requirements.txt`.") from exc


mcp = FastMCP("DataAgent Tools")
tools = DataAgentTools()


@mcp.tool()
def analyze_table(dataset_id: str, question: str, session_id: str = "sess_demo") -> dict:
    """Analyze a dataset table with a natural-language question."""
    return tools.analyze_table(dataset_id=dataset_id, question=question, session_id=session_id).model_dump()


@mcp.tool()
def build_chart(dataset_id: str, question: str, chart_type: str = "trend") -> dict:
    """Build a chart artifact for a dataset, falling back to table output when needed."""
    return tools.build_chart(dataset_id=dataset_id, question=question, chart_type=chart_type).model_dump()


@mcp.tool()
def export_report(
    session_id: str,
    dataset_id: str | None = None,
    analysis_summary: str | None = None,
    chart_urls: list[str] | None = None,
) -> dict:
    """Export the latest analysis context as a Markdown report."""
    return tools.export_report(
        session_id=session_id,
        dataset_id=dataset_id,
        analysis_summary=analysis_summary,
        chart_urls=chart_urls,
    ).model_dump()


if __name__ == "__main__":
    mcp.run()
