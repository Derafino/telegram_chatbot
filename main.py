import asyncio
import random
import threading

from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler
from telegram.helpers import escape_markdown
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT, logger, ANIME_PRICE, MSG_CD, WHO_CD, BALL8_CD, PICK_CD, RATING_CD, \
    ANIME_CD
from db.crud import setup_database, UserCRUD, UserActionCRUD, UserLevelCRUD
from games.black_jack import sum_hand, deal_hand, deal_card, deck
from games.magic_8_ball import magic_8_ball_phrase
from methods import auth_user, chat_only, cooldown_expired, add_coins_per_min, calc_xp
from modules.anime import choose_random_anime_image

BLACKJACK = 0


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
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED & ~filters.UpdateType.EDITED_MESSAGE,
                           self.text_handler),

            CommandHandler('start', self.start_handler),
            CommandHandler('who', self.who_handler),
            CommandHandler('8ball', self.magic_8_ball_handler),
            CommandHandler('balance', self.balance_handler),
            CommandHandler('pick', self.pick_handler),
            CommandHandler('boosters', self.boosters_handler),
            CommandHandler('level', self.level_handler),
            CommandHandler('rating', self.rating_handler),
            CommandHandler('anime', self.anime_handler),
            CommandHandler('cd', self.cd_handler),
            ConversationHandler(
                entry_points=[CommandHandler('bj', self.bj_start_handler)],
                states={
                    BLACKJACK: [
                        CallbackQueryHandler(self.bj_hit_handler, pattern='^hit$'),
                        CallbackQueryHandler(self.bj_stand_handler, pattern='^stand$')
                    ]
                },
                fallbacks=[CommandHandler('start', self.bj_start_handler)],
            )

        ]
        for handle in handlers:
            self.app.add_handler(handle)
        try:
            self.loop.run_until_complete(self.startup_telegram())
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.shutdown_telegram())
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")

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
        action_id = 1
        if cooldown_expired(user_id, action_id):
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            calc_xp(user_id)
            UserCRUD.add_user_coins_per_msg(user_id)

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
        user_id = update.message.from_user.id
        action_id = 2
        if cooldown_expired(user_id, action_id):
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            all_users = UserCRUD.get_all_users()
            who_choice = random.choice(all_users)
            who_choice_mention = User(who_choice.user_id, who_choice.user_nickname, False).mention_markdown_v2()
            bot_message = who_choice_mention
            await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def magic_8_ball_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /8ball
        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        action_id = 3
        if cooldown_expired(user_id, action_id):
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            text = magic_8_ball_phrase()
            text = escape_markdown(text, 2)
            bot_message = f"||{text}||"
            await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def balance_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /balance
        :param update:
        :param context:
        """

        user_id = update.message.from_user.id
        balance = str(UserCRUD.get_user_balance(user_id) / 100)
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
        user_id = update.message.from_user.id
        action_id = 4
        if cooldown_expired(user_id, action_id):

            if context.args:
                user_text = ' '.join(context.args)
                variants = user_text.split(',')
                variants = [variant.strip() for variant in variants]
                variants = [variant for variant in variants if variant]
                if variants:
                    picked_variant = random.choice(variants)
                    await update.message.reply_text(f"The picked variant is: *{picked_variant}*",
                                                    parse_mode=ParseMode.MARKDOWN_V2)
                    UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

                else:
                    reply = update.message.reply_text("No valid variants found.")
                    context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])
            else:
                reply = await update.message.reply_text("Please specify the variants.")
                context.job_queue.run_once(self.delete_messages, 10, data=[update.message, reply])
        else:
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def boosters_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /boosters

        :param update:
        :param context:
        """
        user_coins_per_msg, user_coins_per_min = UserCRUD.get_boosters_amount(update.message.from_user.id)
        user_coins_per_msg = escape_markdown(str(user_coins_per_msg / 100), 2)
        user_coins_per_min = escape_markdown(str(user_coins_per_min / 100), 2)
        bot_message = f"Coins per MSG: *{user_coins_per_msg}*\nCoins per MIN: *{user_coins_per_min}*"
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 15, data=[update.message, reply])

    @auth_user
    async def level_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /level

        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        user_level = UserLevelCRUD.get_level(user_id)
        percent = user_level.xp * 100 / user_level.xp_needed
        percent -= percent % +10
        percent = int(percent / 10)
        string = f"|{'➖' * int(percent)}{'----' * int(10 - percent)}|"
        text = f"Level: {user_level.level}\n" \
               f"{string} {user_level.xp}/{user_level.xp_needed} XP\n"
        bot_message = escape_markdown(text, 2)
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 15, data=[update.message, reply])

    @auth_user
    @chat_only
    async def rating_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /rating

        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        action_id = 5
        if cooldown_expired(user_id, action_id):
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            users = UserLevelCRUD.get_top_users()
            logger.debug(users)
            bot_message = ''
            for i, user in enumerate(users):
                if i == 0:
                    i = '🥇'
                elif i == 1:
                    i = '🥈'
                elif i == 2:
                    i = '🥉'
                else:
                    i = f' {i + 1}\.'
                user_id = user.user_id
                user_nickname = user.user.user_nickname
                user_mention = User(user_id, escape_markdown(user_nickname, 2), False).mention_markdown_v2()
                bot_message += f"{i} {user_mention} \({user.level} lvl\)\n"
            reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
            context.job_queue.run_once(self.delete_messages, 15, data=[update.message, reply])
        else:
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def anime_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /anime

        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        action_id = 6
        if cooldown_expired(user_id, action_id):
            if UserCRUD.pay_coins(user_id, ANIME_PRICE):
                UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

                await update.message.reply_photo(photo=choose_random_anime_image(), parse_mode=ParseMode.MARKDOWN_V2)
        else:
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def cd_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /cd

        :param update:
        :param context:
        """
        bot_message = f"MSG: *{MSG_CD}s*\n" \
                      f"Who: *{WHO_CD}s*\n" \
                      f"8ball: *{BALL8_CD}s*\n" \
                      f"Pick: *{PICK_CD}s*\n" \
                      f"Rating: *{RATING_CD}s*\n" \
                      f"Anime: *{ANIME_CD}s*\n"
        reply = await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        context.job_queue.run_once(self.delete_messages, 15, data=[update.message, reply])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ BLACK JACK ~~~~~~~~~~~~~~~~~~~~~~~~~~
    @auth_user
    async def bj_start_handler(self, update: Update, context: CallbackContext) -> int:
        """
        handler for /bj

        :param update:
        :param context:
        """

        player_hand = deal_hand(deck)
        dealer_hand = deal_hand(deck)

        context.user_data['player_hand'] = player_hand
        context.user_data['dealer_hand'] = dealer_hand

        keyboard = [
            [InlineKeyboardButton('Hit', callback_data='hit'),
             InlineKeyboardButton('Stand', callback_data='stand')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = await update.message.reply_text(f'Your hand: {player_hand}, total: {sum_hand(player_hand)}\n'
                                                  f'Dealer hand: {dealer_hand}, total: {sum_hand(dealer_hand)}\n'
                                                  f'Hit or Stand? ',
                                                  reply_markup=reply_markup)
        context.user_data['message_id'] = message.message_id
        context.user_data['player_id'] = message.from_user.id

        return BLACKJACK

    @auth_user
    async def bj_hit_handler(self, update: Update, context: CallbackContext) -> int:
        if context.user_data['player_id'] == update.callback_query.from_user.id:
            player_hand = context.user_data['player_hand']
            player_hand.append(deal_card(deck))
            dealer_hand = context.user_data['dealer_hand']

            keyboard = [
                [InlineKeyboardButton('Hit', callback_data='hit'),
                 InlineKeyboardButton('Stand', callback_data='stand')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if sum_hand(player_hand) > 21:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, total: {sum_hand(player_hand)}\n'
                                                         f'Bust! You lose.')
                return ConversationHandler.END
            elif sum_hand(player_hand) == 21:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, total: {sum_hand(player_hand)}\n'
                                                         f'Blackjack! You win.')
                return ConversationHandler.END
            else:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, total: {sum_hand(player_hand)}\n'
                                                         f'Dealer hand: {dealer_hand}, total: {sum_hand(dealer_hand)}\n'
                                                         f'Hit or Stand?',
                                                    reply_markup=reply_markup)

                return BLACKJACK

    @auth_user
    async def bj_stand_handler(self, update: Update, context: CallbackContext) -> int:
        if context.user_data['player_id'] == update.callback_query.from_user.id:
            player_hand = context.user_data['player_hand']
            dealer_hand = context.user_data['dealer_hand']

            while sum_hand(dealer_hand) < 17:
                dealer_hand.append(deal_card(deck))

            if sum_hand(dealer_hand) > 21:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, '
                                                         f'total: {sum_hand(player_hand)}\n'
                                                         f'Dealer\'s hand: {dealer_hand}, '
                                                         f'total: {sum_hand(dealer_hand)}\n'
                                                         f'Dealer busts! You win.')
            elif sum_hand(dealer_hand) < sum_hand(player_hand):
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, '
                                                         f'total: {sum_hand(player_hand)}\n'
                                                         f'Dealer\'s hand: {dealer_hand}, '
                                                         f'total: {sum_hand(dealer_hand)}\n'
                                                         f'You win!')
            elif sum_hand(dealer_hand) > sum_hand(player_hand):
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, '
                                                         f'total: {sum_hand(player_hand)}\n'
                                                         f'Dealer\'s hand: {dealer_hand}, '
                                                         f'total: {sum_hand(dealer_hand)}\n'
                                                         f'You lose.')
            else:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, '
                                                         f'total: {sum_hand(player_hand)}\n'
                                                         f'Dealer\'s hand: {dealer_hand}, '
                                                         f'total: {sum_hand(dealer_hand)}\n'
                                                         f'Push. It\'s a tie.')

            return ConversationHandler.END

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
