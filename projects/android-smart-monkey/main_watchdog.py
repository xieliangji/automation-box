from __future__ import annotations

from pathlib import Path

from smart_monkey.app_watchdog import WatchdogSmartMonkeyApp
from smart_monkey.config import ProjectConfig
from smart_monkey.device.robust_adb_driver import RobustAdbDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = ProjectConfig.from_yaml(config_path) if config_path.exists() else ProjectConfig()
    driver = RobustAdbDriver(serial=None)
    app = WatchdogSmartMonkeyApp(driver=driver, config=config, output_dir=Path("output/watchdog_run"))
    app.run()


if __name__ == "__main__":
    main()
