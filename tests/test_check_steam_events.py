import time

from telegram.helpers import escape_markdown
from config import message_queue
from modules.steam_events import SteamEvents
import requests

test_response_content = """<rss xmlns:sy="http://purl.org/rss/1.0/modules/syndication/" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
<channel>
<title>www.SteamCardExchange.net - Event Feed</title>
<link>https://www.steamcardexchange.net/</link>
<pubDate>Tue, 29 Aug 2023 15:00:01 UTC</pubDate>
<sy:updatePeriod>hourly</sy:updatePeriod>
<sy:updateFrequency>1</sy:updateFrequency>
<item>
<title>
<![CDATA[ Strategy Fest 2023 ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-2575570</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-2575570</guid>
<pubDate>Mon, 28 Aug 2023 18:23:18 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/2575570.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/2575570.png" type="image/jpeg"/>
</item>
<item>
<title>
<![CDATA[ QuakeCon 2023 ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-2111330</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-2111330</guid>
<pubDate>Thu, 10 Aug 2023 19:18:38 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/2111330.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/2111330.png" type="image/jpeg"/>
</item>
<item>
<title>
<![CDATA[ Steam Visual Novel Fest 2023 ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-2540780</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-2540780</guid>
<pubDate>Mon, 07 Aug 2023 16:50:04 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/2540780.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/2540780.png" type="image/jpeg"/>
</item>
<item>
<title>
<![CDATA[ Wargaming Pub Weekend Advertising App ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-1906580</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-1906580</guid>
<pubDate>Fri, 04 Aug 2023 06:27:34 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/1906580.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/1906580.png" type="image/jpeg"/>
</item>
<item>
<title>
<![CDATA[ Steam Stealth Fest 2023 ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-2528530</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-2528530</guid>
<pubDate>Fri, 21 Jul 2023 23:00:05 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/2528530.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/2528530.png" type="image/jpeg"/>
</item>
<item>
<title>
<![CDATA[ Dying Light Quiz - Steam Summer Sale 2023 ]]>
</title>
<link>https://www.steamcardexchange.net/index.php?gamepage-appid-2493300</link>
<guid isPermaLink="true">https://www.steamcardexchange.net/index.php?gamepage-appid-2493300</guid>
<pubDate>Thu, 29 Jun 2023 18:10:05 UTC</pubDate>
<enclosure url="https://www.steamcardexchange.net/static/img/banners/2493300.png" type="image/jpeg"/>
<media:content url="https://www.steamcardexchange.net/static/img/banners/2493300.png" type="image/jpeg"/>
</item>
</channel>
</rss>"""


class MockResponse:
    def __init__(self, content, status_code):
        self.content = content
        self.status_code = status_code


def test_get_last_events_success(monkeypatch):
    def mock_get(*args, **kwargs):
        return MockResponse(test_response_content, 200)

    monkeypatch.setattr(requests, "get", mock_get)
    se = SteamEvents()
    result = se.get_last_events()
    assert result == test_response_content


def test_format_response() -> None:
    expected_result = [
        {"title": "Strategy Fest 2023",
         "link": "https://www.steamcardexchange.net/index.php?gamepage-appid-2575570",
         "enclosure_url": "https://www.steamcardexchange.net/static/img/banners/2575570.png"},
        {"title": "QuakeCon 2023",
         "link": "https://www.steamcardexchange.net/index.php?gamepage-appid-2111330",
         "enclosure_url": "https://www.steamcardexchange.net/static/img/banners/2111330.png"},
        {"title": "Steam Visual Novel Fest 2023",
         "link": "https://www.steamcardexchange.net/index.php?gamepage-appid-2540780",
         "enclosure_url": "https://www.steamcardexchange.net/static/img/banners/2540780.png"},
        {"title": "Wargaming Pub Weekend Advertising App",
         "link": "https://www.steamcardexchange.net/index.php?gamepage-appid-1906580",
         "enclosure_url": "https://www.steamcardexchange.net/static/img/banners/1906580.png"},
        {"title": "Steam Stealth Fest 2023",
         "link": "https://www.steamcardexchange.net/index.php?gamepage-appid-2528530",
         "enclosure_url": "https://www.steamcardexchange.net/static/img/banners/2528530.png"},
    ]
    se = SteamEvents()
    result = se.format_response(test_response_content)

    assert result == expected_result


def test_save_and_read_from_file(tmpdir):
    events_data = [
        {
            "title": "Test Event 1",
            "link": "https://test1.com",
            "enclosure_url": "https://test1.com/image.jpg"
        }
    ]
    se = SteamEvents(filename=tmpdir.join("test_file.json"))

    se.save_to_file(events_data)
    read_data = se.read_from_file()

    assert read_data == events_data


def test_get_new_events():
    fetched_events = [
        {"title": "Event 1", "link": "link1", "enclosure_url": "url1"},
        {"title": "Event 2", "link": "link2", "enclosure_url": "url2"},
        {"title": "Event 3", "link": "link3", "enclosure_url": "url3"}
    ]
    saved_events = [
        {"title": "Event 1", "link": "link1", "enclosure_url": "url1"}
    ]

    new_events = SteamEvents.get_new_events(fetched_events, saved_events)

    assert len(new_events) == 2
    assert {"title": "Event 2", "link": "link2", "enclosure_url": "url2"} in new_events
    assert {"title": "Event 3", "link": "link3", "enclosure_url": "url3"} in new_events


def test_print_new_events(monkeypatch):
    mock_put_data = {}

    def mock_put(data):
        mock_put_data['called'] = True
        mock_put_data['data'] = data

    monkeypatch.setattr(message_queue, "put", mock_put)
    mock_put.called = False

    new_events = [
        {"title": "Event 1", "link": "link1", "enclosure_url": "url1"}
    ]

    SteamEvents.print_new_events(new_events)

    assert mock_put_data['called']
    assert mock_put_data['data']['message'] == (
        f"🚀 *{escape_markdown('New Steam Event!', 2)}* 🚀\n"
        f"🎮 *Title:* {escape_markdown('Event 1', 2)}\n"
        f"🔗 *Items:* [Click Here](link1)"
    )
    assert mock_put_data['data']['photos'] == ["url1"]


def test_file_does_not_exist():
    se = SteamEvents(filename="nonexistent_path.json")
    data = se.read_from_file()
    assert data == []


def test_check_steam_events_loop(monkeypatch):
    monkeypatch.setattr(SteamEvents, "get_last_events", lambda x: test_response_content)

    monkeypatch.setattr(SteamEvents, "format_response", lambda x, y: [{"title": "Mock Event"}])

    monkeypatch.setattr(SteamEvents, "read_from_file", lambda x: [])

    monkeypatch.setattr(SteamEvents, "print_new_events", lambda x, y: None)
    monkeypatch.setattr(SteamEvents, "save_to_file", lambda x, y: None)

    monkeypatch.setattr(time, "sleep", lambda x: None)

    steam_events = SteamEvents()
    steam_events.check_steam_events_loop(num_iterations=2)
