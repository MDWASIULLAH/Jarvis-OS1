"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { graphService } from "../services/graph-service";

/**
 * The Knowledge Graph module had no frontend at all -- it fell through to the
 * generic ModuleCenter placeholder even though /v1/graph* was fully implemented.
 */
export function useKnowledgeGraph({ label, entityType, nodeId, depth }: {
  label: string;
  entityType: string;
  nodeId?: string;
  depth: number;
}) {
  const client = useQueryClient();
  const invalidate = () => {
    for (const key of ["graph-overview", "graph-node", "graph-traverse"]) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  };

  const overview = useQuery({
    queryKey: ["graph-overview", label, entityType],
    queryFn: () => graphService.overview(label, entityType),
    refetchInterval: 20_000,
  });
  const node = useQuery({
    queryKey: ["graph-node", nodeId],
    queryFn: () => graphService.node(nodeId as string),
    enabled: Boolean(nodeId),
  });
  const traversal = useQuery({
    queryKey: ["graph-traverse", nodeId, depth],
    queryFn: () => graphService.traverse(nodeId as string, depth),
    enabled: Boolean(nodeId),
  });

  const createNode = useMutation({
    mutationFn: ({ label: nodeLabel, entityType: kind, tags }: { label: string; entityType: string; tags?: string[] }) =>
      graphService.createNode(nodeLabel, kind, tags),
    onSuccess: invalidate,
  });
  const createEdge = useMutation({
    mutationFn: ({ source, target, relationship }: { source: string; target: string; relationship: string }) =>
      graphService.createEdge(source, target, relationship),
    onSuccess: invalidate,
  });
  const deleteNode = useMutation({
    mutationFn: (id: string) => graphService.deleteNode(id),
    onSuccess: invalidate,
  });

  return {
    overview, node, traversal, createNode, createEdge, deleteNode,
    refreshAll: () => { void overview.refetch(); void node.refetch(); void traversal.refetch(); },
  };
}
