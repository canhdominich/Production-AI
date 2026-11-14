import json
import logging
import re

PHONE = re.compile(r"(?<!\d)(?:\+?84|0)[\s.-]?\d{2,3}[\s.-]?\d{3}[\s.-]?\d{3,4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def mask(text):
    return EMAIL.sub("[EMAIL]", PHONE.sub("[PHONE]", text))


class MaskingFilter(logging.Filter):
    def filter(self, record):
        record.msg = mask(record.getMessage())
        record.args = ()
        return True


def get_logger(name="anhti.platform"):
    logger = logging.getLogger(name)
    if not any(isinstance(f, MaskingFilter) for f in logger.filters):
        logger.addFilter(MaskingFilter())
    logger.setLevel(logging.INFO)
    return logger


def log_event(logger, event, **fields):
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, sort_keys=True))
