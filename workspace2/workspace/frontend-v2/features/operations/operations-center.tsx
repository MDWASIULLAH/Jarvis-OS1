"use client";
import { motion } from "framer-motion";
import { RefreshCw } from "lucide-react";
import { Diagnostics } from "./diagnostics";
import { DomainUnavailable } from "./domain-unavailable";
import { EventExplorer } from "./event-explorer";
import { OperationalAnalytics } from "./operational-analytics";
import { SearchProbe } from "./search-probe";
import { SecurityStatus } from "./security-status";
import { SystemMonitor } from "./system-monitor";
import { SystemOverview } from "./system-overview";
import { useOperations } from "./hooks/use-operations";

export function OperationsCenter() {
  const ops = useOperations();
  const refresh = () => { for (const query of Object.values(ops)) void query.refetch(); };

  return <motion.div className="operations-center" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header>
      <div>
        <span>Operational intelligence</span>
        <h1>Operations Center</h1>
        <p>Runtime evidence, measured subsystem health, audit events, and live operational analytics.</p>
      </div>
      <button onClick={refresh}><RefreshCw size={15} className={ops.diagnostics.isFetching ? "spin" : undefined}/> Refresh</button>
    </header>

    <div className="operations-grid">
      <SystemOverview
        runtime={ops.runtime.data}
        system={ops.system.data}
        taskCount={ops.tasks.data?.tasks.length}
        workspace={ops.workspace.data}
      />
      <SystemMonitor system={ops.system.data} resources={ops.mission.data?.resources}/>
      <Diagnostics
        report={ops.diagnostics.data}
        reason={ops.diagnostics.isError ? "The diagnostics endpoint is unreachable. Start the JARVIS backend on port 8000 and refresh." : undefined}
      />
      <OperationalAnalytics
        decisions={ops.decisions.data?.history ?? []}
        reflections={ops.reflections.data?.history ?? []}
        tools={ops.tools.data?.tools ?? []}
        connectors={ops.connectors.data?.connectors ?? []}
        metrics={ops.mission.data?.metrics}
      />
      <EventExplorer entries={ops.audit.data?.entries ?? []}/>
      <SecurityStatus
        summary={ops.security.data}
        reason={ops.security.isError ? "The Security Framework endpoint is unreachable." : undefined}
      />
      <SearchProbe/>
      {/* No installation manager is composed in this build's Runtime, so there is
          nothing to report — say that instead of listing dead rows. */}
      <DomainUnavailable
        title="Installation Center"
        description="This build's runtime composes no installation manager, so there are no plans, dependencies, or rollbacks to report. Package installs happen through the plugin registry instead."
        items={["Environment provisioning", "Dependency graph", "Download queue", "Rollback plans"]}
      />
    </div>
  </motion.div>;
}
