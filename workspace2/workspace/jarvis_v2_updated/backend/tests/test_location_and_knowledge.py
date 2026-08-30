from unittest.mock import MagicMock, patch

from app.capabilities import knowledge_apis, location_services


@patch("app.capabilities.location_services.requests.get")
def test_geocode_parses_result(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = [{"lat": "28.6139", "lon": "77.2090", "display_name": "New Delhi, India"}]
    mock_get.return_value = mock_response

    result = location_services.geocode("New Delhi")
    assert result["lat"] == 28.6139
    assert "Delhi" in result["display_name"]


@patch("app.capabilities.location_services.requests.get")
def test_geocode_returns_none_on_no_results(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    assert location_services.geocode("nonexistent place xyz") is None


@patch("app.capabilities.location_services.requests.get")
def test_ip_info_returns_none_on_failed_status(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"status": "fail", "message": "invalid query"}
    mock_get.return_value = mock_response

    assert location_services.ip_info("not-an-ip") is None


@patch("app.capabilities.knowledge_apis.requests.get")
def test_define_parses_entry(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = [
        {"meanings": [{"partOfSpeech": "noun", "definitions": [{"definition": "a test definition"}]}]}
    ]
    mock_get.return_value = mock_response

    result = knowledge_apis.define("test")
    assert "test definition" in result


@patch("app.capabilities.knowledge_apis.requests.get")
def test_define_handles_not_found(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    result = knowledge_apis.define("asdkjfhaskdjfh")
    assert "couldn't find" in result.lower()
