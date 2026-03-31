from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from smart_monkey.models import DeviceState


@dataclass(slots=True)
class RecoveryValidationResult:
    validated_at_ms: int
    expected_anchor_state: str | None
    candidate_state_ids: list[str]
    actual_state_id: str
    actual_package_name: str
    exact_anchor_hit: bool
    candidate_hit: bool
    in_target_app: bool
    reason: str


class RecoveryValidator:
    def __init__(self, output_dir: str | Path, target_app_id: str) -> None:
        self.output_dir = Path(output_dir)
        self.target_app_id = target_app_id
        self.recovery_dir = self.output_dir / "recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        self.validation_file = self.recovery_dir / "recovery_validation.jsonl"

    def validate(
        self,
        actual_state: DeviceState,
        expected_anchor_state: str | None,
        candidate_state_ids: list[str],
        reason: str,
    ) -> RecoveryValidationResult:
        exact_anchor_hit = bool(expected_anchor_state and actual_state.state_id == expected_anchor_state)
        candidate_hit = actual_state.state_id in set(candidate_state_ids)
        in_target_app = actual_state.package_name == self.target_app_id
        result = RecoveryValidationResult(
            validated_at_ms=int(time.time() * 1000),
            expected_anchor_state=expected_anchor_state,
            candidate_state_ids=candidate_state_ids,
            actual_state_id=actual_state.state_id,
            actual_package_name=actual_state.package_name,
            exact_anchor_hit=exact_anchor_hit,
            candidate_hit=candidate_hit,
            in_target_app=in_target_app,
            reason=reason,
        )
        with self.validation_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True) + "\n")
        return result

    def summary(self) -> dict[str, Any]:
        rows = self._read_jsonl(self.validation_file)
        exact_hits = sum(1 for row in rows if row.get("exact_anchor_hit"))
        candidate_hits = sum(1 for row in rows if row.get("candidate_hit"))
        in_target_app = sum(1 for row in rows if row.get("in_target_app"))
        return {
            "count": len(rows),
            "exact_anchor_hits": exact_hits,
            "candidate_hits": candidate_hits,
            "in_target_app_hits": in_target_app,
            "latest": rows[-10:],
        }

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
