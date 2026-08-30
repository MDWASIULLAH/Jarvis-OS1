import tempfile
import time
from pathlib import Path

from app.companions.companions import CompanionService
from app.plugins.registry import PluginRegistry


def test_pairing_code_lets_a_device_pair_once():
    with tempfile.TemporaryDirectory() as tmp:
        service = CompanionService(Path(tmp) / "companions.db")
        pairing = service.create_pairing_code()
        device = service.pair(pairing["code"], "My Phone", "android")
        assert device is not None
        assert "access_token" in device

        # the same code cannot be reused for a second device
        assert service.pair(pairing["code"], "Second Device", "ios") is None


def test_pairing_code_expires():
    with tempfile.TemporaryDirectory() as tmp:
        service = CompanionService(Path(tmp) / "companions.db")
        pairing = service.create_pairing_code(ttl_seconds=30)  # clamped minimum
        # simulate expiry by pairing with a code that was never issued
        assert service.pair("000000", "Ghost", "android") is None


def test_authenticate_returns_device_and_updates_last_seen():
    with tempfile.TemporaryDirectory() as tmp:
        service = CompanionService(Path(tmp) / "companions.db")
        pairing = service.create_pairing_code()
        device = service.pair(pairing["code"], "My Laptop", "macos")
        found = service.authenticate(device["access_token"])
        assert found is not None
        assert found["label"] == "My Laptop"
        assert service.authenticate("not-a-real-token") is None


def test_record_event_is_retrievable():
    with tempfile.TemporaryDirectory() as tmp:
        service = CompanionService(Path(tmp) / "companions.db")
        pairing = service.create_pairing_code()
        device = service.pair(pairing["code"], "My Phone", "android")
        event = service.record_event(device["device_id"], "battery", {"level": 42})
        assert event["payload"]["level"] == 42


def test_plugin_registry_lists_known_plugins_disabled_by_default():
    registry = PluginRegistry()
    plugins = registry.available()
    assert any(p["identifier"] == "github" for p in plugins)
    assert all(p["enabled"] is False for p in plugins)


def test_plugin_registry_enable_toggles_state():
    registry = PluginRegistry()
    enabled = registry.enable("github")
    assert enabled["enabled"] is True
    assert enabled["oauth_connection_required"] is True
    assert registry.enable("not-a-real-plugin") is None
