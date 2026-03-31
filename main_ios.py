from __future__ import annotations

import shutil
from pathlib import Path

from main import main as run_main


def main() -> None:
    source = Path("config.ios.yaml")
    target = Path("config.yaml")
    if not source.exists():
        raise FileNotFoundError("Missing config.ios.yaml. Please create it first.")
    shutil.copyfile(source, target)
    run_main()


if __name__ == "__main__":
    main()
