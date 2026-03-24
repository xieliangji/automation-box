from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_monkey.report.html_report import HtmlReportGenerator
from smart_monkey.report.html_report_v3 import HtmlReportGeneratorV3
from smart_monkey.report.markdown_report import MarkdownReportGenerator
from smart_monkey.report.markdown_report_v2 import MarkdownReportGeneratorV2
from smart_monkey.report.recovery_metrics import RecoveryMetricsGenerator
from smart_monkey.storage.recorder_indexer import RecorderIndexer


class ReportService:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.recorder_indexer = RecorderIndexer(self.output_dir)
        self.html_report = HtmlReportGenerator(self.output_dir)
        self.html_report_v3 = HtmlReportGeneratorV3(self.output_dir)
        self.markdown_report = MarkdownReportGenerator(self.output_dir)
        self.markdown_report_v2 = MarkdownReportGeneratorV2(self.output_dir)
        self.recovery_metrics = RecoveryMetricsGenerator(self.output_dir)

    def generate_all(self) -> dict[str, str]:
        self.recorder_indexer.build()
        recovery_metrics_path = self.recovery_metrics.generate()
        html_path = self.html_report.generate()
        html_v3_path = self.html_report_v3.generate()
        md_path = self.markdown_report.generate()
        md_v2_path = self.markdown_report_v2.generate()
        return {
            "recovery_metrics": str(recovery_metrics_path),
            "html": str(html_path),
            "html_v3": str(html_v3_path),
            "markdown": str(md_path),
            "markdown_v2": str(md_v2_path),
        }
