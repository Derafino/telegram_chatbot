import asyncio
import random
import threading

from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler
from telegram.helpers import escape_markdown

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT, logger, ANIME_PRICE, MSG_CD, WHO_CD, BALL8_CD, PICK_CD, RATING_CD, \
    ANIME_CD, min_bet, message_queue
from db.crud import setup_database, UserCRUD, UserActionCRUD, UserLevelCRUD, UsersBoostersCRUD
from games.black_jack import sum_hand, deal_hand, deal_card, deck
from games.magic_8_ball import magic_8_ball_phrase
from methods import auth_user, chat_only, cooldown_expired, add_coins_per_min, calc_xp, validate_bet, rate_limited
from modules.anime import choose_random_anime_image
from modules.epic_games import check_epic
from modules.shop import SHOP_ITEMS, ShopItemBoosterMSG, ShopItemBoosterPerMin
from modules.steam_events import check_steam_events

BLACKJACK = 0
TEXT, IMAGE, IMAGE_WAITING, REGULARITY, DELAY, TIME = range(6)


class RateLimiter:
    def __init__(self, rate: int, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = asyncio.get_event_loop().time()

    async def acquire(self):
        while self.tokens <= 0:
            self._refill()
            if self.tokens <= 0:
                await asyncio.sleep(1)
        self.tokens -= 1

    def _refill(self):
        now = asyncio.get_event_loop().time()
        time_delta = now - self.last_refill

        new_tokens = time_delta * self.rate
        self.tokens = min(self.tokens + new_tokens, self.capacity)
        self.last_refill = now


class TelegramBot:
    def __init__(self, token, chat_id):

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.app = Application.builder().token(token).build()
        self.chat_id = chat_id
        self.rate_limiter = RateLimiter(rate=1, capacity=30)
        handlers = [
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
            CommandHandler('shop', self.shop_handler),
            CallbackQueryHandler(self.buy_callback, pattern='^buy_'),
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

            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED & ~filters.UpdateType.EDITED_MESSAGE,
                           self.text_handler)

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

                while not message_queue.empty():
                    data = message_queue.get()
                    if len(data['photos']) == 1:
                        await self.bot_send_photo(photo_url=data['photos'][0], text=data['message'])
                    else:
                        await self.bot_send_media_group(media_urls=data['photos'], text=data['message'])

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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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
    @rate_limited
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
                                                          f'Hit or Stand? ',
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    @rate_limited
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ ADDITIONAL FUNC ~~~~~~~~~~~~~~~~~~~~~~~~~~
    async def bot_send_message(self, text: str) -> None:
        """
         send message with provided text

         :param text:
         """
        await self.app.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)

    @rate_limited
    async def bot_send_photo(self, photo_url: str, text: str) -> None:
        """
        send photo by provided url

        :param photo_url:
        :param text:
        """
        photo = [InputMediaPhoto(photo_url, caption=text, parse_mode=ParseMode.MARKDOWN_V2)]
        await self.app.bot.send_media_group(chat_id=self.chat_id, media=photo)

    @rate_limited
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

    @staticmethod
    async def delete_messages(context: CallbackContext) -> None:
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


if __name__ == '__main__':
    setup_database()
    bonus_per_min_thread = threading.Thread(target=add_coins_per_min, daemon=True)
    bonus_per_min_thread.start()

    check_epic_thread = threading.Thread(target=check_epic, daemon=True)
    check_epic_thread.start()

    check_steam_events_thread = threading.Thread(target=check_steam_events, daemon=True)
    check_steam_events_thread.start()

    TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)
