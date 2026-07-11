from __future__ import annotations

from dataclasses import dataclass

from app.commands.parser import ParsedCommand, parse_command
from app.commands.registry import COMMAND_REGISTRY, list_available_commands


@dataclass(frozen=True)
class CommandDispatch:
    command: ParsedCommand | None
    route: str
    resolved_message: str | None = None
    error_message: str | None = None


def dispatch_command(message: str) -> CommandDispatch:
    command = parse_command(message)
    if command is None:
        return CommandDispatch(command=None, route="analysis")

    definition = COMMAND_REGISTRY.get(command.name)
    if definition is None:
        return CommandDispatch(
            command=command,
            route="error",
            error_message=f"未知命令 /{command.name}。可用命令：{list_available_commands()}。",
        )

    resolved_message = command.args or definition.default_prompt or message
    return CommandDispatch(command=command, route=definition.route, resolved_message=resolved_message)
