"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectService } from "../services/project-service";

/**
 * The Studio used to fetch only the project list and then render "Unavailable"
 * for everything else. Every /v1/company/* surface is now wired, including the
 * three mutations (create project, add department, request review).
 */
export function useDevelopmentStudio(selectedId?: string) {
  const client = useQueryClient();
  const invalidate = () => {
    for (const key of ["projects", "project-dashboard", "company-departments", "company-tasks"]) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  };

  const projects = useQuery({ queryKey: ["projects"], queryFn: projectService.projects, refetchInterval: 10_000 });
  const dashboard = useQuery({
    queryKey: ["project-dashboard", selectedId],
    queryFn: () => projectService.dashboard(selectedId as string),
    enabled: Boolean(selectedId),
    refetchInterval: 10_000,
  });
  const departments = useQuery({ queryKey: ["company-departments"], queryFn: projectService.departments, refetchInterval: 15_000 });
  const companyTasks = useQuery({ queryKey: ["company-tasks"], queryFn: projectService.companyTasks, refetchInterval: 15_000 });
  // The role/department/review vocabulary is static for a given build, so it is
  // fetched once and reused to populate the selects instead of being hardcoded.
  const vocabulary = useQuery({ queryKey: ["company-roles"], queryFn: projectService.vocabulary, staleTime: 5 * 60_000 });
  const goals = useQuery({ queryKey: ["goals"], queryFn: projectService.goals, refetchInterval: 15_000 });
  const tasks = useQuery({ queryKey: ["agent-tasks"], queryFn: projectService.tasks, refetchInterval: 15_000 });

  const create = useMutation({
    mutationFn: ({ title, goal, priority }: { title: string; goal: string; priority?: number }) => projectService.create(title, goal, priority),
    onSuccess: invalidate,
  });
  const addDepartment = useMutation({
    mutationFn: ({ projectId, kind, roles }: { projectId: string; kind: string; roles?: string[] }) => projectService.addDepartment(projectId, kind, roles),
    onSuccess: invalidate,
  });
  const requestReview = useMutation({
    mutationFn: ({ projectId, kind }: { projectId: string; kind: string }) => projectService.requestReview(projectId, kind),
    onSuccess: invalidate,
  });

  return {
    projects, dashboard, departments, companyTasks, vocabulary, goals, tasks,
    create, addDepartment, requestReview,
    refreshAll: () => {
      void projects.refetch(); void dashboard.refetch(); void departments.refetch();
      void companyTasks.refetch(); void goals.refetch(); void tasks.refetch();
    },
  };
}
