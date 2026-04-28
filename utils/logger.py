"""
utils/logger.py
---------------
Configures structured logging for the entire application.
Log format: [timestamp] [level] [module] message
"""
import logging
import sys


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "faiss", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
