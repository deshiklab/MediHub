import type { DeviceDiscoveryCandidate } from "./device-library";

const defaultScopeLimit =
  "Discovery lead only; not installed-base prevalence, verified compatibility, supported drivers, or current availability. Physical-device connections remain disabled.";

const columns = [
  "candidate_id",
  "manufacturer",
  "model",
  "device_family",
  "discovery_basis",
  "evidence_note",
  "source_url",
  "catalog_date_metadata_recorded",
  "status",
  "compatibility_verified",
  "live_adapter_available",
  "scope_limit",
] as const;

function csvCell(value: string): string {
  const safe = /^[\s\u200B\uFEFF]*[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
}

/** Export only the explicitly allowlisted, non-connectable discovery fields. */
export function buildDeviceDiscoveryCsv(
  candidates: readonly DeviceDiscoveryCandidate[],
  scopeLimit = defaultScopeLimit,
): string {
  const rows: string[][] = [
    [...columns],
    ...candidates.map((candidate) => [
      candidate.candidate_id,
      candidate.manufacturer,
      candidate.model,
      candidate.device_family,
      candidate.discovery_basis,
      candidate.evidence_note,
      candidate.source_url ?? "",
      candidate.evidence_reviewed_on === null ? "false" : "true",
      candidate.status,
      String(candidate.compatibility_verified),
      String(candidate.live_adapter_available),
      scopeLimit,
    ]),
  ];
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}
