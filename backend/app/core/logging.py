import logging

from app.core.config import settings


def configure_logging() -> None:
    # Log levels and event names only; never log request bodies or financial values.
    logging.basicConfig(level=settings.LOG_LEVEL.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "pdfminer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
