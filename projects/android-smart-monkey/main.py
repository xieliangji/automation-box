from __future__ import annotations

from pathlib import Path

from smart_monkey.config import ProjectConfig
from smart_monkey.device.adb_driver import AdbDriver
from smart_monkey.runner import SmartMonkeyRunner


def main() -> None:
    config = ProjectConfig()
    driver = AdbDriver(serial=None)
    runner = SmartMonkeyRunner(driver=driver, config=config, output_dir=Path("output/default_run"))
    runner.run()


if __name__ == "__main__":
    main()
