import requests
import xml.etree.ElementTree as ET
import time
import json
import os

from telegram.helpers import escape_markdown


class SteamEvents:
    def __init__(self, filename=None):
        if filename:
            self.filename = filename
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.filename = os.path.join(current_dir, "steam_events.json")

    @staticmethod
    def get_last_events() -> bytes:
        url = "https://www.steamcardexchange.net/include/rss/events.xml"
        response = requests.get(url)
        if response.status_code == 200:
            return response.content

    @staticmethod
    def format_response(response_content) -> list[dict]:
        root = ET.fromstring(response_content)

        events = []
        for item in root.findall(".//item"):
            title = item.find("title").text.strip()
            link = item.find("link").text
            enclosure_url = item.find("enclosure").attrib["url"]
            events.append({
                "title": title,
                "link": link,
                "enclosure_url": enclosure_url
            })

        return events[:1]

    def save_to_file(self, events: list[dict]):
        with open(self.filename, 'w') as f:
            json.dump(events, f, indent=4)

    def read_from_file(self) -> list[dict]:
        if not os.path.exists(self.filename):
            return []
        with open(self.filename, 'r') as f:
            return json.load(f)

    @staticmethod
    def get_new_events(fetched_events: list[dict], saved_events: list[dict]) -> list[dict]:
        return [event for event in fetched_events if event not in saved_events]

    @staticmethod
    def print_new_events(new_events, tg_bot):
        for event in new_events:
            message = f"🚀 *{escape_markdown('New Steam Event!', 2)}* 🚀\n" \
                      f"🎮 *Title:* {escape_markdown(event['title'], 2)}\n" \
                      f"🔗 *Items:* [Click Here]({event['link']})"
            data = {'message': message, 'photos': [event['enclosure_url']]}
            tg_bot.loop.create_task(tg_bot.bot_send_photo(photo_url=data['photos'][0], text=data['message']))

    def check_steam_events_loop(self, tg_bot, num_iterations=None):
        iteration = 0
        while True:
            response_content = self.get_last_events()
            fetched_events = self.format_response(response_content)
            saved_events = self.read_from_file()
            if fetched_events != saved_events:
                new_events = self.get_new_events(fetched_events, saved_events)
                print(new_events)
                self.print_new_events(new_events, tg_bot)
                self.save_to_file(new_events)

            time.sleep(3600)

            if num_iterations is not None:
                iteration += 1
                if iteration >= num_iterations:
                    break
