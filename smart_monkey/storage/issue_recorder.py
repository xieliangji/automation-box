from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class IssueRecorder:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.issues_dir = self.output_dir / "issues"
        self.issues_dir.mkdir(parents=True, exist_ok=True)

    def record_issue(
        self,
        issue_type: str,
        title: str,
        payload: dict[str, Any],
        driver: Any | None = None,
    ) -> Path:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        issue_dir = self.issues_dir / f"{issue_type}_{timestamp}"
        issue_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "issue_type": issue_type,
            "title": title,
            "created_at": int(time.time() * 1000),
            "payload": self._normalize(payload),
        }
        (issue_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        if driver is not None:
            self._capture_screenshot(driver, issue_dir / "screenshot.png")
            self._capture_logcat(driver, issue_dir / "logcat.txt")

        return issue_dir

    def _capture_screenshot(self, driver: Any, target: Path) -> None:
        if hasattr(driver, "take_screenshot"):
            try:
                driver.take_screenshot(target)
            except Exception as exc:  # noqa: BLE001
                target.write_text(f"failed to capture screenshot: {exc}\n", encoding="utf-8")

    def _capture_logcat(self, driver: Any, target: Path) -> None:
        if hasattr(driver, "read_logcat_tail"):
            try:
                target.write_text(driver.read_logcat_tail(300), encoding="utf-8")
                return
            except Exception as exc:  # noqa: BLE001
                target.write_text(f"failed to read logcat: {exc}\n", encoding="utf-8")

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
