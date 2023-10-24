import asyncio
import datetime
import random
import threading
import time

from typing import Tuple, Optional

from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ChatMember, \
    ChatMemberUpdated
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler, ContextTypes, ChatMemberHandler, AIORateLimiter
from telegram.helpers import escape_markdown

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT, logger, ANIME_PRICE, MSG_CD, WHO_CD, BALL8_CD, PICK_CD, RATING_CD, \
    ANIME_CD, min_bet, ADMINS, max_giveaway_coins, min_giveaway_coins, IMG_CD, IMG_PRICE
from db.crud import setup_database, UserCRUD, UserActionCRUD, UserLevelCRUD, UsersBoostersCRUD, GiveawayCRUD
from games.black_jack import sum_hand, deal_hand, deal_card, deck
from games.magic_8_ball import magic_8_ball_phrase
from methods import auth_user, chat_only, cooldown_expired, add_coins_per_min, calc_xp, validate_bet, \
    admin_only, extract_datetime, validate_coins_amount
from modules.anime import choose_random_anime_image
from modules.epic_games import EGSFreeGames
from modules.img import choose_random_image
from modules.shop import SHOP_ITEMS, ShopItemBoosterMSG, ShopItemBoosterPerMin
from modules.slap import choose_random_slap_gif
from modules.steam_events import SteamEvents

BLACKJACK = 0
SET_TYPE, SET_COINS_AMOUNT, SET_ITEM, SET_AMOUNT, SET_END_DATETIME_OR_ADD_ITEM, SET_WINNERS_AMOUNT, SET_END_DATETIME, \
    SET_DESCRIPTION, SET_PHOTO, REVIEW = range(10)
IN_CONVERSATION = 0
SET_AUC_DESCRIPTION = 0
CONFIRM_AUC_BET = 0


