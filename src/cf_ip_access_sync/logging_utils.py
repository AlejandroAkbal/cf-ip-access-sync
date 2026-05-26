from __future__ import annotations

import logging


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = record.msg.replace("Authorization: Bearer", "Authorization: [redacted]")
        return True


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger().addFilter(SecretRedactionFilter())
