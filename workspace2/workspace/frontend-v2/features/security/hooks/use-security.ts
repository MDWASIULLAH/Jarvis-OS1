"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { securityService, type EvaluateInput } from "../services/security-service";

/**
 * Security Framework queries and mutations. Previously the module rendered the
 * generic placeholder even though the whole policy/approval/audit tier existed.
 */
export function useSecurity(auditFilter = "") {
  const client = useQueryClient();
  const invalidate = () => {
    for (const key of ["security-overview", "security-audit"]) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  };

  const overview = useQuery({ queryKey: ["security-overview"], queryFn: securityService.overview, refetchInterval: 15_000 });
  const audit = useQuery({ queryKey: ["security-audit", auditFilter], queryFn: () => securityService.audit(auditFilter), refetchInterval: 15_000 });

  const evaluate = useMutation({ mutationFn: (input: EvaluateInput) => securityService.evaluate(input), onSuccess: invalidate });
  const requestApproval = useMutation({ mutationFn: (input: EvaluateInput) => securityService.requestApproval(input), onSuccess: invalidate });
  const decide = useMutation({
    mutationFn: ({ approvalId, granted }: { approvalId: string; granted: boolean }) => securityService.decide(approvalId, granted),
    onSuccess: invalidate,
  });
  const setTrust = useMutation({
    mutationFn: ({ subjectId, score, rationale }: { subjectId: string; score: number; rationale?: string }) => securityService.setTrust(subjectId, score, rationale),
    onSuccess: invalidate,
  });

  return {
    overview, audit, evaluate, requestApproval, decide, setTrust,
    refreshAll: () => { void overview.refetch(); void audit.refetch(); },
  };
}
