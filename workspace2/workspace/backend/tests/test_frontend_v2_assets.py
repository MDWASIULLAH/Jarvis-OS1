from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/"frontend-v2"

# The eight modules the sidebar lists and the shell routes to a real dashboard.
SHELL_MODULES=("mission-control","neural-nexus","operations","development-studio","agents","knowledge","security","settings")
# Declared NavigationIds without a dedicated dashboard; ModuleCenter serves them.
FALLTHROUGH_MODULES=("workspace","memory","reflection","evolution","search","installation","company","plugins")

def _squeeze(text:str)->str:
    """Whitespace-stripped view of a source file.

    These are source-text assertions, so a reformat (prettier, de-minifying a
    stylesheet) used to fail them even though nothing behavioural changed.
    Comparing squeezed text keeps the assertion about content, not formatting.
    """
    return "".join(text.split())

def test_v2_uses_next_typescript_and_prepares_backend_clients():
    package=(ROOT/"package.json").read_text(encoding="utf-8")
    client=(ROOT/"services"/"api-client.ts").read_text(encoding="utf-8")
    for dependency in ("next","react","typescript","@tanstack/react-query","framer-motion"):
        assert dependency in package
    assert "fetch" in client and "ApiClient" in client
def test_v2_builds_foundation_navigation_and_empty_workspace_only():
    page=(ROOT/"layouts"/"operating-system-shell.tsx").read_text(encoding="utf-8")
    navigation=(ROOT/"components"/"navigation"/"app-sidebar.tsx").read_text(encoding="utf-8")
    ids=(ROOT/"types"/"navigation.ts").read_text(encoding="utf-8")
    boundary=(ROOT/"components"/"ui"/"workspace-error-boundary.tsx").read_text(encoding="utf-8")
    # The sidebar advertises only the modules that have a dashboard behind them;
    # listing views that fell through to a generic panel is what made JARVIS look
    # broken. Each listed id must be declared and routed.
    for view in SHELL_MODULES:
        assert f'"{view}"' in navigation, f"sidebar no longer lists {view}"
        assert f'"{view}"' in ids, f"{view} is not a declared NavigationId"
        assert f'active === "{view}"' in page, f"shell does not route {view}"
    # The remaining ids stay reachable (command palette, stored state) through the
    # generic module panel rather than 404ing the workspace.
    for view in FALLTHROUGH_MODULES:
        assert f'"{view}"' in ids
    assert "ModuleCenter" in page and "id={active}" in page
    # Empty and failed states are rendered by the boundary the shell wraps every
    # module in, not by the shell itself.
    assert "EmptyState" in boundary and "CommandPalette" in page

def test_v2_chat_is_composed_from_frontend_only_boundaries():
    chat = ROOT / "features" / "chat"
    coordinator = (chat / "chat-experience.tsx").read_text(encoding="utf-8")
    stream = (chat / "chat-service.ts").read_text(encoding="utf-8")
    for filename in ("composer.tsx", "conversation-sidebar.tsx", "message-list.tsx", "markdown-renderer.tsx", "code-block.tsx", "artifact-viewer.tsx", "tool-panel.tsx", "typing-indicator.tsx", "mermaid-diagram.tsx", "tool-events.ts"):
        assert (chat / filename).is_file()
    for store in ("conversation-store.ts", "stream-store.ts", "upload-store.ts", "tool-store.ts"):
        assert (chat / "stores" / store).is_file()
    # The stream must be addressed through the shared apiUrl() helper. A bare
    # fetch("/v1/chat/stream") is relative, so it hit the Next dev server on
    # :3000 instead of the backend on :8000 and every chat turn failed.
    assert 'apiUrl("/v1/chat/stream")' in stream and "services/backend" in stream
    assert "AbortController" in coordinator and "localStorage" in coordinator
    assert "MessageList" in coordinator and "ConversationSidebar" in coordinator

