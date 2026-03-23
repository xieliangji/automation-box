from __future__ import annotations

from pathlib import Path

from smart_monkey.action.extractor_v2 import ActionExtractorV2
from smart_monkey.app_watchdog import WatchdogSmartMonkeyApp
from smart_monkey.config import ProjectConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.storage.snapshotter import SnapshotConfig, Snapshotter


class SmartMonkeyAppV2(WatchdogSmartMonkeyApp):
    def __init__(self, driver: DeviceDriver, config: ProjectConfig, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.extractor = ActionExtractorV2(config)
        self.snapshotter = Snapshotter(
            self.output_dir,
            SnapshotConfig(every_n_steps=10, enabled=True),
        )

    def persist_step(self, step, current_state, action, transition, next_state) -> None:
        screenshot_path = self.snapshotter.maybe_capture(step=step, driver=self.driver, label="periodic")
        super().persist_step(step, current_state, action, transition, next_state)
        if screenshot_path:
            self.recorder.record_step(
                {
                    "step": step,
                    "snapshot_path": screenshot_path,
                    "snapshot_type": "periodic",
                }
            )
