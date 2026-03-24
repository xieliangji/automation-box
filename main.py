from __future__ import annotations

from pathlib import Path

from smart_monkey.app_runtime import SmartMonkeyAppRuntime
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.device.robust_adb_driver import RobustAdbDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = RuntimeConfig.from_yaml(config_path) if config_path.exists() else RuntimeConfig()
    driver = RobustAdbDriver(serial=None)
    app = SmartMonkeyAppRuntime(driver=driver, config=config, output_dir=Path("output/run"))
    app.run()


if __name__ == "__main__":
    main()
