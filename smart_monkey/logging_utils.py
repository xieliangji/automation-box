from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


_CONFIGURED_LOG_FILES: set[Path] = set()
_STDERR_CONFIGURED = False


def setup_logger(output_dir: str | Path, level: str = "INFO") -> Path:
    """Configure Loguru sinks and return the run log file path."""
    global _STDERR_CONFIGURED

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "runtime.log"
    resolved_log_file = log_file.resolve()

    # if not _STDERR_CONFIGURED:
    #     logger.remove()
    #     logger.add(
    #         sys.stderr,
    #         level=level,
    #         enqueue=False,
    #         backtrace=False,
    #         diagnose=False,
    #         colorize=True,
    #         format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
    #     )
    #     _STDERR_CONFIGURED = True

    if resolved_log_file not in _CONFIGURED_LOG_FILES:
        logger.add(
            str(log_file),
            level=level,
            rotation="10 MB",
            retention=5,
            enqueue=False,
            encoding="utf-8",
            backtrace=False,
            diagnose=False,
            colorize=True,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
        )
        _CONFIGURED_LOG_FILES.add(resolved_log_file)

    return log_file
