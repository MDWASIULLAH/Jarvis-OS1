from unittest.mock import MagicMock, patch

import requests

from app.capabilities import fun_and_space, translate_currency


@patch("app.capabilities.fun_and_space.requests.get")
def test_space_news_parses_results(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "results": [{"title": "Rocket launches", "url": "https://example.com", "news_site": "Example"}]
    }
    mock_get.return_value = mock_response

    items = fun_and_space.space_news(limit=5)
    assert len(items) == 1
    assert items[0]["title"] == "Rocket launches"


def test_qr_code_url_encodes_data():
    url = fun_and_space.qr_code_url("hello world")
    assert url.startswith("https://api.qrserver.com/")
    assert "hello" in url


@patch("app.capabilities.translate_currency.requests.get")
def test_convert_currency_parses_rate(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"rates": {"EUR": 0.9}}
    mock_get.return_value = mock_response

    result = translate_currency.convert_currency(100, "USD", "EUR")
    assert "90.00 EUR" in result


@patch("app.capabilities.translate_currency.requests.post")
def test_translate_fails_soft_without_instance(mock_post):
    mock_post.side_effect = requests.RequestException("no instance")

    result = translate_currency.translate("hello", "es")
    assert "self-hosted" in result.lower()
