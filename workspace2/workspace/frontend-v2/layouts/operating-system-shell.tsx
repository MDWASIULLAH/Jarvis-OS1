"use client";

import dynamic from "next/dynamic";
import { TopBar } from "../components/navigation/top-bar";
import { AppSidebar } from "../components/navigation/app-sidebar";
import { CodexRightPanel } from "../components/activity/codex-right-panel";
import { PowerShellDrawer } from "../components/terminal/powershell-drawer";
import { CommandPalette } from "../components/command/command-palette";
import { NotificationCenter } from "../components/notifications/notification-center";
import { ScheduledModal } from "../components/modals/scheduled-modal";
import { PluginsModal } from "../components/modals/plugins-modal";
import { WorkspaceErrorBoundary } from "../components/ui/workspace-error-boundary";
import { useUIStore } from "../store/ui-store";
import { ModuleCenter } from "../features/system/module-center";

const loading = () => (
  <section className="chat-loading" aria-live="polite" style={{ padding: 40, textAlign: "center" }}>
    Loading JARVIS workspace…
  </section>
);

const CodexHarness = dynamic(
  () => import("../features/chat/codex-harness").then((module) => module.CodexHarness),
  { ssr: false, loading }
);
const DevelopmentStudio = dynamic(
  () =>
    import("../features/development-studio/dashboard").then(
      (module) => module.DevelopmentStudio
    ),
  { ssr: false, loading }
);
const MissionDashboard = dynamic(
  () =>
    import("../features/mission-control/mission-dashboard").then(
      (module) => module.MissionDashboard
    ),
  { ssr: false, loading }
);
const NeuralNexus = dynamic(
  () =>
    import("../features/mission-control/neural-nexus").then((module) => module.NeuralNexus),
  { ssr: false, loading }
);
const OperationsCenter = dynamic(
  () =>
    import("../features/operations/operations-center").then(
      (module) => module.OperationsCenter
    ),
  { ssr: false, loading }
);
const SettingsCenter = dynamic(
  () => import("../features/settings/settings-center").then((module) => module.SettingsCenter),
  { ssr: false, loading }
);
const WorkforceDashboard = dynamic(
  () =>
    import("../features/workforce/workforce-dashboard").then(
      (module) => module.WorkforceDashboard
    ),
  { ssr: false, loading }
);
const KnowledgeGraphCenter = dynamic(
  () =>
    import("../features/knowledge-graph/knowledge-graph-center").then(
      (module) => module.KnowledgeGraphCenter
    ),
  { ssr: false, loading }
);
const SecurityFrameworkCenter = dynamic(
  () =>
    import("../features/security/security-framework-center").then(
      (module) => module.SecurityFrameworkCenter
    ),
  { ssr: false, loading }
);
const AIStudio = dynamic(
  () => import("../features/ai-studio/ai-studio").then((module) => module.AIStudio),
  { ssr: false, loading }
);

export function OperatingSystemShell() {
  const { active, leftOpen, rightOpen } = useUIStore();

  let mainContent;
  if (active === "chat") {
    mainContent = <CodexHarness />;
  } else if (active === "mission-control") {
    mainContent = <MissionDashboard />;
  } else if (active === "neural-nexus") {
    mainContent = <NeuralNexus />;
  } else if (active === "operations") {
    mainContent = <OperationsCenter />;
  } else if (active === "development-studio") {
    mainContent = <DevelopmentStudio />;
  } else if (active === "agents") {
    mainContent = <WorkforceDashboard />;
  } else if (active === "ai-studio") {
    mainContent = <AIStudio />;
  } else if (active === "knowledge") {
    mainContent = <KnowledgeGraphCenter />;
  } else if (active === "security") {
    mainContent = <SecurityFrameworkCenter />;
  } else if (active === "settings") {
    mainContent = <SettingsCenter />;
  } else {
    mainContent = <ModuleCenter id={active} />;
  }

  return (
    // Theme lives on <html data-theme> (see ThemeManager). Re-declaring it here
    // with the raw store value re-broke the palette whenever theme === "system",
    // which matches no stylesheet.
    <div className="codex-desktop-shell">
      {/* Top Desktop Bar with Menus, Active Project, and Window Controls */}
      <TopBar />

      {/* App Body (Sidebar | Main Canvas | Right Panel) */}
      <div
        className={`app-body ${!leftOpen ? "left-collapsed" : ""} ${
          rightOpen ? "right-open" : ""
        }`}
      >
        <AppSidebar />

        <main className="main-workspace">
          <WorkspaceErrorBoundary key={active}>
            {mainContent}
          </WorkspaceErrorBoundary>

          {/* Integrated PowerShell Drawer at the Bottom */}
          <PowerShellDrawer />
        </main>

        <CodexRightPanel />
      </div>

      {/* Global Modals */}
      <CommandPalette />
      <NotificationCenter />
      <ScheduledModal />
      <PluginsModal />
    </div>
  );
}
