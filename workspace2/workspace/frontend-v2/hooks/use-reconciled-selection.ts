"use client";
import { useEffect, useRef } from "react";

/**
 * Drop a selected id once the authoritative list says it no longer exists.
 *
 * Projects, missions and agents all live in plain in-memory dicts on the backend
 * (`CompanyRegistry._projects`, `MissionRegistry._missions`), so restarting the
 * backend invalidates every id the UI is holding. The detail queries poll on a
 * 10-second interval, which turned one dead id into a permanent 404 loop in the
 * console -- `GET /v1/company/projects/d931d7b2-… → 404`, six times a minute --
 * behind a panel stuck on "Unavailable" with no way to recover but a hard reload.
 *
 * Reconciling against the list query fixes both halves: the poll stops, and the
 * panel falls back to its real "nothing selected" state.
 *
 * @param ready Only reconcile when the list genuinely loaded. A list that failed
 *   because the backend is briefly down must not wipe a still-valid selection --
 *   that would silently deselect the user's work during a restart.
 */
export function useReconciledSelection(
  selectedId: string | undefined,
  ids: string[],
  ready: boolean,
  clear: () => void
): void {
  // Held in a ref so an inline `() => selectProject(undefined)` does not make
  // this effect re-run on every render.
  const clearRef = useRef(clear);
  clearRef.current = clear;

  // A boolean, so the effect is keyed on the answer rather than on the array
  // identity the list query hands back fresh on every poll.
  const missing = Boolean(selectedId) && !ids.includes(selectedId as string);

  useEffect(() => {
    if (ready && missing) clearRef.current();
  }, [ready, missing]);
}
