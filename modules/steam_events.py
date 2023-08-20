import requests
import xml.etree.ElementTree as ET
import time
import json
import os

from telegram.helpers import escape_markdown
from config import message_queue

FILENAME = "steam_events.json"


def get_last_events() -> list[dict]:
    url = "https://www.steamcardexchange.net/include/rss/events.xml"
    response = requests.get(url)
    root = ET.fromstring(response.content)

    events = []
    for item in root.findall(".//item"):
        title = item.find("title").text
        link = item.find("link").text
        enclosure_url = item.find("enclosure").attrib["url"]
        events.append({
            "title": title,
            "link": link,
            "enclosure_url": enclosure_url
        })

    return events[:5]


def save_to_file(events: list[dict]):
    with open(FILENAME, 'w') as f:
        json.dump(events, f, indent=4)


def read_from_file() -> list[dict] | None:
    if not os.path.exists(FILENAME):
        return []
    with open(FILENAME, 'r') as f:
        return json.load(f)


def print_new_events(fetched_events: list[dict], saved_events: list):
    new_events = [event for event in fetched_events if event not in saved_events]
    for event in new_events:
        message = f"🚀 *{escape_markdown('New Steam Event!', 2)}* 🚀\n" \
                  f"🎮 *Title:* {escape_markdown(event['title'], 2)}\n" \
                  f"🔗 *Items:* [Click Here]({event['link']})"
        print(message)
        data = {'message': message, 'photos': [event['enclosure_url']]}
        message_queue.put(data)


def check_steam_events():
    while True:
        fetched_events = get_last_events()
        saved_events = read_from_file()

        if fetched_events != saved_events:
            print_new_events(fetched_events, saved_events)
            save_to_file(fetched_events)

        time.sleep(3600)


if __name__ == "__main__":
    check_steam_events()
