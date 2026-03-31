from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path

from smart_monkey.device.capabilities import DriverCapabilities


class AdbDriver:
    def __init__(
        self,
        serial: str | None = None,
        adb_path: str = "adb",
        command_timeout_sec: float = 20.0,
    ) -> None:
        self.serial = serial
        self.adb_path = adb_path
        self.command_timeout_sec = command_timeout_sec

    def _base_cmd(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def _run(
        self,
        *args: str,
        check: bool = True,
        timeout_sec: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [*self._base_cmd(), *args]
        timeout = self.command_timeout_sec if timeout_sec is None else timeout_sec
        try:
            return subprocess.run(cmd, check=check, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            joined = " ".join(cmd)
            raise RuntimeError(f"ADB command timed out after {timeout}s: {joined}") from exc

    def _shell(self, command: str, check: bool = True, timeout_sec: float | None = None) -> str:
        result = self._run("shell", command, check=check, timeout_sec=timeout_sec)
        return result.stdout.strip()

    def get_foreground_package(self) -> str:
        output = self._shell("dumpsys window | grep mCurrentFocus", check=False)
        if "/" in output:
            token = output.split()[-1]
            return token.split("/")[0]
        return ""

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            platform="android",
            supports_launch_target=True,
            supports_press_back=True,
            supports_press_home=True,
            supports_stop_app=True,
            supports_log_stream=False,
        )

    def get_current_activity(self) -> str | None:
        output = self._shell("dumpsys window | grep mCurrentFocus", check=False)
        if "/" in output:
            token = output.split()[-1]
            return token.split("/")[-1].rstrip("}")
        return None

    def dump_hierarchy(self) -> str:
        remote = "/sdcard/window_dump.xml"
        self._shell("uiautomator dump --compressed /sdcard/window_dump.xml", check=False, timeout_sec=15.0)
        result = self._run("shell", f"cat {shlex.quote(remote)}", check=False, timeout_sec=15.0)
        content = result.stdout.strip()
        if not content:
            raise RuntimeError("Failed to dump UI hierarchy. Please verify uiautomator availability.")
        return content

    def take_screenshot(self, path: str | Path) -> None:
        remote = f"/sdcard/smart_monkey_{int(time.time() * 1000)}.png"
        local_path = Path(path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._run("shell", f"screencap -p {shlex.quote(remote)}", timeout_sec=20.0)
        self._run("pull", remote, str(local_path), timeout_sec=20.0)
        self._run("shell", f"rm -f {shlex.quote(remote)}", check=False, timeout_sec=10.0)

    def click(self, x: int, y: int) -> bool:
        self._shell(f"input tap {x} {y}", check=False)
        return True

    def long_click(self, x: int, y: int, duration_ms: int = 800) -> bool:
        self._shell(f"input swipe {x} {y} {x} {y} {duration_ms}", check=False)
        return True

    def input_text(self, text: str) -> bool:
        safe = text.replace(" ", "%s")
        self._shell(f"input text {safe}", check=False)
        return True

    def clear_text(self) -> bool:
        # 待办：替换为更稳健的清空策略，例如连续删除或按元素级清空。
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", check=False)
        return True

    def pinch(
        self,
        x1_start: int,
        y1_start: int,
        x1_end: int,
        y1_end: int,
        x2_start: int,
        y2_start: int,
        x2_end: int,
        y2_end: int,
        duration_ms: int = 280,
    ) -> bool:
        # 安卓系统在各版本中都缺少统一的原生缩放指令。
        # 这里使用两条并发滑动来模拟双指手势。
        script = (
            f"(input swipe {x1_start} {y1_start} {x1_end} {y1_end} {duration_ms} & "
            f"input swipe {x2_start} {y2_start} {x2_end} {y2_end} {duration_ms}; wait)"
        )
        self._shell(script, check=False)
        return True

    def press_back(self) -> bool:
        self._shell("input keyevent KEYCODE_BACK", check=False)
        return True

    def press_home(self) -> bool:
        self._shell("input keyevent KEYCODE_HOME", check=False)
        return True

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        if activity:
            self._shell(f"am start -n {package_name}/{activity}", check=False)
        else:
            self._shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1", check=False)
        return True

    def stop_app(self, package_name: str) -> bool:
        self._shell(f"am force-stop {package_name}", check=False)
        return True

    def wait_idle(self, timeout_ms: int = 1500) -> None:
        time.sleep(timeout_ms / 1000)
