import asyncio
import random
import threading

from telegram import Update, User
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from telegram.helpers import escape_markdown

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT, logger
from db.crud import setup_database, edit_action_time, get_all_users, get_user_balance
from games.magic_8_ball import magic_8_ball_phrase
from methods import auth_user, chat_only, cooldown_expired, add_coins_for_msg, add_coins_per_min


class TelegramBot:
    def __init__(self, token, chat_id):

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.app = Application.builder().token(token).build()
        self.chat_id = chat_id
        handlers = [
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.text_handler),

            CommandHandler('start', self.start_handler),
            CommandHandler('who', self.who_handler),
            CommandHandler('8ball', self.magic_8_ball_handler),
            CommandHandler('balance', self.balance_handler),
            CommandHandler('pick', self.pick_handler)

        ]
        for handle in handlers:
            self.app.add_handler(handle)
        try:
            self.loop.run_until_complete(self.startup_telegram())
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.shutdown_telegram())

    async def startup_telegram(self) -> None:

        await self.app.initialize()
        await self.app.start()
        if self.app.updater:
            await self.app.updater.start_polling(
                bootstrap_retries=-1,
                timeout=30,
                drop_pending_updates=True,
            )
            while True:
                await asyncio.sleep(10)
                if not self.app.updater.running:
                    break

    async def shutdown_telegram(self) -> None:
        if self.app.updater:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ COMMAND HANDLERS ~~~~~~~~~~~~~~~~~~~~~~~~~~
    @auth_user
    @chat_only
    async def text_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for text msg and adding coins
        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        action_id = 7
        logger.debug(user_id)
        if cooldown_expired(user_id, action_id):
            edit_action_time(user_id=update.message.from_user.id, action_id=action_id)
            add_coins_for_msg(user_id)
        else:
            pass

    @auth_user
    async def start_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /start
        :param update:
        :param context:
        """
        bot_message = 'Hello'
        chat_id = update.message.chat_id

        await self.app.bot.send_message(chat_id, text=bot_message)

    @auth_user
    @chat_only
    async def who_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /who
        :param update:
        :param context:
        """
        all_users = get_all_users()
        who_choice = random.choice(all_users)
        who_choice_mention = User(who_choice.user_id, who_choice.user_nickname, False).mention_markdown_v2()
        bot_message = who_choice_mention
        await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)

    @auth_user
    async def magic_8_ball_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /8ball
        :param update:
        :param context:
        """
        text = magic_8_ball_phrase()
        text = escape_markdown(text, 2)
        bot_message = f"||{text}||"
        await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)

    @auth_user
    async def balance_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /balance
        :param update:
        :param context:
        """

        user_id = update.message.from_user.id
        balance = str(get_user_balance(user_id) / 100)
        balance = escape_markdown(balance, 2)
        bot_message = f"Balance: *{balance}*"
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 15, data=[update.message, reply])

    @auth_user
    async def pick_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /pick
        User sends "/pick variant1, variant2, variant3"
        The function randomly picks one of the variants and replies with it

        :param update:
        :param context:
        """
        if context.args:
            user_text = ' '.join(context.args)
            variants = user_text.split(',')
            variants = [variant.strip() for variant in variants]
            variants = [variant for variant in variants if variant]
            if variants:
                picked_variant = random.choice(variants)
                await update.message.reply_text(f"The picked variant is: *{picked_variant}*",
                                                parse_mode=ParseMode.MARKDOWN_V2)
            else:
                reply = update.message.reply_text("No valid variants found.")
                context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])
        else:
            reply = await update.message.reply_text("Please specify the variants.")
            context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ ADDITIONAL FUNC ~~~~~~~~~~~~~~~~~~~~~~~~~~
    async def group_only_notification(self, update: Update, context: CallbackContext):
        """
        send notification that command can be used only on group chat
        :param update:
        :param context:
        """
        bot_message = "Only group chat"
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])

    async def private_only_notification(self, update: Update, context: CallbackContext):
        """
        send notification that command can be used only on group chat
        :param update:
        :param context:
        """
        bot_message = "Only private"
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])

    @staticmethod
    async def delete_messages(context: CallbackContext) -> None:
        """
        delete msg from context
        :param context:
        """
        messages = context.job.data
        for msg in messages:
            try:
                await msg.delete()
            except Exception as e:
                logger.error(e)


if __name__ == '__main__':
    setup_database()
    bonus_per_min_thread = threading.Thread(target=add_coins_per_min, daemon=True)
    bonus_per_min_thread.start()

    TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)
