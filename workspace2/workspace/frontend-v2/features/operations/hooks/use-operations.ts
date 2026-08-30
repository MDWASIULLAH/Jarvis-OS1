"use client";
import { useQuery } from "@tanstack/react-query";
import { operationsService } from "../services/operations-service";

const polling = { refetchInterval: 10_000, staleTime: 5_000 };

export function useOperations() {
  return {
    runtime: useQuery({ queryKey: ["runtime-status"], queryFn: operationsService.runtime, ...polling }),
    system: useQuery({ queryKey: ["system-status"], queryFn: operationsService.system, ...polling }),
    audit: useQuery({ queryKey: ["system-audit"], queryFn: operationsService.audit, ...polling }),
    brain: useQuery({ queryKey: ["brain-status"], queryFn: operationsService.brain, ...polling }),
    tools: useQuery({ queryKey: ["tools"], queryFn: operationsService.tools, ...polling }),
    connectors: useQuery({ queryKey: ["connectors"], queryFn: operationsService.connectors, ...polling }),
    decisions: useQuery({ queryKey: ["decision-history"], queryFn: operationsService.decisions, ...polling }),
    reflections: useQuery({ queryKey: ["reflection-history"], queryFn: operationsService.reflections, ...polling }),
    tasks: useQuery({ queryKey: ["agent-tasks"], queryFn: operationsService.tasks, ...polling }),
    diagnostics: useQuery({ queryKey: ["system-diagnostics"], queryFn: operationsService.diagnostics, ...polling }),
    mission: useQuery({ queryKey: ["runtime-mission"], queryFn: operationsService.mission, ...polling }),
    security: useQuery({ queryKey: ["security-overview"], queryFn: operationsService.security, ...polling }),
    workspace: useQuery({ queryKey: ["workspace-files"], queryFn: operationsService.workspace, ...polling }),
  };
}
