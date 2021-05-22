# coding=utf-8
# author=torchcc

import logging
import ssl
from requests import Session

HttpClient = Session


def create_http_client() -> HttpClient:
    s = Session()
    s.verify = False  # trust all
    return s


def __create_logger():
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

    # The background is set with 40 plus the number of the color, and the foreground with 30

    # These are the sequences need to get colored ouput
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[1;%dm"
    BOLD_SEQ = "\033[1m"

    def formatter_message(message, use_color=True):
        if use_color:
            message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
        else:
            message = message.replace("$RESET", "").replace("$BOLD", "")
        return message

    COLORS = {
        'WARNING': YELLOW,
        'INFO': WHITE,
        'DEBUG': BLUE,
        'CRITICAL': YELLOW,
        'ERROR': RED
    }

    class ColoredFormatter(logging.Formatter):
        def __init__(self, msg, use_color=True):
            logging.Formatter.__init__(self, msg)
            self.use_color = use_color

        def format(self, record):
            levelname = record.levelname
            if self.use_color and levelname in COLORS:
                levelname_color = COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
                record.levelname = levelname_color
            return logging.Formatter.format(self, record)

    # Custom logger class with multiple destinations
    class ColoredLogger(logging.Logger):
        FORMAT = "[$BOLD%(name)-20s$RESET][%(levelname)-18s]  %(message)s ($BOLD%(filename)s$RESET:%(lineno)d)"
        COLOR_FORMAT = formatter_message(FORMAT, True)

        def __init__(self, name):
            logging.Logger.__init__(self, name, logging.DEBUG)

            color_formatter = ColoredFormatter(self.COLOR_FORMAT)

            console = logging.StreamHandler()
            console.setFormatter(color_formatter)

            self.addHandler(console)
            return

    logging.setLoggerClass(ColoredLogger)

    logger = logging.getLogger("crank4py-connector")
    logger.setLevel(logging.DEBUG)
    __stream_handler = logging.StreamHandler()
    __stream_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(pathname)s:%(funcName)s:%(lineno)d] %(message)s'))
    __stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(__stream_handler)
    return logger


log = __create_logger()


def get_trust_all_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ctx.verify_mode = ssl.CERT_NONE
    ctx.check_hostname = False
    return ctx
