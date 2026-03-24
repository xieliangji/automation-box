from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from smart_monkey.models import DeviceState


@dataclass(slots=True)
class Checkpoint:
    checkpoint_id: str
    state_id: str
    name: str
    priority: int
    created_at_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.file_path = self.output_dir / "checkpoints.json"
        self.checkpoints: dict[str, Checkpoint] = {}

    def consider(self, state: DeviceState, visit_count: int) -> Checkpoint | None:
        if not self._is_candidate(state, visit_count):
            return None
        checkpoint_id = state.state_id[:12]
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            state_id=state.state_id,
            name=self._checkpoint_name(state),
            priority=self._priority(state),
            created_at_ms=int(time.time() * 1000),
            metadata={
                "package_name": state.package_name,
                "activity_name": state.activity_name,
                "app_flags": sorted(state.app_flags),
                "popup_flags": sorted(state.popup_flags),
            },
        )
        self.checkpoints[checkpoint_id] = checkpoint
        self._flush()
        return checkpoint

    def best_checkpoint(self, exclude_state_id: str | None = None, include_login: bool = True) -> Checkpoint | None:
        candidates = [cp for cp in self.checkpoints.values() if cp.state_id != exclude_state_id]
        if not include_login:
            filtered: list[Checkpoint] = []
            for checkpoint in candidates:
                app_flags = {str(flag).lower() for flag in checkpoint.metadata.get("app_flags", [])}
                if checkpoint.name == "login_checkpoint" or "login_page" in app_flags:
                    continue
                filtered.append(checkpoint)
            candidates = filtered
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item.priority, item.created_at_ms))
        return candidates[0]

    def _is_candidate(self, state: DeviceState, visit_count: int) -> bool:
        if state.system_flags or state.popup_flags:
            return False
        if visit_count > 3:
            return False
        if "loading" in state.app_flags:
            return False
        return bool(state.app_flags & {"login_page", "list_page", "form_page"}) or self._looks_like_home(state)

    def _looks_like_home(self, state: DeviceState) -> bool:
        tags = set().union(*(element.semantic_tokens() for element in state.elements)) if state.elements else set()
        return bool(tags & {"home", "首页", "tab", "我的", "发现"})

    def _priority(self, state: DeviceState) -> int:
        if self._looks_like_home(state):
            return 100
        if "list_page" in state.app_flags:
            return 80
        if "form_page" in state.app_flags:
            return 60
        if "login_page" in state.app_flags:
            return 40
        return 20

    def _checkpoint_name(self, state: DeviceState) -> str:
        if self._looks_like_home(state):
            return "home_checkpoint"
        if "list_page" in state.app_flags:
            return "list_checkpoint"
        if "form_page" in state.app_flags:
            return "form_checkpoint"
        if "login_page" in state.app_flags:
            return "login_checkpoint"
        return "generic_checkpoint"

    def _flush(self) -> None:
        payload = [asdict(cp) for cp in sorted(self.checkpoints.values(), key=lambda item: (-item.priority, item.created_at_ms))]
        self.file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
