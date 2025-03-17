import logging


class AnsiColorCodes:
    ITALIC = "\033[3m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"
    RESET = "\033[0m"


class CustomFormatter(logging.Formatter):
    COLOR_MAP = {
        logging.DEBUG: AnsiColorCodes.ITALIC,
        logging.INFO: AnsiColorCodes.GREEN,
        logging.WARNING: AnsiColorCodes.YELLOW,
        logging.ERROR: AnsiColorCodes.RED,
        logging.CRITICAL: AnsiColorCodes.BOLD_RED,
    }
    COLOR_MAP.setdefault(0, AnsiColorCodes.RESET)
    # noinspection SpellCheckingInspection
    time_styles = {
        "default": "[%(asctime)s.%(msecs)03d] %(module)s:%(lineno)d",
        "no_time": "%(module)s.py:%(lineno)d",
    }
    level_name = "[%(levelname)s]"
    formatter = logging.Formatter(time_styles["no_time"], datefmt="%y-%m-%d %H:%M:%S")

    def format(self, record):
        head = self.formatter.format(record)
        raw_msg = f"{head} {(18 - len(head)) * ' '} [{record.levelname}] : {record.msg}"
        return self.COLOR_MAP.get(record.levelno) + raw_msg + AnsiColorCodes.RESET


logger = logging.getLogger("CloudStoreLogger")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)
