"""Logging (standard library): console plus an optional rotating file."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from td_arabic.config import PATHS

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_root = logging.getLogger("td_arabic")


def _add_handler(handler: logging.Handler) -> None:
    """Attach ``handler`` to the project root logger with the shared format.

    Args:
        handler: Handler to configure and attach.
    """
    handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    _root.addHandler(handler)


def get_logger(name: str = "td_arabic", log_to_file: bool = False) -> logging.Logger:
    """Return a project logger, configuring handlers on first use.

    Args:
        name: Logger name; prefixed with ``td_arabic.`` if needed.
        log_to_file: If True, also write to ``logs/app.log`` (10 MB, 5 backups).
            The file handler is added only once per process.

    Returns:
        The configured :class:`logging.Logger`.
    """
    if not _root.handlers:
        _root.setLevel(logging.INFO)
        _add_handler(logging.StreamHandler())
    if log_to_file and not any(isinstance(h, RotatingFileHandler) for h in _root.handlers):
        PATHS.logs.mkdir(parents=True, exist_ok=True)
        _add_handler(RotatingFileHandler(PATHS.logs / "app.log", maxBytes=10_000_000,
                                         backupCount=5, encoding="utf-8"))
    return logging.getLogger(name if name.startswith("td_arabic") else f"td_arabic.{name}")
