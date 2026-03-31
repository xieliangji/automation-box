from __future__ import annotations

from types import SimpleNamespace

from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.services.sidecar_monkey_service import SidecarMonkeyBatchResult, SidecarMonkeyService


class StubAdbDriver:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "", package: str = "com.demo.app") -> None:
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._package = package
        self.commands: list[tuple[str, ...]] = []

    def _run(self, *args: str, check: bool = True, timeout_sec: float | None = None):
        self.commands.append(tuple(args))
        return SimpleNamespace(returncode=self._returncode, stdout=self._stdout, stderr=self._stderr)

    def get_foreground_package(self) -> str:
        return self._package


def test_sidecar_monkey_service_builds_and_runs_batch() -> None:
    cfg = RuntimeConfig()
    cfg.app.platform = "android"
    cfg.sidecar.monkey.enabled = True
    cfg.sidecar.monkey.step_interval = 2
    cfg.sidecar.monkey.max_batches = 3
    cfg.sidecar.monkey.events_per_batch = 70
    cfg.run.seed = 123
    driver = StubAdbDriver(returncode=0, stdout="Events injected: 68")
    service = SidecarMonkeyService(cfg)

    assert service.enabled("android") is True
    assert service.should_trigger(0) is False
    assert service.should_trigger(1) is True

    result = service.run_batch(step=1, driver=driver, target_app_id="com.demo.app")
    assert isinstance(result, SidecarMonkeyBatchResult)
    assert result is not None
    assert result.success is True
    assert result.events_requested == 70
    assert result.events_injected == 68
    assert result.batch_no == 1
    assert result.seed == 1124
    assert "monkey" in result.command
    assert "-p" in result.command
    assert "com.demo.app" in result.command
    assert driver.commands
    assert driver.commands[0][0] == "shell"

    summary = service.summary()
    assert summary["batches_run"] == 1
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 0
    assert summary["total_events_injected"] == 68
    assert summary["success_rate"] == 1.0


def test_sidecar_monkey_service_handles_failures_and_recovery_mark() -> None:
    cfg = RuntimeConfig()
    cfg.app.platform = "android"
    cfg.sidecar.monkey.enabled = True
    cfg.sidecar.monkey.step_interval = 1
    cfg.sidecar.monkey.max_batches = 1
    driver = StubAdbDriver(returncode=1, stdout="", stderr="security exception")
    service = SidecarMonkeyService(cfg)

    result = service.run_batch(step=0, driver=driver, target_app_id="com.demo.app")
    assert result is not None
    assert result.success is False
    assert result.exit_code == 1
    assert result.events_injected == cfg.sidecar.monkey.events_per_batch
    service.mark_recovered(result)
    summary = service.summary()
    assert summary["failure_count"] == 1
    assert summary["recovery_count"] == 1


def test_sidecar_monkey_service_skips_without_adb_runner() -> None:
    cfg = RuntimeConfig()
    cfg.app.platform = "android"
    cfg.sidecar.monkey.enabled = True
    cfg.sidecar.monkey.step_interval = 1
    cfg.sidecar.monkey.max_batches = 1
    service = SidecarMonkeyService(cfg)

    result = service.run_batch(step=0, driver=object(), target_app_id="com.demo.app")
    assert result is not None
    assert result.success is False
    assert result.skipped_reason == "driver_not_supported"
    summary = service.summary()
    assert summary["failure_count"] == 1
    assert summary["last_exit_code"] == 127
