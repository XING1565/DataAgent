from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    route: str
    description: str
    default_prompt: str = ""


COMMAND_REGISTRY: dict[str, CommandDefinition] = {
    "data": CommandDefinition(
        name="data",
        route="data",
        description="查看数据概况",
    ),
    "sql": CommandDefinition(
        name="sql",
        route="sql",
        description="执行 SQL 查询",
    ),
    "chart": CommandDefinition(
        name="chart",
        route="chart",
        description="优先生成图表",
        default_prompt="根据当前数据生成推荐图表",
    ),
    "report": CommandDefinition(
        name="report",
        route="report",
        description="生成 Markdown 报告",
        default_prompt="生成分析报告",
    ),
    "clean": CommandDefinition(
        name="clean",
        route="clean",
        description="数据质量与清洗建议",
    ),
}


def list_available_commands() -> str:
    return "、".join(f"/{name}" for name in COMMAND_REGISTRY)
