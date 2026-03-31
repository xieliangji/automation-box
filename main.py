from __future__ import annotations

from pathlib import Path

from smart_monkey.app_runtime import SmartMonkeyAppRuntime
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.device.robust_adb_driver import RobustAdbDriver
from smart_monkey.device.wda_driver import WdaDriver


def main() -> None:
    config_path = Path("config.yaml")
    config = RuntimeConfig.from_yaml(config_path) if config_path.exists() else RuntimeConfig()
    if config.app.platform == "ios":
        driver = WdaDriver(
            wda_url=config.ios.wda_url,
            target_bundle_id=config.app.target_app_id,
            launch_target=config.app.launch_target,
            request_timeout_sec=float(config.ios.command_timeout_sec),
            session_create_timeout_sec=float(config.ios.session_create_timeout_sec),
            request_retry=int(config.ios.request_retry),
            keep_session=bool(config.ios.keep_session),
            auto_recreate_session=bool(config.ios.auto_recreate_session),
        )
    else:
        driver = RobustAdbDriver(serial=None)
    app = SmartMonkeyAppRuntime(driver=driver, config=config, output_dir=Path("output/run"))
    app.run()


if __name__ == "__main__":
    main()
