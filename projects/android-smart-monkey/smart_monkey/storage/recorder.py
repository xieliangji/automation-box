from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.utg import UTG


class RunRecorder:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.states_dir = self.output_dir / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
        self.actions_file = self.output_dir / "actions.jsonl"
        self.transitions_file = self.output_dir / "transitions.jsonl"
        self.steps_file = self.output_dir / "steps.jsonl"
        self.utg_file = self.output_dir / "utg.json"

    def record_state(self, state: Any) -> None:
        path = self.states_dir / f"{getattr(state, 'state_id', 'unknown')}.json"
        path.write_text(self._dump(state), encoding="utf-8")

    def record_action(self, action: Any) -> None:
        self._append_jsonl(self.actions_file, action)

    def record_transition(self, transition: Any) -> None:
        self._append_jsonl(self.transitions_file, transition)

    def record_step(self, payload: dict[str, Any]) -> None:
        self._append_jsonl(self.steps_file, payload)

    def record_utg(self, utg: UTG) -> None:
        self.utg_file.write_text(json.dumps(utg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_jsonl(self, path: Path, payload: Any) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(self._dump(payload) + "\n")

    def _dump(self, payload: Any) -> str:
        return json.dumps(self._normalize(payload), ensure_ascii=False, sort_keys=True)

    def _normalize(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, dict):
            return {key: self._normalize(value) for key, value in payload.items()}
        if isinstance(payload, (list, tuple)):
            return [self._normalize(item) for item in payload]
        if isinstance(payload, set):
            return sorted(self._normalize(item) for item in payload)
        return payload
