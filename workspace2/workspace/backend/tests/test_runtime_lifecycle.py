from pathlib import Path

from app.core.config import Settings
from app.core.runtime import RuntimeProvider


def test_runtime_provider_starts_and_stops_its_service_graph(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        ollama_host="http://127.0.0.1:9",
        ollama_model="unused",
        cloud_base_url=None,
        cloud_api_key=None,
        cloud_model=None,
        allow_cloud=False,
    )
    provider = RuntimeProvider(settings_factory=lambda: settings)

    instance = provider.start()

    assert provider.started is True
    assert instance.settings.data_dir == tmp_path

    provider.stop()

    assert provider.started is False
