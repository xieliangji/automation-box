from __future__ import annotations

from pathlib import Path

from loguru import logger


_CONFIGURED_LOG_FILES: set[Path] = set()
def setup_logger(output_dir: str | Path, level: str = "INFO") -> Path:
    """配置日志输出并返回本次运行日志路径。"""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "runtime.log"
    resolved_log_file = log_file.resolve()

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
