from app.commands.dispatcher import dispatch_command
from app.commands.parser import parse_command
from app.commands.registry import COMMAND_REGISTRY


def test_parse_command_returns_name_args_and_raw_message() -> None:
    command = parse_command("/sql SELECT * FROM main_table")

    assert command is not None
    assert command.name == "sql"
    assert command.args == "SELECT * FROM main_table"
    assert command.raw_message == "/sql SELECT * FROM main_table"


def test_parse_command_ignores_plain_message() -> None:
    assert parse_command("普通问题") is None


def test_registry_contains_initial_commands() -> None:
    assert set(COMMAND_REGISTRY) == {"data", "sql", "chart", "report", "clean"}


def test_dispatch_command_sets_tool_route() -> None:
    dispatch = dispatch_command("/chart compare product sales")

    assert dispatch.command is not None
    assert dispatch.command.name == "chart"
    assert dispatch.route == "chart"
    assert dispatch.resolved_message == "compare product sales"


def test_dispatch_unknown_command_returns_readable_error() -> None:
    dispatch = dispatch_command("/unknown")

    assert dispatch.route == "error"
    assert dispatch.error_message
    assert "/data" in dispatch.error_message
