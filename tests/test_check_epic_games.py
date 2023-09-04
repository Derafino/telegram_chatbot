import datetime
import time

import pytest
import requests
from epicstore_api import EpicGamesStoreAPI
from telegram.helpers import escape_markdown

from config import message_queue
from modules.epic_games import EGSFreeGames

test_free_games_data = {
    "current": [
        {
            "title": "Mock Game 1",
            "url": "https://mockgame1.com",
            "start_date": "2023-08-01T15:00:01Z",
            "end_date": "2023-09-01T15:00:01Z",
            "img_url": "https://mockgame1.com/image.jpg"
        }
    ],
    "future":
        [
            {
                "title": "Mock Game 2",
                "url": "https://mockgame2.com",
                "start_date": "2023-09-01T15:00:01Z",
                "img_url": "https://mockgame2.com/image.jpg"
            }
        ]
}


def test_format_response():
    raw_data = {
        'data': {
            'Catalog': {
                'searchStore': {
                    'elements': [
                        {
                            'title': 'FreeGame1',
                            'promotions': {
                                'promotionalOffers': [
                                    {
                                        'promotionalOffers': [
                                            {
                                                'startDate': '1990-08-31T17:00:00.000Z',
                                                'endDate': '2030-09-15T17:00:00.000Z'
                                            }
                                        ]
                                    }
                                ],
                                'upcomingPromotionalOffers': []
                            },
                            'price': {
                                'totalPrice': {
                                    'discountPrice': 0
                                }
                            },
                            'catalogNs': {
                                'mappings': [
                                    {
                                        'pageSlug': 'freegame1-slug'
                                    }
                                ]
                            },
                            'keyImages': [
                                {
                                    'type': 'OfferImageTall',
                                    'url': 'https://example.com/freegame1_image.jpg'
                                }
                            ]
                        },
                        {
                            'title': 'FreeGame2',
                            'promotions': {
                                'promotionalOffers': [],
                                'upcomingPromotionalOffers': [
                                    {
                                        'promotionalOffers': [
                                            {
                                                'startDate': '2030-09-05T17:00:00.000Z',
                                            }
                                        ]
                                    }
                                ]
                            },
                            'catalogNs': {
                                'mappings': [
                                    {
                                        'pageSlug': 'freegame2-slug'
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
    }

    egs = EGSFreeGames()
    result = egs.format_response(raw_data)
    expected_result = {
        "current": [
            {
                "title": "FreeGame1",
                "url": "https://store.epicgames.com/en-US/p/freegame1-slug",
                "start_date": 652111200,
                "end_date": 1915711200,
                "img_url": "https://example.com/freegame1_image.jpg"
            }
        ],
        "future":
            [
                {
                    "title": "FreeGame2",
                    "url": "https://store.epicgames.com/en-US/p/freegame2-slug",
                    "start_date": 1914847200,
                }
            ]
    }
    assert result == expected_result


class MockEpicGamesStoreAPI:
    @staticmethod
    def get_free_games():
        return test_free_games_data


def test_get_free_games_success(monkeypatch):
    def mock_get_free_games(*args, **kwargs):
        return test_free_games_data

    monkeypatch.setattr(EpicGamesStoreAPI, "get_free_games", mock_get_free_games)
    egs = EGSFreeGames()
    result = egs.get_free_games()
    assert result == test_free_games_data


def test_get_free_games_fail(monkeypatch):
    def mock_raise_connection_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Test connection error")

    monkeypatch.setattr(EpicGamesStoreAPI, "get_free_games", mock_raise_connection_error)
    egs = EGSFreeGames()
    result = egs.get_free_games()
    assert result == {}


def test_save_and_read_from_file(tmpdir):
    egs = EGSFreeGames(filename=tmpdir.join("test_file.json"))

    egs.save_to_file(test_free_games_data)
    read_data = egs.read_from_file()

    assert read_data == test_free_games_data


def test_get_new_games():
    fetched_games = {
        "current": [{"title": "Game 1", "link": "link1", "enclosure_url": "url1", "end_date": "2023-09-01T15:00:01Z"},
                    {"title": "Game 2", "link": "link2", "enclosure_url": "url2", "end_date": "2023-09-02T15:00:01Z"},
                    {"title": "Game 3", "link": "link3", "enclosure_url": "url3", "end_date": "2023-09-03T15:00:01Z"}],
        "future": []
    }
    saved_games = {
        "current": [{"title": "Game 1", "link": "link1", "enclosure_url": "url1", "end_date": "2023-09-01T15:00:01Z"}],
        "future": [{"title": "Game 2", "link": "link2", "enclosure_url": "url2", "end_date": "2023-09-02T15:00:01Z"}]
    }

    assert fetched_games["current"] != saved_games["current"]


def test_print_new_games(monkeypatch):
    mock_put_data = {}

    def mock_put(data):
        mock_put_data['called'] = True
        mock_put_data['data'] = data

    monkeypatch.setattr(message_queue, "put", mock_put)

    new_games = {

        "current": [
            {
                "title": "New Game 1",
                "url": "https://new_game1.com",
                "start_date": 1693483200,
                "end_date": 1694088000,
                "img_url": "https://new_game1.com/image.jpg"
            }
        ],
        "future": [{
            "title": "New Game 2",
            "url": "https://new_game2.com",
            "start_date": 1693483200,
            "img_url": "https://new_game2.com/image.jpg"
        }]
    }

    EGSFreeGames.print_new_free_games(new_games)

    expected_message = f"🎮 *Epic Games Free Games* 🎮:\n\n" \
                       f"🎁 [{escape_markdown('New Game 1', 2)}](https://new_game1.com) 📅" + \
                       escape_markdown(f"({datetime.datetime.fromtimestamp(1693483200).strftime('%d.%m')}-"
                                       f"{datetime.datetime.fromtimestamp(1694088000).strftime('%d.%m')})", 2)
    expected_message += "\n\n🔮 *Future Games* 🔮:\n\n" \
                        "🔜 New Game 2 📅" + \
                        escape_markdown(f"({datetime.datetime.fromtimestamp(1693483200).strftime('%d.%m')})", 2)

    assert mock_put_data['called']
    assert mock_put_data['data']['message'] == expected_message


def test_file_does_not_exist():
    egs = EGSFreeGames(filename="nonexistent_path.json")
    data = egs.read_from_file()
    assert data == {"current": [], "future": []}


class MockDatetime(datetime.datetime):
    current_time = datetime.datetime(2023, 8, 31, 17, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.current_time


@pytest.mark.parametrize("test_time, expected_sleep_duration", [
    (datetime.datetime(2023, 8, 31, 18, 0), 300),
    (datetime.datetime(2023, 8, 31, 22, 0), 21600),
])
def test_check_epic_free_games_loop(monkeypatch, test_time, expected_sleep_duration):
    MockDatetime.current_time = test_time

    monkeypatch.setattr(EGSFreeGames, "get_free_games", lambda x: {'data': {}})
    monkeypatch.setattr(EGSFreeGames, "format_response",
                        lambda self, x: {"current": [{"title": "Mock Game"}], "future": []})
    monkeypatch.setattr(EGSFreeGames, "read_from_file", lambda x: {"current": []})
    monkeypatch.setattr(EGSFreeGames, "print_new_free_games", lambda self, x: None)
    monkeypatch.setattr(EGSFreeGames, "save_to_file", lambda self, x: None)
    monkeypatch.setattr(datetime, 'datetime', MockDatetime)

    sleep_call_duration = None

    def mock_sleep(duration):
        nonlocal sleep_call_duration
        sleep_call_duration = duration

    monkeypatch.setattr(time, "sleep", mock_sleep)

    epic_free_games = EGSFreeGames()
    epic_free_games.check_epic_free_games_loop(num_iterations=2)

    assert sleep_call_duration == expected_sleep_duration
