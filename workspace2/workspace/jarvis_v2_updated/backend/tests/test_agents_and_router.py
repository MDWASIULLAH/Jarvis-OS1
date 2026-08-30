import tempfile
from pathlib import Path

from app.agents.orchestrator import AgentName, AgentOrchestrator, AgentRouter
from app.brain.llm_interface import MockBackend, ModelRouter
from app.memory.memory_store import MemorySystem
from app.observability.audit import AuditLog
from app.tasks.store import TaskStatus, TaskStore


def test_router_matches_coding_keywords():
    route = AgentRouter().route("can you help debug this python code")
    assert AgentName.CODING in route.agents


def test_router_falls_back_to_planning_when_nothing_matches():
    route = AgentRouter().route("hello there")
    assert route.agents == [AgentName.PLANNING]


def test_router_prepends_planning_for_multi_agent_requests():
    route = AgentRouter().route("draft an email about the meeting on my calendar")
    assert AgentName.PLANNING in route.agents
    assert len(route.agents) >= 2


def test_router_caps_at_four_agents():
    text = "code debug test email mail calendar meeting screenshot camera file folder cpu ram"
    route = AgentRouter().route(text)
    assert len(route.agents) <= 4


def test_orchestrator_executes_and_records_a_completed_task():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        memory = MemorySystem(tmp_path)
        tasks = TaskStore(tmp_path / "tasks.db")
        audit = AuditLog(tmp_path / "audit.db")
        orchestrator = AgentOrchestrator(model=MockBackend(), memory=memory, tasks=tasks, audit=audit)

        result = orchestrator.execute("please debug my failing test")

        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["result"]["agent_results"]
        assert result["result"]["requires_confirmation_for_actions"] is True


def test_model_router_defaults_to_local_without_opt_in():
    class TaggedBackend(MockBackend):
        def __init__(self, tag):
            self.tag = tag

        def generate(self, prompt, system=None):
            return f"[{self.tag}] {prompt}"

    router = ModelRouter(local=TaggedBackend("local"), cloud=TaggedBackend("cloud"), allow_cloud=False)
    reply = router.generate("hello", preference="cloud")
    assert reply.startswith("[local]")  # cloud was requested but never opted in, so local still answers
    assert router.status()["cloud_allowed"] is False


def test_model_router_uses_cloud_when_explicitly_allowed_and_requested():
    class TaggedBackend(MockBackend):
        def __init__(self, tag):
            self.tag = tag

        def generate(self, prompt, system=None):
            return f"[{self.tag}] {prompt}"

    router = ModelRouter(local=TaggedBackend("local"), cloud=TaggedBackend("cloud"), allow_cloud=True)
    reply = router.generate("hello", preference="cloud")
    assert reply.startswith("[cloud]")
