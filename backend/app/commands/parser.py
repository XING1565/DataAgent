from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: str
    raw_message: str


def parse_command(message: str) -> ParsedCommand | None:
    stripped = message.strip()
    if not stripped.startswith("/"):
        return None

    token, _, args = stripped.partition(" ")
    name = token[1:].strip().lower()
    if not name:
        return None
    return ParsedCommand(name=name, args=args.strip(), raw_message=message)
