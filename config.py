import json
import os
import sys

from loguru import logger


def settings():
    with open("./config.json", "r", encoding="utf-8") as f:
        return dict(json.loads(f.read()))


cfg = settings()
TELEGRAM_TOKEN = cfg.get("telegram_token", None)
TELEGRAM_CHAT = cfg.get("telegram_chat", None)
COINS_PER_MSG = cfg.get("coins_per_msg", None)

# ---------------------- LOGGER ----------------------

log_dir = "./log"

logger_config = {
    "handlers": [
        {"sink": sys.stderr, "colorize": True, "level": "DEBUG"},
        {"sink": os.path.join(log_dir, "debug.log"), "serialize": False, "level": "DEBUG"},
    ],

}
logger.configure(**logger_config)
