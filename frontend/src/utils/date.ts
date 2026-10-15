/**
 * Date utility functions for consistent timezone parsing, sorting, and formatting.
 *
 * Contract:
 * - Timestamps from the backend originate in UTC.
 * - The backend API contract represents timestamps as ISO 8601 with 'Z' (e.g. 2026-10-12T18:55:49Z).
 * - If historical or un-suffixed ISO date strings (e.g. 2026-10-04T10:13:40.407483) are encountered,
 *   we know from verified backend telemetry and DB schema that they are UTC.
 * - Formatted strings are always displayed in the browser's local timezone.
 */

export function parseDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  let str = String(dateStr).trim();
  if (!str) return null;

  // If string is an ISO date-time string without a timezone indicator (e.g. YYYY-MM-DDTHH:mm:ss.sss),
  // ECMAScript specification parses date-time strings without timezone as local time.
  // Normalize known UTC ISO timestamps without timezone to append 'Z'.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(str)) {
    str += 'Z';
  }

  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr || !String(dateStr).trim()) return '-';
  const d = parseDate(dateStr);
  if (!d) return String(dateStr);
  return d.toLocaleString();
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr || !String(dateStr).trim()) return '-';
  const d = parseDate(dateStr);
  if (!d) return String(dateStr);
  return d.toLocaleDateString();
}

export function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr || !String(dateStr).trim()) return '-';
  const d = parseDate(dateStr);
  if (!d) return String(dateStr);
  return d.toLocaleTimeString();
}

export function getTimestampMs(dateStr: string | null | undefined): number | null {
  if (!dateStr || !String(dateStr).trim()) return null;
  const d = parseDate(dateStr);
  return d ? d.getTime() : null;
}

/**
 * Deterministically sort incidents newest first based on their actual creation time:
 * 1. Valid timestamps come before missing/null/undefined/invalid timestamps.
 * 2. Newer timestamps come first (descending).
 * 3. Equal timestamps use numeric id descending as secondary tie-breaker.
 * 4. Fall back to incident_id string comparison descending if id is missing, equal, or non-numeric.
 */
export function compareIncidents(a: any, b: any): number {
  const aTime = getTimestampMs(a?.created_at);
  const bTime = getTimestampMs(b?.created_at);

  // 1. Explicit handling of missing / invalid timestamps: valid dates first, missing dates last
  if (aTime !== null && bTime === null) return -1;
  if (aTime === null && bTime !== null) return 1;

  // 2. Both timestamps valid and unequal: newest first
  if (aTime !== null && bTime !== null && aTime !== bTime) {
    return bTime - aTime;
  }

  // 3. Secondary tie-breaker: numeric id descending (if available and valid)
  const aId = typeof a?.id === 'number' ? a.id : null;
  const bId = typeof b?.id === 'number' ? b.id : null;
  if (aId !== null && bId !== null && aId !== bId) {
    return bId - aId;
  }

  // 4. Deterministic string fallback: incident_id descending
  const aCode = String(a?.incident_id || '');
  const bCode = String(b?.incident_id || '');
  return bCode.localeCompare(aCode);
}
