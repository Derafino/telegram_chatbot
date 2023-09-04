import json
import os
import sys
import queue
from loguru import logger

current_dir = os.path.dirname(os.path.abspath(__file__))


def settings():
    file_path = os.path.join(current_dir, "config.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return dict(json.loads(f.read()))


cfg = settings()
TELEGRAM_TOKEN = cfg.get("telegram_token", None)
TELEGRAM_CHAT = cfg.get("telegram_chat", None)
ADMINS = cfg.get("admins", None)
COINS_PER_MSG = cfg.get("coins_per_msg", None)
ANIME_PRICE = cfg.get("anime_price", 10000)

COOLDOWN = cfg.get("cooldown", None)
if COOLDOWN:
    MSG_CD = COOLDOWN.get("msg", 60)
    WHO_CD = COOLDOWN.get("who", 20)
    BALL8_CD = COOLDOWN.get("8ball", 10)
    PICK_CD = COOLDOWN.get("pick", 10)
    RATING_CD = COOLDOWN.get("rating", 30)
    ANIME_CD = COOLDOWN.get("anime", 30)
    BJ_CD = COOLDOWN.get("bj", 30)

xp_range = list(range(15, 26))

min_bet = cfg.get("min_bet", 1000)
min_giveaway_coins = cfg.get("min_giveaway_coins", 10000)
max_giveaway_coins = cfg.get("max_giveaway_coins", 100000)

anime_path = os.path.join(current_dir, "img/anime")

# ---------------------- LOGGER ----------------------

log_dir = os.path.join(current_dir, "/log")

logger_config = {
    "handlers": [
        {"sink": sys.stderr, "colorize": True, "level": "DEBUG"},
        {"sink": os.path.join(log_dir, "debug.log"), "serialize": False, "level": "DEBUG"},
    ],

}
logger.configure(**logger_config)
