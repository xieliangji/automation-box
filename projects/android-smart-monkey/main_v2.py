from __future__ import annotations

from pathlib import Path

from smart_monkey.app_v2 import SmartMonkeyAppV2
from smart_monkey.config import ProjectConfig
from smart_monkey.device.robust_adb_driver import RobustAdbDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = ProjectConfig.from_yaml(config_path) if config_path.exists() else ProjectConfig()
    driver = RobustAdbDriver(serial=None)
    app = SmartMonkeyAppV2(driver=driver, config=config, output_dir=Path("output/v2_run"))
    app.run()


if __name__ == "__main__":
    main()
