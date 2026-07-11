from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.chat import ChartArtifact


TEXT_DATASET_TREND_TOPIC = "\u9500\u552e\u8d8b\u52bf"
TEXT_FOLLOW_UP_PREFIX = "\u5728\u4e0a\u4e00\u8f6e\u9500\u552e\u8d8b\u52bf\u5206\u6790\u4e2d\uff0c\u6309\u5730\u533a\u6bd4\u8f83\u9500\u552e\u989d\u4e0b\u964d\u5e45\u5ea6\uff0c"


class SessionStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parents[3] / "data"
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        path = self._session_path(session_id)
        if not path.exists():
            return []
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if isinstance(content, list):
            return content
        return []

    def get_last_turn(self, session_id: str) -> dict[str, Any] | None:
        history = self.get_history(session_id)
        return history[-1] if history else None

    def resolve_message(self, session_id: str, message: str) -> str:
        last_turn = self.get_last_turn(session_id)
        if not last_turn or not self._looks_like_follow_up(message):
            return message

        previous_topic = str(last_turn.get("topic") or last_turn.get("resolved_message") or last_turn.get("message") or "")
        if "\u9500\u552e\u8d8b\u52bf" in previous_topic or "\u8d8b\u52bf" in previous_topic or "\u6708\u4efd" in previous_topic:
            return f"{TEXT_FOLLOW_UP_PREFIX}{message}"
        return f"\u7ed3\u5408\u4e0a\u4e00\u8f6e\u5206\u6790\u4e0a\u4e0b\u6587\uff0c{message}"

    def append_turn(
        self,
        session_id: str,
        dataset_id: str,
        message: str,
        resolved_message: str,
        result_summary: str,
        charts: list[ChartArtifact],
        warnings: list[str],
        errors: list[str],
    ) -> None:
        history = self.get_history(session_id)
        history.append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "dataset_id": dataset_id,
                "message": message,
                "resolved_message": resolved_message,
                "topic": self._infer_topic(resolved_message),
                "result_summary": result_summary,
                "charts": [chart.model_dump() for chart in charts],
                "warnings": warnings,
                "errors": errors,
            }
        )
        self._session_path(session_id).write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _session_path(self, session_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id).strip("._")
        return self.sessions_dir / f"{safe_id or 'session'}.json"

    def _looks_like_follow_up(self, message: str) -> bool:
        normalized = message.strip().lower()
        return normalized.startswith(("\u90a3", "\u90a3\u4e48", "\u7136\u540e", "\u7ee7\u7eed", "\u518d", "\u54ea\u4e2a", "which", "what about"))

    def _infer_topic(self, message: str) -> str:
        if "\u8d8b\u52bf" in message or "\u6708\u4efd" in message or "month" in message.lower():
            return TEXT_DATASET_TREND_TOPIC
        return message[:80]