class TelegramBot:
    def __init__(self, token, chat_id):

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        app_builder = Application.builder()
        app_builder.token(token)
        rate_limiter = AIORateLimiter(
            overall_max_rate=30,
            overall_time_period=1,
            group_max_rate=20,
            group_time_period=60,
            max_retries=3,
        )
        app_builder.rate_limiter(rate_limiter)
        self.app = app_builder.build()
        self.chat_id = chat_id
        handlers = [
            ChatMemberHandler(self.greet_chat_members, ChatMemberHandler.CHAT_MEMBER),

            CommandHandler('start', self.start_handler),
            CommandHandler('who', self.who_handler),
            CommandHandler('8ball', self.magic_8_ball_handler),
            CommandHandler('balance', self.balance_handler),
            CommandHandler('pick', self.pick_handler),
            CommandHandler('boosters', self.boosters_handler),
            CommandHandler('level', self.level_handler),
            CommandHandler('rating', self.rating_handler),
            CommandHandler('anime', self.anime_handler),
            CommandHandler('img', self.image_handler),
            CommandHandler('slap', self.slap_handler),
            CommandHandler('cd', self.cd_handler),
            CommandHandler('shop', self.shop_handler),
            CallbackQueryHandler(self.buy_callback, pattern='^buy_'),
            CallbackQueryHandler(self.delete_user_callback, pattern='^DELETE_USER_'),
            ConversationHandler(
                entry_points=[CommandHandler('bj', self.bj_start_handler)],
                states={
                    BLACKJACK: [
                        CallbackQueryHandler(self.bj_hit_handler, pattern='^hit$'),
                        CallbackQueryHandler(self.bj_stand_handler, pattern='^stand$')
                    ]
                },
                fallbacks=[CommandHandler('start', self.bj_start_handler)],
                per_message=True
            ),
            ConversationHandler(
                entry_points=[CommandHandler('create_giveaway', self.create_giveaway_handler)],
                states={
                    SET_TYPE: [CallbackQueryHandler(self.set_giveaway_type)],
                    SET_COINS_AMOUNT: [MessageHandler(filters.TEXT, self.set_giveaway_coins_amount)],
                    SET_ITEM: [MessageHandler(filters.TEXT, self.set_giveaway_item)],
                    SET_AMOUNT: [MessageHandler(filters.TEXT, self.set_giveaway_item_amount)],
                    SET_END_DATETIME_OR_ADD_ITEM: [CallbackQueryHandler(self.set_end_datetime_or_add_item)],
                    SET_WINNERS_AMOUNT: [MessageHandler(filters.TEXT, self.set_giveaway_winners_amount)],

                    SET_END_DATETIME: [MessageHandler(filters.TEXT, self.set_giveaway_end_datetime)],
                    SET_DESCRIPTION: [MessageHandler(filters.TEXT, self.set_giveaway_description)],
                    SET_PHOTO: [MessageHandler(filters.PHOTO, self.set_giveaway_photo)],
                    REVIEW: [CallbackQueryHandler(self.review_giveaway, pattern='CONFIRM')],
                },
                fallbacks=[CommandHandler('cancel_giveaway', self.cancel_giveaway_handler),
                           CallbackQueryHandler(self.cancel_giveaway_handler, pattern='CANCEL')],
            ),
            CallbackQueryHandler(self.participate_callback, pattern="GIVEAWAY_PARTICIPATE_"),

            MessageHandler(
                filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED & ~filters.UpdateType.EDITED_MESSAGE &
                ~filters.ChatType.PRIVATE,
                self.text_handler),

        ]
        for handler in handlers:
            self.app.add_handler(handler)

    def start(self):
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
        if cooldown_expired(user_id, action_id) is True:
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
        cooldown = cooldown_expired(user_id, action_id)

        if cooldown is True:
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            all_users = UserCRUD.get_all_users()
            who_choice = random.choice(all_users)
            who_choice_mention = User(who_choice.user_id, who_choice.user_nickname, False).mention_markdown_v2()
            bot_message = who_choice_mention
            await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            print(f"You should wait {cooldown} seconds.")
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
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            text = magic_8_ball_phrase()
            text = escape_markdown(text, 2)
            bot_message = f"||{text}||"
            await update.message.reply_text(text=bot_message, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            print(f"You should wait {cooldown} seconds.")
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
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:

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
            print(f"You should wait {cooldown} seconds.")
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
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:
            UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

            users = UserLevelCRUD.get_top_users()
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
            print(f"You should wait {cooldown} seconds.")
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
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:
            if UserCRUD.pay_coins(user_id, ANIME_PRICE):
                UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

                await update.message.reply_photo(photo=choose_random_anime_image(), parse_mode=ParseMode.MARKDOWN_V2)
        else:
            print(f"You should wait {cooldown} seconds.")
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def image_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /img

        :param update:
        :param context:
        """
        user_id = update.message.from_user.id
        action_id = 8
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:
            if UserCRUD.pay_coins(user_id, IMG_PRICE):
                UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)

                await update.message.reply_photo(photo=choose_random_image(), has_spoiler=True)
        else:
            print(f"You should wait {cooldown} seconds.")
            context.job_queue.run_once(self.delete_messages, 1, data=[update.message])

    @auth_user
    async def slap_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /slap

        :param update:
        :param context:
        """
        await update.message.delete()
        user_name_mention = None
        mentioned_user = update.message.parse_entities(types=["mention"])
        if mentioned_user:
            user_name = next(iter(mentioned_user.values()), None)
            user_id = UserCRUD.get_user_id_by_username(user_name[1:])
            if user_id:
                user_nickname = UserCRUD.get_user_by_id(user_id).user_nickname
                user_name_mention = User(user_id, user_nickname, False).mention_html()
        if user_name_mention:
            await self.app.bot.send_animation(chat_id=self.chat_id, animation=choose_random_slap_gif(),
                                              caption=user_name_mention,
                                              parse_mode=ParseMode.HTML)

        elif update.message.reply_to_message:
            reply_to_msg_id = update.message.reply_to_message.message_id
            await update.message.reply_animation(animation=choose_random_slap_gif(),
                                                 reply_to_message_id=reply_to_msg_id,
                                                 parse_mode=ParseMode.HTML)
        else:
            await self.app.bot.send_animation(chat_id=self.chat_id, animation=choose_random_slap_gif())

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
                      f"Image: *{IMG_CD}s*\n" \
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
        if context.args and validate_bet(context.args[0], min_bet):
            bet = int(context.args[0]) * 100

        else:
            await update.message.reply_text(f'You must provide a bet of at least {int(min_bet / 100)} coins.')
            return ConversationHandler.END
        user_id = update.message.from_user.id
        action_id = 7
        cooldown = cooldown_expired(user_id, action_id)
        if cooldown is True:
            if UserCRUD.pay_coins(user_id, bet):
                UserActionCRUD.update_action_time(user_id=update.message.from_user.id, action_id=action_id)
                player_hand = deal_hand(deck)
                dealer_hand = deal_hand(deck)

                context.user_data['player_hand'] = player_hand
                context.user_data['dealer_hand'] = dealer_hand
                context.user_data['bet'] = bet

                keyboard = [
                    [InlineKeyboardButton('Hit', callback_data='hit'),
                     InlineKeyboardButton('Stand', callback_data='stand')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                message = await update.message.reply_text(f'Your hand: {player_hand}, total: {sum_hand(player_hand)}\n'
                                                          f'Dealer hand: {dealer_hand}, total: {sum_hand(dealer_hand)}\n'
                                                          f'Hit or Stand?',
                                                          reply_markup=reply_markup)
                context.user_data['message_id'] = message.message_id
                context.user_data['player_id'] = user_id

                return BLACKJACK
            else:
                await update.message.reply_text('You do not have enough coins for that bet.')
                return ConversationHandler.END
        else:
            await update.message.reply_text(f'wait {cooldown} sec')
            return ConversationHandler.END

    @auth_user
    async def bj_hit_handler(self, update: Update, context: CallbackContext) -> int:
        """
        handler for black jack hit callback

        :param update:
        :param context:
        """
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
                UserCRUD.add_coins(context.user_data['player_id'], context.user_data['bet'] * 2)
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
        """
        handler for black jack stand callback

        :param update:
        :param context:
        """
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
                UserCRUD.add_coins(context.user_data['player_id'], context.user_data['bet'] * 2)
            elif sum_hand(dealer_hand) < sum_hand(player_hand):
                await context.bot.edit_message_text(chat_id=update.effective_chat.id,
                                                    message_id=context.user_data['message_id'],
                                                    text=f'Your hand: {player_hand}, '
                                                         f'total: {sum_hand(player_hand)}\n'
                                                         f'Dealer\'s hand: {dealer_hand}, '
                                                         f'total: {sum_hand(dealer_hand)}\n'
                                                         f'You win!')
                UserCRUD.add_coins(context.user_data['player_id'], context.user_data['bet'] * 2)
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
                UserCRUD.add_coins(context.user_data['player_id'], context.user_data['bet'])

            return ConversationHandler.END

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ SHOP ~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    async def generate_shop_message(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
        user_balance = UserCRUD.get_user_balance(user_id)

        keyboard = []
        user_nickname = UserCRUD.get_user_by_id(user_id).user_nickname
        shop_text = f'{user_nickname}, welcome to the Shop!\n\n'
        row = []
        buttons_per_row = 3

        for i, (item_key, item_details) in enumerate(SHOP_ITEMS.items()):
            if i % buttons_per_row == 0 and row:
                keyboard.append(row)
                row = []
            if isinstance(item_details, ShopItemBoosterMSG) or isinstance(item_details, ShopItemBoosterPerMin):
                booster_count = UsersBoostersCRUD.get_booster_count(user_id, item_details.booster_id)
                shop_text += f"{i + 1}. " + \
                             f"{item_details.name} - {item_details.calculate_price(booster_count) / 100} 💵\n" \
                             f"\t\t\t{item_details.display_info(amount=item_details.bonus_amount, count=booster_count)}\n"
            else:
                shop_text += f"{i + 1}. " + item_details.display_info() + "\n"

            row.append(InlineKeyboardButton(str(i + 1), callback_data=f"buy_{item_key}"))

        if row:
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)
        shop_text += f"\nYour balance: {user_balance / 100} coins"

        return shop_text, reply_markup

    @auth_user
    async def shop_handler(self, update: Update, context: CallbackContext) -> None:
        """
        handler for /shop

        :param update:
        :param context:
        """
        shop_message, reply_markup = await self.generate_shop_message(update.message.from_user.id)
        await update.message.reply_text(shop_message, reply_markup=reply_markup)
        context.user_data['shop_user_id'] = update.message.from_user.id

    async def buy_callback(self, update: Update, context: CallbackContext) -> None:
        """
        handler for buy_item callback

        :param update:
        :param context:
        """
        user_id = update.callback_query.from_user.id
        if 'shop_user_id' in context.user_data and \
                context.user_data['shop_user_id'] == user_id:
            item_id = update.callback_query.data.split('_')[1]
            if item_id not in SHOP_ITEMS:
                await update.callback_query.answer("Invalid item!")
                return

            user_balance = UserCRUD.get_user_balance(user_id)

            if isinstance(SHOP_ITEMS[item_id], ShopItemBoosterMSG) or isinstance(SHOP_ITEMS[item_id],
                                                                                 ShopItemBoosterPerMin):
                booster_count = UsersBoostersCRUD.get_booster_count(user_id, SHOP_ITEMS[item_id].booster_id)
                price = SHOP_ITEMS[item_id].calculate_price(booster_count)
            else:
                price = SHOP_ITEMS[item_id].calculate_price()

            if user_balance < price:
                await update.callback_query.answer("You don't have enough coins!")
                return

            logger.debug(f"BUY {update.callback_query.from_user.id} {item_id} {price}")
            if UserCRUD.pay_coins(
                    user_id, price):
                if isinstance(SHOP_ITEMS[item_id], ShopItemBoosterMSG) or isinstance(SHOP_ITEMS[item_id],
                                                                                     ShopItemBoosterPerMin):
                    UsersBoostersCRUD.increment_or_create(user_id, SHOP_ITEMS[item_id].booster_id)
                else:
                    pass

            shop_message, reply_markup = await self.generate_shop_message(update.callback_query.from_user.id)
            await update.callback_query.edit_message_text(shop_message, reply_markup=reply_markup)

            await update.callback_query.answer(f"You've successfully purchased {SHOP_ITEMS[item_id].name}!")
        else:
            await update.callback_query.answer("You're not authorized to interact with this menu!")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ GIVEAWAY ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def create_giveaway_handler(self, update: Update, context: CallbackContext) -> None:
        if update.effective_chat.id in ADMINS:
            user = update.message.from_user
            context.user_data['user'] = user
            await update.message.delete()

            keyboard = [
                [InlineKeyboardButton("COINS", callback_data="COINS"),
                 InlineKeyboardButton("ELSE", callback_data="ELSE")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = await update.message.reply_text(
                "Let's create a giveaway! Please choose the type of giveaway:",
                reply_markup=reply_markup,
            )
            context.user_data['bot_message'] = message

            return SET_TYPE

    async def set_giveaway_type(self, update: Update, context):
        query = update.callback_query
        user_choice = query.data

        context.user_data['giveaway_type'] = user_choice
        if user_choice == 'COINS':
            await query.message.edit_text(
                f'You chose {user_choice}. Now, please enter the number of COINS for the giveaway '
                f'({int(min_giveaway_coins / 100)} - {int(max_giveaway_coins / 100)}):'
            )
            return SET_COINS_AMOUNT
        elif user_choice == 'ELSE':
            await query.message.edit_text(
                f'You chose {user_choice}. Write item.')
            context.user_data['gifts'] = []
            return SET_ITEM

    async def set_giveaway_coins_amount(self, update: Update, context):
        amount = update.message.text
        await update.message.delete()
        if validate_coins_amount(amount):
            context.user_data['giveaway_coins_amount'] = amount
            bot_message = context.user_data['bot_message']
            await bot_message.edit_text(
                "You've set the giveaway coins amount. Please enter the number of winners:")
            return SET_WINNERS_AMOUNT

    async def set_giveaway_winners_amount(self, update: Update, context: CallbackContext):
        winners_amount_text = update.message.text
        await update.message.delete()
        bot_message = context.user_data['bot_message']
        try:
            winners_amount = int(winners_amount_text)
            if winners_amount <= 0:
                raise ValueError
            giveaway_type = context.user_data['giveaway_type']
            if giveaway_type == 'COINS':
                gifts = [{"name": "coins", "amount": context.user_data['giveaway_coins_amount']}] * winners_amount
                context.user_data['gifts'] = gifts
            await bot_message.edit_text("Now, let's set the giveaway end datetime in format:\n"
                                        "- in 3 hours: '3h'\n"
                                        "- in 1 day: '1d'\n"
                                        "- or exact time: '12:10 10.10.2023'")
            return SET_END_DATETIME

        except ValueError:
            await bot_message.edit_text("Invalid input. Please enter a positive integer for the number of winners.")
            return SET_WINNERS_AMOUNT

    async def set_giveaway_item(self, update: Update, context: CallbackContext):
        bot_message = context.user_data['bot_message']
        item = update.message.text
        await update.message.delete()
        context.user_data['gifts'].append({'name': item})
        await bot_message.edit_text(f"You added item: {item}\nNow, please enter the amount:")
        return SET_AMOUNT

    async def set_giveaway_item_amount(self, update: Update, context: CallbackContext):
        amount = update.message.text
        await update.message.delete()
        bot_message = context.user_data['bot_message']
        if amount.isdigit():
            context.user_data['gifts'][-1]['amount'] = int(amount)
        else:
            return SET_AMOUNT
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Add one more item", callback_data='ADD_GIVEAWAY_ITEM')],
             [InlineKeyboardButton("Next step", callback_data='SET_END_DATETIME')]])
        await bot_message.edit_text(
            f"You added item: {context.user_data['gifts'][-1]['name']}\n"
            f"Amount: {context.user_data['gifts'][-1]['amount']}",
            reply_markup=reply_markup)
        return SET_END_DATETIME_OR_ADD_ITEM

    async def set_end_datetime_or_add_item(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if query:
            if query.data == 'ADD_GIVEAWAY_ITEM':
                await query.message.edit_text(f' Write item.')
                return SET_ITEM
            elif query.data == 'SET_END_DATETIME':
                await query.message.edit_text("Now, let's set the giveaway end datetime in format:\n"
                                              "- in 3 hours: '3h'\n"
                                              "- in 1 day: '1d'\n"
                                              "- or exact time: '12:10 10.10.2023'")
                return SET_END_DATETIME

    async def set_giveaway_end_datetime(self, update: Update, context: CallbackContext):
        datetime_user_str = update.message.text
        context.user_data['end_datetime'] = extract_datetime(datetime_user_str)
        await update.message.delete()

        bot_message = context.user_data['bot_message']
        await bot_message.edit_text("Now send photo")

        return SET_PHOTO

    async def set_giveaway_photo(self, update: Update, context: CallbackContext):
        context.user_data['giveaway_photo'] = update.message.photo[-1].file_id
        await update.message.delete()
        bot_message = context.user_data['bot_message']
        await bot_message.edit_text("Now provide description")
        return SET_DESCRIPTION

    async def set_giveaway_description(self, update: Update, context: CallbackContext):
        user_description = update.message.text
        context.user_data['description'] = user_description
        await update.message.delete()

        bot_message = context.user_data['bot_message']
        gifts = context.user_data['gifts']
        end_datetime = context.user_data['end_datetime']
        giveaway_type = context.user_data['giveaway_type']
        giveaway_description = context.user_data['description']

        keyboard = [
            [
                InlineKeyboardButton("✅", callback_data="CONFIRM"),
                InlineKeyboardButton("❌", callback_data="CANCEL"),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"Great! Here's a summary of your giveaway:\n" \
               f"Type: {giveaway_type}\n" \
               f"Gifts: {gifts}\n" \
               f"Description: {giveaway_description}\n" \
               f"End datetime: {end_datetime}\n"
        await bot_message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return REVIEW

    async def review_giveaway(self, update: Update, context):
        giveaway_type = context.user_data['giveaway_type']
        gifts = context.user_data['gifts']
        end_datetime = context.user_data['end_datetime']
        giveaway_description = context.user_data['description']

        created_giveaway_id = GiveawayCRUD.create_giveaway(giveaway_type=giveaway_type,
                                                           description=giveaway_description, end_datetime=end_datetime,
                                                           gifts=gifts)

        bot_message = context.user_data['bot_message']
        await bot_message.edit_text("Congratulations! Your giveaway has been created and saved.")
        keyboard = [
            [InlineKeyboardButton(f"Participate", callback_data=f"GIVEAWAY_PARTICIPATE_{created_giveaway_id}"), ]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        end_datetime_str = end_datetime.strftime("%B %d, %Y at %I:%M %p")
        text = (
            "<b>🎉 New Giveaway Alert! 🎉</b>\n\n"
            "We're excited to announce a new giveaway with amazing prizes! 🎁\n\n"
            f"<b>Description:</b>\n{giveaway_description}\n\n"
            "<b>Prizes:</b>\n"
        )

        for idx, gift in enumerate(gifts, start=1):
            gift_name = gift['name']
            gift_amount = gift['amount']
            text += f"{idx}. {gift_name} ({gift_amount}x)\n"

        text += (
            f"\n\n<b>End Date and Time:</b>\n{end_datetime_str}\n\n"
            "\nParticipate now for a chance to win these fantastic prizes! 🎉\n"
            "Good luck to everyone! 🍀\n\n"
        )
        giveaway_message = await self.app.bot.send_photo(chat_id=self.chat_id,
                                                         photo=context.user_data['giveaway_photo'], caption=text,
                                                         reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        GiveawayCRUD.set_message_id(giveaway_id=created_giveaway_id, message_id=giveaway_message.message_id)
        wait_for_giveaway_ending_thread = threading.Thread(target=wait_for_giveaway_ending,
                                                           args=(created_giveaway_id, self,),
                                                           daemon=True)
        wait_for_giveaway_ending_thread.start()
        return ConversationHandler.END

    async def cancel_giveaway_handler(self, update: Update, context):
        bot_message = context.user_data['bot_message']
        await bot_message.edit_text('Giveaway creation has been canceled.')
        return ConversationHandler.END

    async def participate_callback(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id

        callback_data = update.callback_query.data
        giveaway_id = int(callback_data.split("_")[-1])

        end_datetime = GiveawayCRUD.get_giveaway_end_datetime(giveaway_id)
        if end_datetime and datetime.datetime.now().timestamp() > end_datetime:
            await update.callback_query.answer("Sorry, the giveaway has ended.")
            return

        if GiveawayCRUD.has_user_participated(user_id, giveaway_id):
            await update.callback_query.answer("You have already participated in this giveaway.")

        else:
            GiveawayCRUD.add_participant(user_id, giveaway_id)
            await update.callback_query.answer("You have successfully participated in the giveaway")
            participant_count = GiveawayCRUD.get_participant_count(giveaway_id)
            keyboard = [
                [InlineKeyboardButton(f"Participate ({participant_count})",
                                      callback_data=f"GIVEAWAY_PARTICIPATE_{giveaway_id}"), ]]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.edit_reply_markup(reply_markup)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ ADDITIONAL FUNC ~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def bot_send_message(self, text: str, reply_message: int = None,
                               parse_mode: ParseMode = ParseMode.HTML) -> None:
        """
         send message with provided text


         :param text:
         :param reply_message:
         :param parse_mode:
         """

        await self.app.bot.send_message(chat_id=self.chat_id, text=text,
                                        reply_to_message_id=reply_message, parse_mode=parse_mode)

    async def bot_edit_message_text(self, chat_id: int, message_id: int, text: str,
                                    parse_mode: ParseMode = None) -> None:
        """
        send message with provided text


        :param chat_id:
        :param message_id:
        :param text:
        :param parse_mode:
        """

        await self.app.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)

    async def bot_edit_message_caption(self, chat_id: int, message_id: int, text: str,
                                       parse_mode: ParseMode = None) -> None:
        """
        send message with provided text
        """
        await self.app.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text,
                                                parse_mode=parse_mode)

    async def bot_send_photo(self, photo_url: str, text: str) -> None:
        """
        send photo by provided url

        :param photo_url:
        :param text:
        """
        photo = [InputMediaPhoto(photo_url, caption=text, parse_mode=ParseMode.MARKDOWN_V2)]
        await self.app.bot.send_media_group(chat_id=self.chat_id, media=photo)

    async def bot_send_media_group(self, media_urls: list, text: str) -> None:
        """
        send media group by provided list of urls

        :param media_urls:
        :param text:
        """
        media = [InputMediaPhoto(media_urls[0], caption=text, parse_mode=ParseMode.MARKDOWN_V2)]
        for url in media_urls[1:]:
            media.append(InputMediaPhoto(url))
        await self.app.bot.send_media_group(chat_id=self.chat_id, media=media)

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

    async def delete_messages(self, context: CallbackContext) -> None:
        """
        delete msg from context
        :param context:
        """
        messages = context.job.data
        logger.debug(messages)
        for msg in messages:
            try:
                await msg.delete()
            except Exception as e:
                logger.error(e)

    @staticmethod
    def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
        """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
        of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
        the status didn't change.
        """
        status_change = chat_member_update.difference().get("status")
        old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

        if status_change is None:
            return None

        old_status, new_status = status_change
        was_member = old_status in [
            ChatMember.MEMBER,
            ChatMember.OWNER,
            ChatMember.ADMINISTRATOR,
        ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
        is_member = new_status in [
            ChatMember.MEMBER,
            ChatMember.OWNER,
            ChatMember.ADMINISTRATOR,
        ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

        return was_member, is_member

    async def greet_chat_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Greets new users in chats and announces when someone leaves"""
        if update.effective_chat.id == self.chat_id:
            result = self.extract_status_change(update.chat_member)
            if result is None:
                return

            was_member, is_member = result

            cause_user_id = update.chat_member.from_user.id
            user_nickname = UserCRUD.get_user_by_id(cause_user_id).user_nickname
            cause_user_name = User(cause_user_id, user_nickname, False).mention_html()

            member_id = update.chat_member.new_chat_member.user.id

            if not was_member and is_member:

                member_user_name = update.chat_member.new_chat_member.user.name[1:]
                member_nickname = update.chat_member.new_chat_member.user.full_name

                member_mention = update.chat_member.new_chat_member.user.mention_html()
                if update.chat_member.from_user == update.chat_member.new_chat_member.user:
                    await update.effective_chat.send_message(f"{member_mention} has joined. Welcome!",
                                                             parse_mode=ParseMode.HTML)
                else:
                    await update.effective_chat.send_message(
                        f"{member_mention} was added by {cause_user_name}. Welcome!",
                        parse_mode=ParseMode.HTML)
                UserCRUD.create_user(member_id, member_user_name, member_nickname)
            elif was_member and not is_member:
                user_nickname = UserCRUD.get_user_by_id(member_id).user_nickname
                member_user_name = User(member_id, user_nickname, False).mention_html()
                if update.chat_member.from_user == update.chat_member.new_chat_member.user:
                    text = f"{member_user_name} has left :("
                else:
                    text = f"{member_user_name} is no longer with us. Thanks a lot, {cause_user_name}..."
                keyboard = [
                    [InlineKeyboardButton(f"🚷",
                                          callback_data=f"DELETE_USER_{member_id}"), ]]

                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.effective_chat.send_message(text, reply_markup=reply_markup,
                                                         parse_mode=ParseMode.HTML)

    @admin_only
    async def delete_user_callback(self, update: Update, context: CallbackContext):
        callback_data = update.callback_query.data
        user_id = int(callback_data.split("_")[-1])
        UserCRUD.delete_user(user_id)
        await update.callback_query.message.edit_reply_markup(reply_markup=None)


def announce_winners(tg_bot: TelegramBot, winners: list, message_id: int, participants_count: int):
    message = "🎉 Giveaway Ended 🎉\n\n"
    winners_message = ''
    if participants_count > 0:
        if winners:
            message += f"Thank you to all {participants_count} participants for joining our giveaway! 🙌\n\n"
            winners_message += "Winners Announcement 🏆:\n"

            for idx, winner_info in enumerate(winners, start=1):
                winner_id = winner_info['winner']
                gift_info = winner_info['gift']
                gift_name = gift_info['name']
                gift_amount = gift_info['amount']
                user = UserCRUD.get_user_by_id(winner_id)
                user_mention = User(winner_id, user.user_nickname, is_bot=False).mention_html()
                winners_message += f"{idx}. {user_mention} wins {gift_amount}x {gift_name}\n"

            winners_message += "\nCongratulations to our lucky winners! 🎉\n\n"
            winners_message += "Stay tuned for more exciting giveaways in the future. " \
                               "Don't miss your chance to win amazing prizes! " \
                               "🎁\n\n"
        else:
            winners_message += "Unfortunately, there are no winners this time. 😔 " \
                               "Don't worry, we'll have more giveaways in the " \
                               "future. Stay tuned! 🎁\n\n"
    else:
        winners_message += "There were no participants in this giveaway. 😢 We'll try again in our next giveaway! 🎁\n\n"
    logger.debug(winners_message)
    message += winners_message
    tg_bot.loop.create_task(tg_bot.bot_edit_message_caption(tg_bot.chat_id, message_id, message, ParseMode.HTML))
    mention_text = f"Giveaway Results 👀\n"
    mention_text += winners_message
    tg_bot.loop.create_task(tg_bot.bot_send_message(mention_text, message_id, ParseMode.HTML))


def wait_for_giveaway_ending(giveaway_id, tg_bot: TelegramBot):
    end_datetime = GiveawayCRUD.get_giveaway_end_datetime(giveaway_id)
    now = datetime.datetime.now().timestamp()
    remaining_time = end_datetime - now
    logger.debug(f'waiting for giv {giveaway_id}, remaining_time: {remaining_time}')
    if remaining_time > 0:
        time.sleep(remaining_time)
    message_id = GiveawayCRUD.get_giveaway_message_id(giveaway_id)
    participants_count = GiveawayCRUD.get_participant_count(giveaway_id)
    winners = GiveawayCRUD.select_giveaway_winners(giveaway_id)
    announce_winners(tg_bot, winners, message_id, participants_count)


def start_giveaway_threads(tg_bot: TelegramBot):
    giveaways = GiveawayCRUD.get_all_giveaways()
    for giveaway in giveaways:
        thread = threading.Thread(target=wait_for_giveaway_ending, args=(giveaway.id, tg_bot,), daemon=True)
        thread.start()


def main():
    tg_bot = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)

    setup_database()
    start_giveaway_threads(tg_bot)
    bonus_per_min_thread = threading.Thread(target=add_coins_per_min, daemon=True)
    bonus_per_min_thread.start()

    # egs_free_games = EGSFreeGames()
    # check_epic_thread = threading.Thread(target=egs_free_games.check_epic_free_games_loop, args=(tg_bot,), daemon=True)
    # check_epic_thread.start()

    steam_events = SteamEvents()
    check_steam_events_thread = threading.Thread(target=steam_events.check_steam_events_loop, args=(tg_bot,),
                                                 daemon=True)
    check_steam_events_thread.start()
    tg_bot.start()


if __name__ == '__main__':
    main()
