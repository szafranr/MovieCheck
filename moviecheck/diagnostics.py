import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(directory: Path):
    logger = logging.getLogger("moviecheck")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "errors.log", maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    except OSError:
        # Brak możliwości zapisania diagnostyki nie blokuje wyszukiwania.
        handler = logging.NullHandler()
    logger.addHandler(handler)
