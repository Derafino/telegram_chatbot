import datetime
import random
import time

from functools import wraps
from typing import Callable, Coroutine, Any, Union
from telegram import Update

from config import xp_range, logger
from db.crud import UserCRUD, UserActionCRUD, ActionCooldownCRUD, UserLevelCRUD


def cooldown_expired(user_id: int, action_id: int) -> Union[bool, int]:
    cooldown = ActionCooldownCRUD.get_cooldown(action_id)
    last_action_time = UserActionCRUD.get_last_action(user_id, action_id)
    if last_action_time:
        remaining_time = calculate_remaining_time(last_action_time, cooldown)
        if remaining_time < 0:
            return True
        else:
            return int(remaining_time)
    else:
        UserActionCRUD.add_action(user_id, action_id)
        return True


def calculate_remaining_time(last_action_time, cooldown):
    now = datetime.datetime.now()
    return last_action_time.timestamp() + cooldown - now.timestamp()


def auth_user(command_handler: Callable[[Update, Any], Coroutine[Any, Any, None]]):
    @wraps(command_handler)
    async def wrapper(self, *args, **kwargs):

        update = kwargs.get('update') or args[0]
        if update.callback_query:
            chat_id = int(update.callback_query.message.chat.id)
            user_id = int(update.callback_query.message.from_user.id)
        else:
            chat_id = int(update.message.chat_id)
            user_id = int(update.message.from_user.id)
        logger.debug(f"user ({user_id}) triggers handler ({command_handler.__name__})")
        all_users = UserCRUD.get_all_users()
        all_users = [i.user_id for i in all_users]
        if chat_id != self.chat_id and chat_id not in all_users:
            return wrapper
        else:
            is_user = UserCRUD.check_user_exists(user_id)
            if not is_user:
                if update.callback_query:

                    user_name = update.callback_query.message.from_user.username
                    user_nickname = update.callback_query.message.from_user.first_name
                    last_name = update.callback_query.message.from_user.last_name
                else:

                    user_name = update.message.from_user.username
                    user_nickname = update.message.from_user.first_name
                    last_name = update.message.from_user.last_name
                if last_name:
                    user_nickname += f" {last_name}"
                UserCRUD.create_user(user_id, user_name, user_nickname)
                UserLevelCRUD.create_level(user_id)

        return await command_handler(self, *args, **kwargs)

    return wrapper


def chat_only(handler: Callable[[Update, Any], Coroutine[Any, Any, None]]) -> \
        Callable[..., Coroutine[Any, Any, None]]:
    @wraps(handler)
    async def wrapper(self, *args, **kwargs):
        update = kwargs.get('update') or args[0]
        if update.effective_chat.type != 'supergroup' and update.effective_chat.type != 'supergroup':
            await self.group_only_notification(*args, **kwargs)
            return wrapper
        return await handler(self, *args, **kwargs)

    return wrapper


def private_only(command_handler: Callable[[Update, Any], Coroutine[Any, Any, None]]):
    @wraps(command_handler)
    async def wrapper(self, *args, **kwargs):
        update = kwargs.get('update') or args[0]
        if update.effective_chat.type != 'private':
            await self.private_only_notification(*args, **kwargs)
            return wrapper
        return await command_handler(self, *args, **kwargs)

    return wrapper


def add_coins_per_min():
    while True:
        time.sleep(60)
        UserCRUD.add_user_coins_per_min()


def calc_xp(user_id):
    user_level = UserLevelCRUD.get_level(user_id)
    add_xp_amount = random.choice(xp_range)
    user_level.xp += add_xp_amount
    if user_level.xp >= user_level.xp_needed:
        user_level.xp = user_level.xp - user_level.xp_needed
        user_level.level += 1
        user_level.xp_needed = 5 * (user_level.level ** 2) + (50 * user_level.level) + 100
    UserLevelCRUD.update_level(user_id, user_level.level, user_level.xp, user_level.xp_needed)


def validate_bet(bet, min_bet):
    if bet.isdigit() and int(bet) * 100 >= min_bet:
        return True
    else:
        return False
