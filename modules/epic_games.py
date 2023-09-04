import json
import os
import time
import datetime

import requests.exceptions
from epicstore_api import EpicGamesStoreAPI
from telegram.helpers import escape_markdown
from config import logger


class EGSFreeGames:
    def __init__(self, filename=None):
        if filename:
            self.filename = filename
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.filename = os.path.join(current_dir, "free_games.json")

    @staticmethod
    def get_free_games() -> dict:
        api = EpicGamesStoreAPI()
        try_counter = 0
        while try_counter < 5:
            try:
                free_games = api.get_free_games()
                return free_games
            except requests.exceptions.ConnectionError:
                time.sleep(10)
                try_counter += 1
            except Exception as e:
                logger.error(e)
        return {}

    @staticmethod
    def format_response(free_games) -> dict:
        free_games_data = {"current": [], "future": []}
        for i in free_games['data']['Catalog']['searchStore']['elements']:
            if i['promotions']:
                url = "https://store.epicgames.com/en-US/p/" + i['catalogNs']['mappings'][0]['pageSlug']

                if i['promotions']['promotionalOffers']:

                    start_date = i['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['startDate']
                    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    end_date = i['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['endDate']
                    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if end_date > datetime.datetime.now() > start_date and \
                            i['price']['totalPrice']['discountPrice'] == 0:
                        img_url = [img for img in i['keyImages'] if img['type'] == 'OfferImageTall'][0]['url']
                        game = {'title': i['title'], 'url': url, 'start_date': int(start_date.timestamp()),
                                'end_date': int(end_date.timestamp()),
                                'img_url': img_url}
                        free_games_data["current"].append(game)
                elif i['promotions']['upcomingPromotionalOffers']:

                    start_date = i['promotions']['upcomingPromotionalOffers'][0]['promotionalOffers'][0]['startDate']
                    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if datetime.datetime.now() < start_date:
                        game = {'title': i['title'], 'url': url, 'start_date': int(start_date.timestamp())}
                        free_games_data["future"].append(game)
        return free_games_data

    def save_to_file(self, games: dict):
        with open(self.filename, 'w') as f:
            json.dump(games, f, indent=4)

    def read_from_file(self) -> dict:
        if not os.path.exists(self.filename):
            return {"current": [], "future": []}
        with open(self.filename, 'r') as f:
            return json.load(f)

    @staticmethod
    def print_new_free_games(new_free_games, tg_bot):
        current_games = new_free_games["current"]
        future_games = new_free_games["future"]
        message = f'🎮 *Epic Games Free Games* 🎮:\n\n' + "\n".join(
            [f"🎁 [{escape_markdown(game['title'], 2)}]({game['url']}) 📅" + escape_markdown(
                f"({datetime.datetime.fromtimestamp(game['start_date']).strftime('%d.%m')}-"
                f"{datetime.datetime.fromtimestamp(game['end_date']).strftime('%d.%m')})", 2) for game in
             current_games])

        if future_games:
            message += f'\n\n🔮 *Future Games* 🔮:\n\n' + "\n".join(
                [f"🔜 {escape_markdown(game['title'], 2)} 📅" + escape_markdown(
                    f"({datetime.datetime.fromtimestamp(game['start_date']).strftime('%d.%m')})", 2) for game in
                 future_games])

        photos = [i['img_url'] for i in current_games]
        data = {'message': message, 'photos': photos}

        if len(data['photos']) == 1:
            tg_bot.loop.create_task(tg_bot.bot_send_photo(photo_url=data['photos'][0], text=data['message']))
        else:
            tg_bot.loop.create_task(tg_bot.bot_send_media_group(media_urls=data['photos'], text=data['message']))

    def check_epic_free_games_loop(self, tg_bot, num_iterations=None, ):
        iteration = 0
        while True:
            current_time = datetime.datetime.now().time()
            logger.debug(f"CHECK EPIC | {current_time}")
            free_games = self.get_free_games()
            if free_games:
                formatted_free_games = self.format_response(free_games)
                saved_free_games = self.read_from_file()
                if formatted_free_games["current"] != saved_free_games["current"]:
                    self.print_new_free_games(formatted_free_games, tg_bot)
                    self.save_to_file(formatted_free_games)
            if datetime.datetime.strptime("17:30", "%H:%M").time() <= current_time <= datetime.datetime.strptime(
                    "18:30", "%H:%M").time():
                time.sleep(300)
            else:
                time.sleep(21600)
            if num_iterations is not None:
                iteration += 1
                if iteration >= num_iterations:
                    break
