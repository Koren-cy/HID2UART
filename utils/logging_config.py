"""日志配置模块。

用法：
    from utils.logging_config import setup_logging
    setup_logging()

日志级别可通过环境变量 LOG_LEVEL 配置，默认为 INFO。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# 日志格式
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 默认日志级别
_DEFAULT_LEVEL = "INFO"


def setup_logging(
    level: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """
    配置全局日志系统。

    同时输出到控制台和（可选的）文件。

    参数：
        level: 日志级别字符串（DEBUG/INFO/WARNING/ERROR）。
               默认为环境变量 LOG_LEVEL 或 INFO。
        log_file: 日志文件路径，默认为 None。
    """
    if level is None:
        level = os.environ.get("LOG_LEVEL", _DEFAULT_LEVEL).upper()

    numeric_level = getattr(logging, level, logging.INFO)

    handlers: list[logging.Handler] = []

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    )
    handlers.append(console_handler)

    # 文件处理器
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=numeric_level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=handlers,
        force=True,
    )
