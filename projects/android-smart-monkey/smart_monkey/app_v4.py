from __future__ import annotations

from pathlib import Path

from smart_monkey.app_v3 import SmartMonkeyAppV3
from smart_monkey.config_v2 import ProjectConfigV2
from smart_monkey.device.base import DeviceDriver
from smart_monkey.report.html_report import HtmlReportGenerator
from smart_monkey.storage.recorder_indexer import RecorderIndexer


class SmartMonkeyAppV4(SmartMonkeyAppV3):
    def __init__(self, driver: DeviceDriver, config: ProjectConfigV2, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.recorder_indexer = RecorderIndexer(self.output_dir)
        self.report_generator = HtmlReportGenerator(self.output_dir)

    def run(self) -> None:
        super().run()
        self.recorder_indexer.build()
        self.report_generator.generate()
