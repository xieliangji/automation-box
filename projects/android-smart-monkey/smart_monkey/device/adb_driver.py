from __future__ import annotations

import shlex
import subprocess
import tempfile
import time
from pathlib import Path


class AdbDriver:
    def __init__(self, serial: str | None = None, adb_path: str = "adb") -> None:
        self.serial = serial
        self.adb_path = adb_path

    def _base_cmd(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [*self._base_cmd(), *args]
        return subprocess.run(cmd, check=check, text=True, capture_output=True)

    def _shell(self, command: str, check: bool = True) -> str:
        result = self._run("shell", command, check=check)
        return result.stdout.strip()

    def get_foreground_package(self) -> str:
        output = self._shell("dumpsys window | grep mCurrentFocus", check=False)
        if "/" in output:
            token = output.split()[-1]
            return token.split("/")[0]
        return ""

    def get_current_activity(self) -> str | None:
        output = self._shell("dumpsys window | grep mCurrentFocus", check=False)
        if "/" in output:
            token = output.split()[-1]
            return token.split("/")[-1].rstrip("}")
        return None

    def dump_hierarchy(self) -> str:
        remote = "/sdcard/window_dump.xml"
        self._shell("uiautomator dump --compressed /sdcard/window_dump.xml", check=False)
        result = self._run("shell", f"cat {shlex.quote(remote)}", check=False)
        content = result.stdout.strip()
        if not content:
            raise RuntimeError("Failed to dump UI hierarchy. Please verify uiautomator availability.")
        return content

    def take_screenshot(self, path: str | Path) -> None:
        remote = f"/sdcard/smart_monkey_{int(time.time() * 1000)}.png"
        local_path = Path(path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._run("shell", f"screencap -p {shlex.quote(remote)}")
        self._run("pull", remote, str(local_path))
        self._run("shell", f"rm -f {shlex.quote(remote)}", check=False)

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
        # TODO: replace with a more robust strategy, e.g. repeated DEL or element-level clear.
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", check=False)
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
