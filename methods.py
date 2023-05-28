import datetime
import time
from functools import wraps
from typing import Callable, Coroutine, Any

from config import logger, COINS_PER_MSG
from telegram import Update

from db.crud import check_user_exists, create_user, get_all_users, get_cooldown, get_last_action, add_coins, \
    add_user_coins_per_min


def cooldown_expired(user_id: int, action_id: int) -> bool:
    now = datetime.datetime.now()
    cooldown = get_cooldown(action_id)
    last_action_time = get_last_action(user_id, action_id)
    if last_action_time:
        remaining_time = last_action_time.timestamp() + cooldown - now.timestamp()
        if remaining_time < 0:
            return True
        else:
            logger.debug(f'wait: {remaining_time}')
            return False


def add_coins_for_msg(user_id: int):
    amount = COINS_PER_MSG
    add_coins(user_id, amount)


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
        all_users = get_all_users()
        all_users = [i.user_id for i in all_users]
        if chat_id != self.chat_id and chat_id not in all_users:
            return wrapper
        else:
            is_user = check_user_exists(user_id)
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
                create_user(user_id, user_name, user_nickname)

        return await command_handler(self, *args, **kwargs)

    return wrapper


def chat_only(command_handler: Callable[[Update, Any], Coroutine[Any, Any, None]]) -> \
        Callable[..., Coroutine[Any, Any, None]]:
    @wraps(command_handler)
    async def wrapper(self, *args, **kwargs):
        update = kwargs.get('update') or args[0]
        if update.effective_chat.type != 'supergroup' and update.effective_chat.type != 'supergroup':
            await self.group_only_notification(*args, **kwargs)
            return wrapper
        return await command_handler(self, *args, **kwargs)

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
        add_user_coins_per_min()
