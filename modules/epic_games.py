import json
import os
import time
from datetime import datetime
from epicstore_api import EpicGamesStoreAPI
from telegram.helpers import escape_markdown

from config import message_queue, logger

FILENAME = "free_games.json"


def get_free_games():
    api = EpicGamesStoreAPI()

    return api.get_free_games()


def save_to_file(games):
    with open(FILENAME, 'w') as file:
        json.dump(games, file)


def read_from_file():
    if not os.path.exists(FILENAME):
        return None
    with open(FILENAME, 'r') as file:
        return json.load(file)


def compare_and_notify(current_games, saved_games):
    games = list()
    for i in current_games['data']['Catalog']['searchStore']['elements']:

        if i['promotions']:
            url = "https://store.epicgames.com/en-US/p/" + i['catalogNs']['mappings'][0]['pageSlug']
            img_url = [img for img in i['keyImages'] if img['type'] == 'OfferImageTall'][0]['url']
            if i['promotions']['promotionalOffers']:

                start_date = i['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['startDate']
                effective_date = i['effectiveDate']
                effective_date = datetime.strptime(effective_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                end_date = i['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['endDate']
                end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                if end_date > datetime.now() > start_date == effective_date:
                    game = {'title': i['title'], 'url': url, 'start_date': int(start_date.timestamp()),
                            'end_date': int(end_date.timestamp()),
                            'img_url': img_url}
                    games.append(game)
            elif i['promotions']['upcomingPromotionalOffers']:

                start_date = i['promotions']['upcomingPromotionalOffers'][0]['promotionalOffers'][0]['startDate']
                start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                if datetime.now() < start_date:
                    game = {'title': i['title'], 'url': url, 'start_date': int(start_date.timestamp())}
                    games.append(game)

    if games != saved_games:
        cur_games = [i for i in games if i['start_date'] < datetime.now().timestamp() < i['end_date']]

        future_games = [i for i in games if datetime.now().timestamp() < i['start_date']]
        message = f'🎮 *Epic Games Free Games* 🎮:\n\n' + "\n".join(

            [f"🎁 [{escape_markdown(game['title'], 2)}]({game['url']}) 📅" + escape_markdown(
                f"({datetime.fromtimestamp(game['start_date']).strftime('%d.%m')}-"
                f"{datetime.fromtimestamp(game['end_date']).strftime('%d.%m')})", 2) for game in cur_games])

        if future_games:
            message += f'\n\n🔮 *Future Games* 🔮:\n\n' + "\n".join(
                [f"🔜 {escape_markdown(game['title'], 2)} 📅" + escape_markdown(
                    f"({datetime.fromtimestamp(game['start_date']).strftime('%d.%m')})", 2) for game in
                 future_games])
        photos = [i['img_url'] for i in cur_games]
        data = {'message': message, 'photos': photos}
        message_queue.put(data)
        save_to_file(games)


def check_and_notify():
    current_games = get_free_games()
    saved_games = read_from_file()
    compare_and_notify(current_games, saved_games)


def check_epic():
    while True:
        current_time = datetime.now().time()
        logger.debug(f"CHECK EPIC | {current_time}")
        if datetime.strptime("17:30", "%H:%M").time() <= current_time <= datetime.strptime("18:30", "%H:%M").time():
            check_and_notify()
            time.sleep(300)
        else:
            check_and_notify()
            time.sleep(21600)


if __name__ == "__main__":
    check_epic()
