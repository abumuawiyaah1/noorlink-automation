"""Application logging setup (stdout + optional rotating file)."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def configure_app_logging(*, log_to_file: bool | None = None) -> None:
    """Idempotent root logger setup so 5xx/DB errors include stack traces in Railway/CF logs."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)

    if log_to_file is None:
        log_to_file = os.getenv("LOG_TO_FILE", "").strip().lower() in {"1", "true", "yes"}

    if log_to_file:
        Path("logs").mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/app.log",
            maxBytes=5_000_000,
            backupCount=5,
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    # Quiet noisy libraries a bit; keep our app loggers at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
