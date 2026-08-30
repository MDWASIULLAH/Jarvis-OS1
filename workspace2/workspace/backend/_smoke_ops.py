"""Smoke-check every operations route against the real composed runtime."""
from fastapi.testclient import TestClient
from app.main import app

FAIL = []

with TestClient(app) as client:
    def check(method, path, body=None, expect=200):
        response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
        ok = response.status_code == expect
        if not ok:
            FAIL.append(f"{method.upper()} {path} -> {response.status_code} {response.text[:220]}")
        return response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

    print("--- Mission Control ---")
    missions = check("get", "/v1/missions")
    print("missions:", [m["mission_id"] for m in missions])
    mid = missions[0]["mission_id"]
    detail = check("get", f"/v1/missions/{mid}")
    print("detail keys:", sorted(detail))
    print("timeline:", len(detail["timeline"]), "| agents:", len(detail["related_agents"]))
    print("metrics:", detail["metrics"])
    print("resources:", detail["resources"])
    nexus = check("get", f"/v1/missions/{mid}/nexus")
    print("nexus:", len(nexus["nodes"]), "nodes /", len(nexus["edges"]), "edges")
    print("node sample:", nexus["nodes"][0])
    print("edge sample:", nexus["edges"][0])
    snaps = check("get", f"/v1/missions/{mid}/nexus/snapshots")
    print("snapshots:", len(snaps))
    created = check("post", "/v1/missions", {"title": "Route check", "description": "created by smoke test"}, expect=201)
    print("created:", created["mission_id"], created["lifecycle"])
    check("post", f"/v1/missions/{created['mission_id']}/pause")
    check("post", f"/v1/missions/{created['mission_id']}/resume")
    check("patch", f"/v1/missions/{created['mission_id']}", {"title": "Route check renamed"})
    check("get", f"/v1/missions/{created['mission_id']}/replay")
    check("get", "/v1/missions/does-not-exist", expect=404)

    print("\n--- Workforce ---")
    agents = check("get", "/v1/workforce/agents")
    print("agents:", len(agents))
    print("agent sample:", {k: agents[0][k] for k in ("agent_id", "kind", "name", "lifecycle", "health", "current_task")})
    print("status:", check("get", "/v1/workforce/status"))
    aid = agents[1]["agent_id"]
    check("get", f"/v1/workforce/agents/{aid}")
    check("post", f"/v1/workforce/agents/{aid}/pause")
    check("post", f"/v1/workforce/agents/{aid}/resume")
    check("post", f"/v1/workforce/agents/{aid}/health-check")
    task = check("post", "/v1/workforce/tasks", {"title": "Verify swarm assignment", "description": "smoke"}, expect=201)
    print("assigned:", task["assignment"])
    print("tasks:", len(check("get", "/v1/workforce/tasks")))
    bc = check("post", "/v1/workforce/broadcast", {"sender_agent_id": agents[0]["agent_id"], "content": "roll call"})
    print("broadcast:", len(bc), "messages")
    print("communications:", len(check("get", "/v1/workforce/communications")))
    new_agent = check("post", "/v1/workforce/agents", {"name": "Smoke Helper", "kind": "helper"}, expect=201)
    check("delete", f"/v1/workforce/agents/{new_agent['agent_id']}")
    check("get", "/v1/workforce/agents/nope", expect=404)

    print("\n--- Company ---")
    print("projects:", check("get", "/v1/company/projects"))
    project = check("post", "/v1/company/projects", {"title": "JARVIS UI hardening", "goal": "Connect every dashboard to the backend"}, expect=201)
    print("created project:", project["project_id"], project["lifecycle"], "milestones:", len(project["milestones"]), "gates:", len(project["quality_gates"]))
    pid = project["project_id"]
    dept = check("post", f"/v1/company/projects/{pid}/departments", {"kind": "engineering", "roles": ["backend_engineer", "frontend_engineer"]}, expect=201)
    print("department:", dept["name"], dept["roles"])
    review = check("post", f"/v1/company/projects/{pid}/reviews", {"kind": "code", "requested_by": "smoke"}, expect=201)
    print("review:", review["review_id"], review["kind"])
    dash = check("get", f"/v1/company/projects/{pid}")
    print("dashboard keys:", sorted(dash), "progress:", dash["progress"])
    print("roles vocabulary:", len(check("get", "/v1/company/roles")["roles"]), "roles")
    print("departments:", len(check("get", "/v1/company/departments")))
    check("get", "/v1/company/projects/nope", expect=404)

    print("\n--- Knowledge graph ---")
    graph = check("get", "/v1/graph")
    print("graph:", graph["total_nodes"], "nodes /", graph["total_edges"], "edges")
    print("node sample:", {k: graph["nodes"][0][k] for k in ("node_id", "entity_type", "label", "attributes")})
    node = check("post", "/v1/graph/nodes", {"label": "Smoke node", "entity_type": "task", "tags": ["smoke"]}, expect=201)
    edge = check("post", "/v1/graph/edges", {"source_node_id": "jarvis", "target_node_id": node["node_id"], "relationship": "contains"}, expect=201)
    print("edge:", edge["edge_id"][:8], edge["relationship"])
    detail = check("get", f"/v1/graph/nodes/{node['node_id']}")
    print("node detail:", len(detail["inbound"]["nodes"]), "inbound /", len(detail["similar"]), "similar")
    print("traverse:", len(check("get", "/v1/graph/traverse/jarvis?depth=2")["nodes"]), "nodes")
    check("delete", f"/v1/graph/nodes/{node['node_id']}")
    check("get", "/v1/graph/nodes/nope", expect=404)

    print("\n--- Security ---")
    overview = check("get", "/v1/security/overview")
    print("counts:", overview["counts"])
    print("policies:", len(overview["policies"]), "| first:", overview["policies"][0])
    ev = check("post", "/v1/security/evaluate", {"title": "Delete all project files", "target": "rm -rf /", "domain": "filesystem", "permissions": ["write", "administrator"]})
    print("risk:", ev["report"]["decision"]["risk"]["level"], "allowed:", ev["report"]["decision"]["allowed"], "threats:", len(ev["threats"]))
    ev2 = check("post", "/v1/security/evaluate", {"title": "Read a local note", "target": "notes.md", "domain": "filesystem", "permissions": ["read"]})
    print("risk:", ev2["report"]["decision"]["risk"]["level"], "allowed:", ev2["report"]["decision"]["allowed"])
    appr = check("post", "/v1/security/approvals", {"title": "Install a plugin", "target": "plugin.zip", "domain": "plugins", "permissions": ["install"]}, expect=201)
    print("approval:", appr["approval"]["state"])
    check("post", f"/v1/security/approvals/{appr['approval']['approval_id']}/decide", {"granted": True, "decided_by": "smoke"})
    print("audit:", len(check("get", "/v1/security/audit")), "records")
    print("trust:", check("post", "/v1/security/trust", {"subject_id": "operator", "score": 0.9, "rationale": "smoke"}))

print("\n================ RESULT ================")
if FAIL:
    print(f"{len(FAIL)} FAILURES:")
    for line in FAIL:
        print("  ", line)
    raise SystemExit(1)
print("all operations routes OK")
