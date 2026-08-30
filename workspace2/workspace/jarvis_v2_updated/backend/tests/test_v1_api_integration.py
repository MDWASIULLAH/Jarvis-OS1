from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_status_endpoints():
    assert client.get("/health").status_code == 200
    status = client.get("/v1/status")
    assert status.status_code == 200
    assert status.json()["name"] == "JARVIS Core"


def test_agent_task_runs_through_real_threadpool_without_sqlite_errors():
    # This specifically exercises the sync-endpoint-in-a-worker-thread path
    # that broke before check_same_thread=False + a lock were added.
    response = client.post("/v1/agents/tasks", json={"text": "please debug this failing unit test"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "coding" in body["agents"]


def test_memory_remember_and_search_round_trip():
    client.post("/v1/memory/facts", json={"key": "fav_editor", "value": "prefers VS Code for Python", "category": "preference"})
    # TF-IDF matches shared vocabulary, not true synonyms -- "VS Code" is the
    # word overlap to search for, not a paraphrase like "editor".
    results = client.get("/v1/memory/search", params={"query": "VS Code preference"}).json()["results"]
    assert any(r["key"] == "fav_editor" for r in results)


def test_knowledge_ingest_and_search_round_trip():
    client.post("/v1/knowledge/documents", json={"title": "Networking note", "text": "TCP requires a handshake before data transfer."})
    results = client.get("/v1/knowledge/search", params={"query": "handshake"}).json()["results"]
    assert len(results) >= 1


def test_delete_requires_confirmation_before_it_actually_happens():
    client.post("/v1/memory/facts", json={"key": "temp_fact", "value": "delete me"})
    pending = client.delete("/v1/memory/facts/temp_fact").json()
    assert pending["requires_confirmation"] is True
    # not deleted yet
    still_there = client.get("/v1/memory/facts").json()["facts"]
    assert "temp_fact" in still_there
    confirmed = client.post("/v1/actions/confirm", json={"confirmation_id": pending["confirmation_id"]}).json()
    assert confirmed["deleted"] is True


def test_companion_devices_require_a_bearer_token():
    assert client.get("/v1/companions/devices").status_code == 401


def test_companion_pair_and_authenticated_event():
    code = client.post("/v1/companions/pairing-code").json()["code"]
    device = client.post(
        "/v1/companions/pair", json={"code": code, "label": "Test Phone", "platform": "android", "capabilities": []}
    ).json()
    token = device["access_token"]
    event = client.post(
        "/v1/companions/events",
        json={"event_type": "battery", "payload": {"level": 55}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert event.status_code == 200
    assert event.json()["payload"]["level"] == 55


def test_plugins_listed_and_enableable():
    plugins = client.get("/v1/plugins").json()["plugins"]
    assert len(plugins) > 0
    enabled = client.post("/v1/plugins/enable", json={"identifier": "github"}).json()
    assert enabled["enabled"] is True


def test_system_status_reports_real_local_metrics():
    status = client.get("/v1/system/status").json()
    assert status["platform"] in ("Linux", "Darwin", "Windows")
    assert "storage" in status
