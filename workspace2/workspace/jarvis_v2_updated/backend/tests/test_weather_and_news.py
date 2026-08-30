from unittest.mock import MagicMock, patch

import requests

from app.capabilities.news_module import NewsModule
from app.capabilities.weather_module import WeatherModule

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>Sample Headline One</title>
      <link>https://example.com/1</link>
      <source url="https://example.com">Example Source</source>
    </item>
  </channel>
</rss>"""


@patch("app.capabilities.weather_module.requests.get")
def test_open_meteo_used_by_default(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"current_weather": {"temperature": 21.3, "windspeed": 8.0}}
    mock_get.return_value = mock_response

    weather = WeatherModule()
    result = weather.current_weather(28.6, 77.2)
    assert "21" in result
    assert "Open-Meteo" in result


@patch("app.capabilities.weather_module.requests.get")
def test_weather_fails_soft_on_network_error(mock_get):
    mock_get.side_effect = requests.RequestException("down")

    weather = WeatherModule()
    result = weather.current_weather(28.6, 77.2)
    assert "couldn't reach" in result.lower()


def test_news_not_configured_without_key():
    assert NewsModule().is_configured() is False


@patch("app.capabilities.news_module.requests.get")
def test_rss_fallback_parses_headlines(mock_get):
    mock_response = MagicMock()
    mock_response.content = SAMPLE_RSS.encode("utf-8")
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    news = NewsModule()
    items = news.headlines(limit=5)
    assert len(items) == 1
    assert items[0].title == "Sample Headline One"
    assert items[0].source == "Example Source"


@patch("app.capabilities.news_module.requests.get")
def test_news_summarize_fails_soft(mock_get):
    mock_get.side_effect = requests.RequestException("down")
    result = NewsModule().summarize()
    assert "couldn't reach" in result.lower()
