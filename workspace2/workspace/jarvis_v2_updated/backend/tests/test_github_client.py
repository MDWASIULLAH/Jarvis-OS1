from unittest.mock import MagicMock, patch

import requests

from app.capabilities.github_client import GitHubClient


@patch("app.capabilities.github_client.requests.get")
def test_get_repo_parses_response(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "full_name": "MDWASIULLAH/jarvis",
        "description": "A JARVIS-style assistant",
        "stargazers_count": 3,
        "language": "Python",
        "html_url": "https://github.com/MDWASIULLAH/jarvis",
    }
    mock_get.return_value = mock_response

    repo = GitHubClient().get_repo("MDWASIULLAH", "jarvis")
    assert repo["full_name"] == "MDWASIULLAH/jarvis"
    assert repo["stars"] == 3


@patch("app.capabilities.github_client.requests.get")
def test_get_repo_returns_none_on_rate_limit_or_error(mock_get):
    # Mirrors the real 403 rate-limit response this sandbox's shared IP just hit.
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("403 rate limit exceeded")
    mock_get.return_value = mock_response

    assert GitHubClient().get_repo("MDWASIULLAH", "jarvis") is None


@patch("app.capabilities.github_client.requests.get")
def test_search_repos_parses_results(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "items": [{"full_name": "example/repo", "stargazers_count": 10, "html_url": "https://github.com/example/repo"}]
    }
    mock_get.return_value = mock_response

    results = GitHubClient().search_repos("jarvis assistant")
    assert len(results) == 1
    assert results[0]["full_name"] == "example/repo"


def test_token_adds_auth_header():
    client = GitHubClient(token="fake-token-123")
    assert client.headers["Authorization"] == "Bearer fake-token-123"
