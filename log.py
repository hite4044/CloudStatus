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
    fmt_styles = {
        "default": "[%(asctime)s.%(msecs)03d] %(module)s:%(lineno)d [%(levelname)s] : %(message)s",
        "no_time": "%(module)s.py:%(lineno)d [%(levelname)s] : %(message)s",
    }
    formatter = logging.Formatter(fmt_styles["no_time"], datefmt="%y-%m-%d %H:%M:%S")

    def update_formatter(self, time_stamp: bool = True):
        if time_stamp:
            self.formatter = logging.Formatter(self.fmt_styles["default"], datefmt="%y-%m-%d %H:%M:%S")
        else:
            self.formatter = logging.Formatter(self.fmt_styles["no_time"])

    def format(self, record):
        return self.COLOR_MAP.get(record.levelno) + self.formatter.format(record) + AnsiColorCodes.RESET


logger = logging.getLogger("YunStoreLogger")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)
