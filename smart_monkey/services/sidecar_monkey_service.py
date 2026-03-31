from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass(slots=True)
class SidecarMonkeyBatchResult:
    triggered_step: int
    batch_no: int
    command: str
    seed: int
    events_requested: int
    events_injected: int
    exit_code: int
    success: bool
    stdout_tail: str
    stderr_tail: str
    recovered_to_target: bool = False
    skipped_reason: str | None = None


class SidecarMonkeyService:
    _EVENTS_RE = re.compile(r"Events injected:\s*(\d+)", re.IGNORECASE)

    def __init__(self, config: Any) -> None:
        self.config = config
        self._batches_run = 0
        self._success_count = 0
        self._failure_count = 0
        self._recovery_count = 0
        self._total_events_injected = 0
        self._last_exit_code: int | None = None

    def enabled(self, platform: str) -> bool:
        sidecar = getattr(getattr(self.config, "sidecar", None), "monkey", None)
        if sidecar is None:
            return False
        return bool(getattr(sidecar, "enabled", False)) and str(platform).lower() == "android"

    def should_trigger(self, step: int) -> bool:
        sidecar = getattr(getattr(self.config, "sidecar", None), "monkey", None)
        if sidecar is None:
            return False
        if self._batches_run >= max(0, int(getattr(sidecar, "max_batches", 0))):
            return False
        interval = max(1, int(getattr(sidecar, "step_interval", 1)))
        return (step + 1) % interval == 0

    def run_batch(self, step: int, driver: Any, target_app_id: str) -> SidecarMonkeyBatchResult | None:
        if not self.should_trigger(step):
            return None
        sidecar = self.config.sidecar.monkey
        batch_no = self._batches_run + 1
        events_requested = max(1, int(getattr(sidecar, "events_per_batch", 60)))
        seed = int(getattr(self.config.run, "seed", 12345)) + int(getattr(sidecar, "seed_offset", 1000)) + batch_no
        command = self._build_command(target_app_id=target_app_id, seed=seed, events_requested=events_requested)
        run_fn = getattr(driver, "_run", None)
        if not callable(run_fn):
            result = SidecarMonkeyBatchResult(
                triggered_step=step,
                batch_no=batch_no,
                command=command,
                seed=seed,
                events_requested=events_requested,
                events_injected=0,
                exit_code=127,
                success=False,
                stdout_tail="",
                stderr_tail="driver does not expose adb runner",
                skipped_reason="driver_not_supported",
            )
            self._consume(result)
            logger.warning("sidecar monkey skipped reason={} step={}", result.skipped_reason, step)
            return result

        timeout_sec = max(1.0, float(getattr(sidecar, "adb_timeout_sec", 30.0)))
        completed = run_fn("shell", command, check=False, timeout_sec=timeout_sec)
        exit_code = int(getattr(completed, "returncode", 1) or 0)
        stdout = str(getattr(completed, "stdout", "") or "")
        stderr = str(getattr(completed, "stderr", "") or "")
        events_injected = self._parse_events(stdout, fallback=events_requested)
        result = SidecarMonkeyBatchResult(
            triggered_step=step,
            batch_no=batch_no,
            command=command,
            seed=seed,
            events_requested=events_requested,
            events_injected=events_injected,
            exit_code=exit_code,
            success=exit_code == 0,
            stdout_tail=self._tail(stdout),
            stderr_tail=self._tail(stderr),
        )
        self._consume(result)
        logger.info(
            "sidecar monkey batch={} step={} success={} exit_code={} events_injected={}",
            batch_no,
            step,
            result.success,
            result.exit_code,
            result.events_injected,
        )
        return result

    def mark_recovered(self, result: SidecarMonkeyBatchResult) -> None:
        if result.recovered_to_target:
            return
        result.recovered_to_target = True
        self._recovery_count += 1

    def summary(self) -> dict[str, Any]:
        success_rate: float | None = None
        if self._batches_run > 0:
            success_rate = round(self._success_count / max(1, self._batches_run), 4)
        return {
            "enabled": bool(getattr(self.config.sidecar.monkey, "enabled", False)),
            "batches_run": self._batches_run,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "total_events_injected": self._total_events_injected,
            "recovery_count": self._recovery_count,
            "last_exit_code": self._last_exit_code,
        }

    def _consume(self, result: SidecarMonkeyBatchResult) -> None:
        self._batches_run += 1
        self._total_events_injected += max(0, int(result.events_injected))
        self._last_exit_code = int(result.exit_code)
        if result.success:
            self._success_count += 1
        else:
            self._failure_count += 1

    def _build_command(self, target_app_id: str, seed: int, events_requested: int) -> str:
        sidecar = self.config.sidecar.monkey
        throttle_ms = max(0, int(getattr(sidecar, "throttle_ms", 25)))
        pct_touch = self._clamp_percent(getattr(sidecar, "pct_touch", 55))
        pct_motion = self._clamp_percent(getattr(sidecar, "pct_motion", 20))
        pct_nav = self._clamp_percent(getattr(sidecar, "pct_nav", 20))
        pct_syskeys = self._clamp_percent(getattr(sidecar, "pct_syskeys", 5))
        parts = [
            "monkey",
            "-p",
            target_app_id,
            "-s",
            str(seed),
            "--throttle",
            str(throttle_ms),
            "--pct-touch",
            str(pct_touch),
            "--pct-motion",
            str(pct_motion),
            "--pct-nav",
            str(pct_nav),
            "--pct-syskeys",
            str(pct_syskeys),
        ]
        if bool(getattr(sidecar, "ignore_crashes", True)):
            parts.append("--ignore-crashes")
        if bool(getattr(sidecar, "ignore_timeouts", True)):
            parts.append("--ignore-timeouts")
        if bool(getattr(sidecar, "ignore_security_exceptions", True)):
            parts.append("--ignore-security-exceptions")
        parts.append(str(events_requested))
        return " ".join(shlex.quote(item) for item in parts)

    @classmethod
    def _parse_events(cls, stdout: str, fallback: int) -> int:
        match = cls._EVENTS_RE.search(stdout or "")
        if not match:
            return fallback
        try:
            return max(0, int(match.group(1)))
        except ValueError:
            return fallback

    @staticmethod
    def _tail(text: str, limit: int = 600) -> str:
        clean = str(text or "").strip()
        if len(clean) <= limit:
            return clean
        return clean[-limit:]

    @staticmethod
    def _clamp_percent(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 0
        return max(0, min(100, parsed))