def test_v2_chat_supports_streaming_markdown_code_and_upload_accessibility():
    chat = ROOT / "features" / "chat"
    markdown = (chat / "markdown-renderer.tsx").read_text(encoding="utf-8")
    code = (chat / "code-block.tsx").read_text(encoding="utf-8")
    composer = (chat / "composer.tsx").read_text(encoding="utf-8")
    stylesheet = (ROOT / "styles" / "globals.css").read_text(encoding="utf-8")
    assert "remarkGfm" in markdown and "remarkMath" in markdown and "MermaidDiagram" in markdown and "CodeBlock" in markdown
    assert "SyntaxHighlighter" in code and "Copy code" in code and "Download code" in code
    assert "Monaco Editor is not connected" in code and "jarvis:open-artifact" not in code
    assert "clipboardData.files" in composer and "Stop generation" in composer and "aria-label" in composer
    assert ".typing-indicator" in stylesheet
    # A responsive breakpoint has to exist; its exact width and spacing are the
    # stylesheet's business, so match the squeezed form.
    assert "@media(max-width:" in _squeeze(stylesheet)

def test_v2_mission_control_uses_real_contracts_or_explicit_unavailable_states():
    mission = ROOT / "features" / "mission-control"
    dashboard = (mission / "mission-dashboard.tsx").read_text(encoding="utf-8")
    service = (mission / "services" / "mission-service.ts").read_text(encoding="utf-8")
    replay = (mission / "mission-replay.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    for filename in ("mission-card.tsx", "mission-list.tsx", "mission-details.tsx", "mission-timeline.tsx", "mission-replay.tsx", "flight-recorder.tsx", "resource-monitor.tsx", "system-health.tsx", "metrics-panel.tsx"):
        assert (mission / filename).is_file()
    assert '"/v1/status"' in service and '"/v1/agents/tasks"' in service
    assert "NEXT_PUBLIC_JARVIS_MISSIONS_API_URL" in service
    assert "MissionDashboard" in shell and 'active === "mission-control"' in shell
    assert "setReplay" in replay and "setReplayIndex" in replay
    assert "mission-api-notice" in dashboard and "unavailable" in service

def test_v2_chat_uses_existing_rich_stream_contract_for_execution_activity():
    chat = ROOT / "features" / "chat"
    service = (chat / "chat-service.ts").read_text(encoding="utf-8")
    experience = (chat / "chat-experience.tsx").read_text(encoding="utf-8")
    assert '"/v1/chat/stream"' in service and 'type === "delta"' in service
    assert "ExecutionTimeline" in (chat / "message-list.tsx").read_text(encoding="utf-8")
    assert "setActivities" in experience and "execution:" in experience

def test_v2_neural_nexus_uses_snapshot_contract_without_fake_graph_data():
    nexus = ROOT / "features" / "mission-control"
    service = (nexus / "services" / "mission-service.ts").read_text(encoding="utf-8")
    graph = (nexus / "nexus-graph.tsx").read_text(encoding="utf-8")
    view_3d = (nexus / "nexus-3d-view.tsx").read_text(encoding="utf-8")
    component = (nexus / "neural-nexus.tsx").read_text(encoding="utf-8")
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    for filename in ("neural-nexus.tsx", "nexus-graph.tsx", "nexus-3d-view.tsx", "nexus-inspector.tsx"):
        assert (nexus / filename).is_file()
    assert "@xyflow/react" in package and '"three"' in package
    assert "ReactFlow" in graph and "MiniMap" in graph and "nexusFlow" in graph
    assert "OrbitControls" in view_3d and 'import("three")' in view_3d
    assert "nexusSnapshots" in service and "NEXT_PUBLIC_JARVIS_MISSIONS_API_URL" in service
    assert "nexus-unavailable" in component and "invalidateQueries" in component

def test_v2_workforce_uses_public_tasks_and_optional_operational_contracts():
    workforce = ROOT / "features" / "workforce"
    service = (workforce / "services" / "workforce-service.ts").read_text(encoding="utf-8")
    dashboard = (workforce / "workforce-dashboard.tsx").read_text(encoding="utf-8")
    nexus = (ROOT / "features" / "mission-control" / "neural-nexus.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    for filename in ("workforce-dashboard.tsx", "agent-card.tsx", "agent-grid.tsx", "agent-details.tsx", "agent-hierarchy.tsx", "communication-viewer.tsx", "performance-panel.tsx"):
        assert (workforce / filename).is_file()
    assert '"/v1/agents/tasks"' in service and "NEXT_PUBLIC_JARVIS_WORKFORCE_API_URL" in service
    assert "workforce-api-notice" in dashboard and "selectAgent" in dashboard
    assert 'active === "agents"' in shell
    assert "useOperationalSelectionStore" in nexus

def test_v2_operations_center_uses_available_operational_endpoints_and_explicit_gaps():
    operations = ROOT / "features" / "operations"
    service = (operations / "services" / "operations-service.ts").read_text(encoding="utf-8")
    center = (operations / "operations-center.tsx").read_text(encoding="utf-8")
    explorer = (operations / "event-explorer.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    for filename in ("operations-center.tsx", "system-overview.tsx", "system-monitor.tsx", "diagnostics.tsx", "event-explorer.tsx", "operational-analytics.tsx", "domain-unavailable.tsx"):
        assert (operations / filename).is_file()
    for endpoint in ('"/v1/status"', '"/v1/system/status"', '"/v1/system/audit"', '"/v1/brain/status"', '"/v1/decision/history"', '"/v1/reflection/history"'):
        assert endpoint in service
    assert "DomainUnavailable" in center and "EventExplorer" in center
    assert "Export visible events" in explorer and "Search audit events" in explorer
    assert 'active === "operations"' in shell

def test_v2_chat_supports_message_bookmarks_and_markdown_export():
    chat = ROOT / "features" / "chat"
    actions = (chat / "message-actions.tsx").read_text(encoding="utf-8")
    assert (chat / "stores" / "bookmark-store.ts").is_file()
    assert "Bookmark message" in actions and "Copy message as Markdown" in actions and "Export message as Markdown" in actions

def test_v2_development_studio_uses_optional_company_contract_and_real_goal_task_records():
    studio = ROOT / "features" / "development-studio"
    service = (studio / "services" / "project-service.ts").read_text(encoding="utf-8")
    dashboard = (studio / "dashboard.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    for filename in ("dashboard.tsx", "project-card.tsx", "project-list.tsx", "studio-panels.tsx"):
        assert (studio / filename).is_file()
    assert "NEXT_PUBLIC_JARVIS_DEVELOPMENT_API_URL" in service
    assert '"/v1/goals"' in service and '"/v1/agents/tasks"' in service
    assert "ProjectList" in dashboard and "StudioPanels" in dashboard
    assert 'active === "development-studio"' in shell

def test_v2_hardening_removes_dead_global_controls_with_persisted_preferences():
    store = (ROOT / "store" / "ui-store.ts").read_text(encoding="utf-8")
    topbar = (ROOT / "components" / "navigation" / "top-bar.tsx").read_text(encoding="utf-8")
    palette = (ROOT / "components" / "command" / "command-palette.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    settings = (ROOT / "features" / "settings" / "settings-center.tsx").read_text(encoding="utf-8")
    assert "persist" in store and "jarvis-ui-preferences" in store
    assert "setNotificationsOpen" in topbar
    assert "Open Development Studio" in palette and "disabled" not in palette
    assert "NotificationCenter" in shell and "SettingsCenter" in shell
    assert "local" in settings and "setTheme" in settings


def test_v2_workspace_loads_feature_modules_lazily_and_contains_failures():
    shell = (ROOT / "layouts" / "operating-system-shell.tsx").read_text(encoding="utf-8")
    squeezed = _squeeze(shell)
    boundary = ROOT / "components" / "ui" / "workspace-error-boundary.tsx"
    # Every workspace surface is code-split behind next/dynamic, so one heavy
    # module (three.js, mermaid) cannot block the shell from painting.
    lazy = (
        "chat/codex-harness",
        "mission-control/mission-dashboard",
        "mission-control/neural-nexus",
        "operations/operations-center",
        "development-studio/dashboard",
        "workforce/workforce-dashboard",
        "knowledge-graph/knowledge-graph-center",
        "security/security-framework-center",
        "settings/settings-center",
    )
    for module in lazy:
        assert f'dynamic(()=>import("../features/{module}")' in squeezed, f"{module} is not lazily imported"
    assert squeezed.count("ssr:false") >= len(lazy)
    # A module that throws must degrade to a recoverable panel, not a blank shell.
    assert "WorkspaceErrorBoundary" in shell
    assert boundary.is_file()


def test_v2_code_editor_control_reports_an_unavailable_integration_honestly():
    code_block = (ROOT / "features" / "chat" / "code-block.tsx").read_text(encoding="utf-8")
    assert "jarvis:open-artifact" not in code_block
    assert "Monaco Editor is not connected" in code_block
