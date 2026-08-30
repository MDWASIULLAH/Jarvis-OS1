"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workforceService } from "../services/workforce-service";

/**
 * Workforce queries plus the mutations the swarm API supports. Actions used to
 * be entirely absent from the UI even though SwarmManager exposed them, so the
 * Workforce Center was read-only against a fully controllable subsystem.
 */
export function useWorkforce() {
  const client = useQueryClient();
  const invalidate = () => {
    for (const key of ["workforce-agents", "workforce-communications", "workforce-status", "workforce-tasks", "workforce-activity"]) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  };

  const agents = useQuery({ queryKey: ["workforce-agents"], queryFn: workforceService.agents, refetchInterval: 10_000 });
  const communications = useQuery({ queryKey: ["workforce-communications"], queryFn: workforceService.communications, refetchInterval: 10_000 });
  const status = useQuery({ queryKey: ["workforce-status"], queryFn: workforceService.status, refetchInterval: 10_000 });
  const swarmTasks = useQuery({ queryKey: ["workforce-tasks"], queryFn: workforceService.swarmTasks, refetchInterval: 10_000 });
  const tasks = useQuery({ queryKey: ["agent-tasks"], queryFn: workforceService.tasks, refetchInterval: 10_000 });
  const activity = useQuery({ queryKey: ["workforce-activity"], queryFn: workforceService.activity, refetchInterval: 10_000 });

  const act = useMutation({
    mutationFn: ({ agentId, action }: { agentId: string; action: Parameters<typeof workforceService.act>[1] }) => workforceService.act(agentId, action),
    onSuccess: invalidate,
  });
  const assignTask = useMutation({
    mutationFn: ({ title, description }: { title: string; description?: string }) => workforceService.assignTask(title, description),
    onSuccess: invalidate,
  });
  const broadcast = useMutation({
    mutationFn: ({ senderAgentId, content }: { senderAgentId: string; content: string }) => workforceService.broadcast(senderAgentId, content),
    onSuccess: invalidate,
  });

  return {
    agents, communications, status, swarmTasks, tasks, activity, act, assignTask, broadcast,
    refreshAll: () => { void agents.refetch(); void communications.refetch(); void status.refetch(); void swarmTasks.refetch(); void tasks.refetch(); void activity.refetch(); },
  };
}
