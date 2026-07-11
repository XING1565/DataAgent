from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Any

from app.schemas.agent import AgentEvent, AgentStatus
from app.schemas.chat import AgentTraceStep


class AgentEventStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data"
        self.events_dir = self.base_dir / "agent_events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def append_event(
        self,
        *,
        type: str,
        title: str,
        summary: str,
        status: str = "success",
        session_id: str = "global",
        dataset_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_steps: list[AgentTraceStep] | None = None,
    ) -> AgentEvent:
        event = AgentEvent(
            event_id=f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{token_hex(3)}",
            session_id=session_id or "global",
            dataset_id=dataset_id,
            type=type,
            title=title,
            summary=summary,
            status=status,
            created_at=datetime.now().isoformat(timespec="seconds"),
            metadata=metadata or {},
            trace_steps=trace_steps or [],
        )
        events = self.get_events(session_id=event.session_id)
        events.append(event)
        self._event_path(event.session_id).write_text(
            json.dumps([item.model_dump() for item in events], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return event

    def get_events(self, session_id: str | None = None, limit: int = 50) -> list[AgentEvent]:
        if session_id:
            events = self._read_event_file(self._event_path(session_id))
        else:
            events = []
            for path in sorted(self.events_dir.glob("*.json")):
                events.extend(self._read_event_file(path))
        events.sort(key=lambda event: event.created_at, reverse=True)
        return events[:limit]

    def get_latest_event(self, session_id: str | None = None) -> AgentEvent | None:
        events = self.get_events(session_id=session_id, limit=1)
        return events[0] if events else None

    def get_latest_trace(self, session_id: str) -> list[AgentTraceStep]:
        for event in self.get_events(session_id=session_id):
            if event.trace_steps:
                return event.trace_steps
        return []

    def get_status(self, session_id: str | None = None) -> AgentStatus:
        events = self.get_events(session_id=session_id, limit=100)
        last_event = events[0] if events else None
        warning_count = sum(1 for event in events if event.status == "warning")
        error_count = sum(1 for event in events if event.status == "error")
        if last_event:
            message = f"{last_event.title} · {last_event.summary}"
            status = "error" if error_count else "warning" if warning_count else "success"
        else:
            message = "Agent 正在监控销售数据，等待分析任务。"
            status = "idle"
        return AgentStatus(
            status=status,
            message=message,
            last_event=last_event,
            total_events=len(events),
            warning_count=warning_count,
            error_count=error_count,
        )

    def _read_event_file(self, path: Path) -> list[AgentEvent]:
        if not path.exists():
            return []
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(content, list):
            return []
        events: list[AgentEvent] = []
        for item in content:
            try:
                events.append(AgentEvent(**item))
            except (TypeError, ValueError):
                continue
        return events

    def _event_path(self, session_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id).strip("._")
        return self.events_dir / f"{safe_id or 'global'}.json"
