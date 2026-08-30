"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { missionService } from "../services/mission-service";
import type { MissionAction } from "../types";

/**
 * One hook for the whole Mission Control screen.
 *
 * The mission detail query used to live inside <MissionDetails>, so the side
 * rail (Flight recorder, Resources, Metrics) had no access to it and rendered
 * "Unavailable" for values the backend was already returning. Hoisting it here
 * lets every panel read the same cached response, and gives the header its
 * create/transition mutations.
 */
export function useMissionControl(selectedId?: string) {
  const client = useQueryClient();
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ["missions"] });
    void client.invalidateQueries({ queryKey: ["mission", selectedId] });
  };

  const missions = useQuery({ queryKey: ["missions"], queryFn: missionService.missions, refetchInterval: 15_000 });
  const detail = useQuery({
    queryKey: ["mission", selectedId],
    queryFn: () => missionService.detail(selectedId),
    enabled: Boolean(selectedId),
    refetchInterval: 10_000,
  });
  const runtime = useQuery({ queryKey: ["runtime-status"], queryFn: missionService.runtime, refetchInterval: 15_000 });
  const system = useQuery({ queryKey: ["system-status"], queryFn: missionService.system, refetchInterval: 10_000 });
  const tasks = useQuery({ queryKey: ["agent-tasks"], queryFn: missionService.tasks, refetchInterval: 10_000 });

  const create = useMutation({
    mutationFn: ({ title, description }: { title: string; description: string }) => missionService.create(title, description),
    onSuccess: invalidate,
  });
  const transition = useMutation({
    mutationFn: ({ missionId, action }: { missionId: string; action: MissionAction }) => missionService.transition(missionId, action),
    onSuccess: invalidate,
  });

  return { missions, detail, runtime, system, tasks, create, transition, refreshAll: () => { void missions.refetch(); void detail.refetch(); void runtime.refetch(); void system.refetch(); void tasks.refetch(); } };
}
