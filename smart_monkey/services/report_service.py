from __future__ import annotations

from pathlib import Path

from smart_monkey.report.coverage_benchmark import CoverageBenchmarkGenerator
from smart_monkey.report.html_report import HtmlReportGenerator
from smart_monkey.report.markdown_report import MarkdownReportGenerator
from smart_monkey.report.recovery_metrics import RecoveryMetricsGenerator
from smart_monkey.storage.recorder_indexer import RecorderIndexer


class ReportService:
    def __init__(self, output_dir: str | Path, baseline_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.recorder_indexer = RecorderIndexer(self.output_dir)
        self.html_report = HtmlReportGenerator(self.output_dir)
        self.markdown_report = MarkdownReportGenerator(self.output_dir)
        self.recovery_metrics = RecoveryMetricsGenerator(self.output_dir)
        self.coverage_benchmark = CoverageBenchmarkGenerator(self.output_dir, baseline_dir=baseline_dir)

    def generate_all(self) -> dict[str, str]:
        self.recorder_indexer.build()
        recovery_metrics_path = self.recovery_metrics.generate()
        coverage_benchmark_path = self.coverage_benchmark.generate()
        html_path = self.html_report.generate()
        md_path = self.markdown_report.generate()
        return {
            "recovery_metrics": str(recovery_metrics_path),
            "coverage_benchmark": str(coverage_benchmark_path),
            "html": str(html_path),
            "markdown": str(md_path),
        }
