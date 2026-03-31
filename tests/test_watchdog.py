from __future__ import annotations

from pathlib import Path

from smart_monkey.monitor.watchdog import Watchdog
from smart_monkey.storage.issue_recorder import IssueRecorder


def _make_watchdog(tmp_path: Path) -> Watchdog:
    recorder = IssueRecorder(tmp_path)
    return Watchdog(app_package="com.ugreen.iot", issue_recorder=recorder)


def test_watchdog_crash_requires_fatal_and_package_context(tmp_path: Path) -> None:
    watchdog = _make_watchdog(tmp_path)
    excerpt = """
03-24 12:06:14.111  7808  7808 D AndroidRuntime: Shutting down VM
03-24 12:06:14.111  7808  7808 I ActivityManager: Displayed com.ugreen.iot/.ui.MainActivity
"""

    assert watchdog._looks_like_crash(excerpt) is False


def test_watchdog_crash_detects_fatal_for_target_package(tmp_path: Path) -> None:
    watchdog = _make_watchdog(tmp_path)
    excerpt = """
03-24 12:06:14.111  7808  7808 E AndroidRuntime: FATAL EXCEPTION: main
03-24 12:06:14.111  7808  7808 E AndroidRuntime: Process: com.ugreen.iot, PID: 7808
03-24 12:06:14.111  7808  7808 E AndroidRuntime: java.lang.RuntimeException: Boom
"""

    assert watchdog._looks_like_crash(excerpt) is True


def test_watchdog_anr_requires_target_package_context(tmp_path: Path) -> None:
    watchdog = _make_watchdog(tmp_path)
    excerpt = """
03-24 12:06:14.111  7808  7808 E ActivityManager: ANR in com.other.app
03-24 12:06:14.111  7808  7808 E ActivityManager: Input dispatching timed out
"""

    assert watchdog._looks_like_anr(excerpt) is False


def test_watchdog_ios_crash_detection_uses_ios_markers(tmp_path: Path) -> None:
    recorder = IssueRecorder(tmp_path)
    watchdog = Watchdog(app_package="com.demo.ios", issue_recorder=recorder, platform="ios")
    excerpt = """
    03-24 12:06:14.111 SpringBoard[123] termination reason: Namespace SIGNAL, Code 0xb
    03-24 12:06:14.111 com.demo.ios[456] uncaught exception: boom
    """

    assert watchdog._looks_like_crash(excerpt) is True
