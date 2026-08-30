"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { RefreshCw, Search, ShieldCheck } from "lucide-react";
import { useSecurity } from "./hooks/use-security";
import type { EvaluationResult } from "./types";

const RISK_TONE: Record<string, string> = { low: "ok", medium: "pending", high: "bad", critical: "bad" };

export function SecurityFrameworkCenter() {
  const [auditFilter, setAuditFilter] = useState("");
  const { overview, audit, evaluate, requestApproval, decide, setTrust, refreshAll } = useSecurity(auditFilter);

  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [domain, setDomain] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [subject, setSubject] = useState("");
  const [score, setScore] = useState(0.5);

  const data = overview.data?.data;
  const domains = data?.vocabulary.domains ?? [];
  const permissionOptions = data?.vocabulary.permissions ?? [];
  const pending = (data?.approvals ?? []).filter(approval => approval.state === "pending");
  const auditRecords = audit.data?.data ?? [];

  const toggle = (permission: string) =>
    setPermissions(current => current.includes(permission) ? current.filter(item => item !== permission) : [...current, permission]);

  const runEvaluate = async () => {
    if (!title.trim() || !domain) return;
    const payload = { title: title.trim(), target: target.trim(), domain, permissions };
    setResult(await evaluate.mutateAsync(payload));
  };

  const decision = result?.report.decision;
  const risk = decision?.risk;

  return <motion.div className="security-center" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header>
      <div><span>Governance</span><h1>Security Framework</h1><p>Policies, risk assessment, approval gates, trust scores, and the tamper-evident audit trail.</p></div>
      <button onClick={refreshAll}><RefreshCw size={15} className={overview.isFetching ? "spin" : undefined}/> Refresh</button>
    </header>

    {!overview.data?.available && <p className="security-api-notice">{overview.data?.reason ?? "Checking security framework availability…"}</p>}

    <div className="security-stats">
      <div><span>Policies</span><strong>{data?.counts.policies ?? 0}</strong></div>
      <div><span>Pending approvals</span><strong>{data?.counts.pending_approvals ?? 0}</strong></div>
      <div><span>Incidents</span><strong>{data?.counts.incidents ?? 0}</strong></div>
      <div><span>Audit records</span><strong>{data?.counts.audit_records ?? 0}</strong></div>
      <div><span>Trust subjects</span><strong>{data?.trust_scores.length ?? 0}</strong></div>
      <div><span>Quarantined</span><strong>{data?.quarantined.length ?? 0}</strong></div>
    </div>

    <div className="security-layout">
      <section className="security-card">
        <h2><ShieldCheck size={15}/> Evaluate an action</h2>
        <p className="security-hint">Run a proposed action through the policy engine to see the decision, risk level, and whether it needs an approval gate — nothing is executed.</p>
        <form className="security-form" onSubmit={event => { event.preventDefault(); void runEvaluate(); }}>
          <label>Action<input value={title} onChange={event => setTitle(event.target.value)} placeholder="Install the ffmpeg binary" required/></label>
          <label>Target<input value={target} onChange={event => setTarget(event.target.value)} placeholder="C:\\tools\\ffmpeg"/></label>
          <label>Policy domain
            <select value={domain} onChange={event => setDomain(event.target.value)} required>
              <option value="">Choose a domain…</option>
              {domains.map(item => <option key={item} value={item}>{item.replace(/_/g, " ")}</option>)}
            </select>
          </label>
          <fieldset className="security-permissions">
            <legend>Permissions requested</legend>
            {permissionOptions.map(permission =>
              <label key={permission} className={permissions.includes(permission) ? "checked" : undefined}>
                <input type="checkbox" checked={permissions.includes(permission)} onChange={() => toggle(permission)}/>
                {permission}
              </label>)}
          </fieldset>
          <div className="security-form-actions">
            <button type="submit" className="primary" disabled={evaluate.isPending || !title.trim() || !domain}>{evaluate.isPending ? "Evaluating…" : "Evaluate"}</button>
            <button type="button" disabled={requestApproval.isPending || !title.trim() || !domain}
              onClick={() => requestApproval.mutate({ title: title.trim(), target: target.trim(), domain, permissions })}>
              {requestApproval.isPending ? "Requesting…" : "Request approval"}
            </button>
          </div>
        </form>

        {evaluate.isError && <p className="security-api-notice">Evaluation failed. Check the domain and permission values against the backend vocabulary.</p>}

        {result && <div className="security-verdict">
          <div className="security-verdict-head">
            <span className={`studio-tag ${decision?.allowed ? "ok" : "bad"}`}>{decision?.allowed ? "allowed" : "blocked"}</span>
            <span className={`studio-tag ${RISK_TONE[risk?.level ?? ""] ?? "pending"}`}>risk: {risk?.level ?? "unknown"}</span>
            {result.report.approval && <span className="studio-tag pending">approval required</span>}
          </div>
          {decision?.rationale?.length ? <ul className="security-rationale">{decision.rationale.map((line, index) =>
            <li key={`${index}-${line}`}>{line}</li>)}</ul> : null}
          {risk?.rationale?.length ? <ul className="security-rationale">{risk.rationale.map((line, index) =>
            <li key={`${index}-${line}`}>{line}</li>)}</ul> : null}
          {result.threats.length ? <ul className="security-threats">{result.threats.map((threat, index) =>
            <li key={threat.threat_id ?? index}><strong>{threat.category ?? "threat"}</strong><span>{threat.detail ?? threat.severity ?? ""}</span></li>)}</ul>
            : <p className="security-hint">No threats detected for this action.</p>}
        </div>}
      </section>

      <aside className="security-side">
        <section className="security-card">
          <h2>Approval queue</h2>
          {pending.length ? <ul className="security-approvals">{pending.map(approval =>
            <li key={approval.approval_id}>
              <div><strong>{approval.action_id.slice(0, 8)}</strong><em>requested by {approval.requested_by}</em></div>
              <div className="security-approval-actions">
                <button className="primary" disabled={decide.isPending} onClick={() => decide.mutate({ approvalId: approval.approval_id, granted: true })}>Grant</button>
                <button className="danger" disabled={decide.isPending} onClick={() => decide.mutate({ approvalId: approval.approval_id, granted: false })}>Deny</button>
              </div>
            </li>)}</ul>
            : <p className="security-hint">No approvals are waiting. High-risk actions land here when the policy engine gates them.</p>}
        </section>

        <section className="security-card">
          <h2>Policies</h2>
          <ul className="security-policies">{(data?.policies ?? []).map(policy =>
            <li key={policy.policy_id}>
              <strong>{policy.domain.replace(/_/g, " ")}</strong>
              <span className={`studio-tag ${policy.enabled ? "ok" : "bad"}`}>{policy.enabled ? "enabled" : "disabled"}</span>
              <em>max risk {policy.max_risk} · {policy.allowed_permissions.length} permissions</em>
            </li>)}</ul>
          {!data?.policies.length && <p className="security-hint">No policies are registered.</p>}
        </section>

        <section className="security-card">
          <h2>Trust scores</h2>
          <form className="security-form security-trust" onSubmit={event => {
            event.preventDefault();
            if (!subject.trim()) return;
            setTrust.mutate({ subjectId: subject.trim(), score });
            setSubject("");
          }}>
            <input value={subject} onChange={event => setSubject(event.target.value)} placeholder="Subject id (agent, plugin, host)"/>
            <input type="range" min={0} max={1} step={0.05} value={score} onChange={event => setScore(Number(event.target.value))} aria-label="Trust score"/>
            <span>{Math.round(score * 100)}%</span>
            <button type="submit" className="primary" disabled={setTrust.isPending || !subject.trim()}>Set</button>
          </form>
          {data?.trust_scores.length ? <ul className="security-trust-list">{data.trust_scores.map(item =>
            <li key={item.subject_id}>
              <strong>{item.subject_id}</strong>
              <div className="graph-bar"><span style={{ width: `${item.score * 100}%` }}/></div>
              <em>{Math.round(item.score * 100)}%</em>
            </li>)}</ul>
            : <p className="security-hint">No trust scores recorded yet.</p>}
        </section>

        <section className="security-card">
          <h2>Incidents</h2>
          {data?.incidents.length ? <ul className="security-incidents">{data.incidents.map(incident =>
            <li key={incident.incident_id}>
              <strong>{incident.summary ?? incident.incident_id}</strong>
              <span className={`studio-tag ${RISK_TONE[incident.severity ?? ""] ?? "pending"}`}>{incident.severity ?? "unknown"}</span>
              {incident.detail && <em>{incident.detail}</em>}
            </li>)}</ul>
            : <p className="security-hint">No security incidents recorded.</p>}
        </section>
      </aside>
    </div>

    <section className="security-card security-audit">
      <header className="security-toolbar">
        <h2>Audit trail</h2>
        <label><Search size={14}/><input value={auditFilter} onChange={event => setAuditFilter(event.target.value)} placeholder="Filter audit records"/></label>
        <span>{auditRecords.length}</span>
      </header>
      {auditRecords.length ? <ul className="security-audit-list">{auditRecords.slice(-60).reverse().map(record =>
        <li key={record.record_id}>
          <time>{record.timestamp ? new Date(record.timestamp).toLocaleTimeString() : "—"}</time>
          <strong>{record.event.replace(/_/g, " ")}</strong>
          <span>{record.detail ?? ""}</span>
        </li>)}</ul>
        : <p className="security-hint">The audit trail is empty. Evaluate an action above and it will be recorded here.</p>}
    </section>
  </motion.div>;
}
