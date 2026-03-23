from __future__ import annotations

from pathlib import Path

from smart_monkey.app import SmartMonkeyApp
from smart_monkey.config import ProjectConfig
from smart_monkey.device.adb_driver import AdbDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = ProjectConfig.from_yaml(config_path) if config_path.exists() else ProjectConfig()
    driver = AdbDriver(serial=None)
    app = SmartMonkeyApp(driver=driver, config=config, output_dir=Path("output/stateful_run"))
    app.run()


if __name__ == "__main__":
    main()
