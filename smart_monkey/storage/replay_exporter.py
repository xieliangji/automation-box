from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class ReplayExporter:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.replay_dir = self.output_dir / "replay"
        self.replay_dir.mkdir(parents=True, exist_ok=True)
        self.replay_file = self.replay_dir / "actions_replay.jsonl"

    def append_action(self, step: int, action: Any, state_id: str) -> None:
        payload = {
            "step": step,
            "state_id": state_id,
            "action": self._normalize(action),
        }
        with self.replay_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def export_issue_replay(self, issue_dir: str | Path, recent_steps: list[dict[str, Any]]) -> None:
        target = Path(issue_dir) / "recent_replay.json"
        target.write_text(
            json.dumps([self._normalize(item) for item in recent_steps], ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _normalize(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._normalize(asdict(value))
        if isinstance(value, dict):
            return {key: self._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize(item) for item in value]
        if isinstance(value, set):
            return sorted(self._normalize(item) for item in value)
        return value
