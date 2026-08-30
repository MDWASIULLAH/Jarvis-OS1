"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { operationsService } from "./services/operations-service";

/**
 * Search Intelligence health, measured by running a real query.
 *
 * The slot used to claim search analytics "require a public Search Intelligence
 * operational endpoint". GET /v1/search is public and live, so this probes it on
 * demand — a dashboard should not fire outbound web requests on every poll.
 */
export function SearchProbe() {
  const [query, setQuery] = useState("who is Ada Lovelace");
  const [elapsed, setElapsed] = useState<number | null>(null);

  const probe = useMutation({
    mutationFn: async (text: string) => {
      const started = performance.now();
      const result = await operationsService.searchProbe(text);
      setElapsed(Math.round(performance.now() - started));
      return result;
    },
  });

  return <section className="operations-card">
    <h2>Search Intelligence</h2>
    <form className="search-probe" onSubmit={event => { event.preventDefault(); if (query.trim()) probe.mutate(query.trim()); }}>
      <label>
        <Search size={14}/>
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Ask the search provider something"/>
      </label>
      <button type="submit" disabled={probe.isPending || !query.trim()}>{probe.isPending ? "Probing…" : "Run probe"}</button>
    </form>
    <div className="analytics-grid search-probe-grid">
      <div><span>Provider</span><strong title={probe.data?.engine ?? ""}>{probe.data?.engine?.replace(/_/g, " ") ?? "Not probed"}</strong></div>
      <div><span>Round trip</span><strong>{elapsed === null ? "—" : `${elapsed} ms`}</strong></div>
      <div><span>Answered</span><strong>{probe.data ? (probe.data.answer ? "Yes" : "No result") : "—"}</strong></div>
    </div>
    {probe.isError && <p className="operations-unavailable">The search provider did not answer. It needs outbound network access.</p>}
    {probe.data?.answer && <p className="operations-unavailable search-probe-answer">{probe.data.answer}</p>}
  </section>;
}
