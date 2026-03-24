from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SnapshotConfig:
    every_n_steps: int = 10
    enabled: bool = True


class Snapshotter:
    def __init__(self, output_dir: str | Path, config: SnapshotConfig | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or SnapshotConfig()

    def maybe_capture(self, step: int, driver: Any, label: str = "step") -> str | None:
        if not self.config.enabled:
            return None
        if self.config.every_n_steps <= 0:
            return None
        if step % self.config.every_n_steps != 0:
            return None
        target = self.screenshots_dir / f"{label}_{step:04d}.png"
        try:
            driver.take_screenshot(target)
            return str(target)
        except Exception:  # noqa: BLE001
            return None
