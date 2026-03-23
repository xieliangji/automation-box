from __future__ import annotations

from pathlib import Path

from smart_monkey.app_v5 import SmartMonkeyAppV5
from smart_monkey.config_v2 import ProjectConfigV2
from smart_monkey.device.robust_adb_driver import RobustAdbDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = ProjectConfigV2.from_yaml(config_path) if config_path.exists() else ProjectConfigV2()
    driver = RobustAdbDriver(serial=None)
    app = SmartMonkeyAppV5(driver=driver, config=config, output_dir=Path("output/v5_run"))
    app.run()


if __name__ == "__main__":
    main()
