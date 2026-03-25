from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_monkey.storage.replay_exporter import ReplayExporter
from smart_monkey.storage.snapshotter import SnapshotConfig, Snapshotter


class TelemetryService:
    def __init__(
        self,
        output_dir: str | Path,
        snapshot_every_n_steps: int,
        snapshot_enabled: bool,
        export_replay: bool,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.snapshotter = Snapshotter(
            self.output_dir,
            SnapshotConfig(every_n_steps=snapshot_every_n_steps, enabled=snapshot_enabled),
        )
        self.replay_exporter = ReplayExporter(self.output_dir) if export_replay else None
        self.recent_steps: list[dict[str, Any]] = []
        self.runtime_metrics: dict[str, Any] = {}

    def maybe_capture_periodic_snapshot(self, step: int, driver: Any, recorder: Any) -> str | None:
        screenshot_path = self.snapshotter.maybe_capture(step=step, driver=driver, label="periodic")
        if screenshot_path:
            recorder.record_step(
                {
                    "step": step,
                    "snapshot_path": screenshot_path,
                    "snapshot_type": "periodic",
                }
            )
        return screenshot_path

    def append_replay(self, step: int, action: Any, state_id: str) -> None:
        if self.replay_exporter is not None:
            self.replay_exporter.append_action(step=step, action=action, state_id=state_id)

    def append_recent_step(self, payload: dict[str, Any], keep_last: int = 30) -> None:
        self.recent_steps.append(payload)
        self.recent_steps = self.recent_steps[-keep_last:]

    def export_issue_replay(self, issue_dirs: list[Path]) -> None:
        if self.replay_exporter is None:
            return
        for issue_dir in issue_dirs:
            self.replay_exporter.export_issue_replay(issue_dir, self.recent_steps)

    def set_runtime_metric(self, key: str, value: Any) -> None:
        self.runtime_metrics[key] = value
