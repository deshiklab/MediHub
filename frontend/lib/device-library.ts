export const deviceFamilies = [
  "immunoassay",
  "hematology",
  "clinical_chemistry",
  "urinalysis",
  "electrolyte",
  "coagulation",
  "hba1c",
  "blood_gas",
  "point_of_care",
  "other",
] as const;

export const discoveryBases = [
  "user_selected_target",
  "bangladesh_seller_listing",
  "bangladesh_supplier_category",
  "bangladesh_facility_self_report",
] as const;

export type DeviceFamily = (typeof deviceFamilies)[number];
export type DiscoveryBasis = (typeof discoveryBases)[number];

export type DeviceDiscoveryCandidate = {
  candidate_id: string;
  manufacturer: string;
  model: string;
  device_family: DeviceFamily;
  discovery_basis: DiscoveryBasis;
  evidence_note: string;
  source_url: string | null;
  evidence_reviewed_on: string | null;
  status: "discovery_only";
  compatibility_verified: false;
  live_adapter_available: false;
};

export type DeviceAdapter = {
  adapter_id: "medihub.synthetic-device" | "offline-astm-e1394-parser-scaffold";
  label: string;
  status: "available_for_local_demo" | "parser_only_no_transport_or_model_profile";
  connects_to_physical_device: false;
};

export type DeviceLibrary = {
  mode: "synthetic_only";
  country_focus: "BD";
  candidate_count: number;
  installed_base_ranked: false;
  physical_device_connections_enabled: false;
  endpoint_fields_supported: false;
  credential_fields_supported: false;
  device_adapters: DeviceAdapter[];
  candidates: DeviceDiscoveryCandidate[];
};

const libraryKeys = [
  "mode",
  "country_focus",
  "candidate_count",
  "installed_base_ranked",
  "physical_device_connections_enabled",
  "endpoint_fields_supported",
  "credential_fields_supported",
  "device_adapters",
  "candidates",
] as const;

const candidateKeys = [
  "candidate_id",
  "manufacturer",
  "model",
  "device_family",
  "discovery_basis",
  "evidence_note",
  "source_url",
  "evidence_reviewed_on",
  "status",
  "compatibility_verified",
  "live_adapter_available",
] as const;

const adapterKeys = ["adapter_id", "label", "status", "connects_to_physical_device"] as const;

const safeAdapterStatuses = {
  "medihub.synthetic-device": "available_for_local_demo",
  "offline-astm-e1394-parser-scaffold": "parser_only_no_transport_or_model_profile",
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(value: Record<string, unknown>, allowed: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

function isNonEmptyString(value: unknown, maxLength: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= maxLength;
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (year < 1 || month < 1 || month > 12) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysByMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= daysByMonth[month - 1];
}

function isSafeSourceUrl(value: unknown): value is string | null {
  if (value === null) return true;
  if (typeof value !== "string" || value.length > 2048) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname) && !url.username && !url.password;
  } catch {
    return false;
  }
}

function isCandidate(value: unknown): value is DeviceDiscoveryCandidate {
  if (!isRecord(value) || !hasOnlyKeys(value, candidateKeys)) return false;
  const sourceUrl = value.source_url;
  const reviewDate = value.evidence_reviewed_on;
  return (
    isNonEmptyString(value.candidate_id, 64)
    && isNonEmptyString(value.manufacturer, 80)
    && isNonEmptyString(value.model, 80)
    && typeof value.device_family === "string"
    && deviceFamilies.includes(value.device_family as DeviceFamily)
    && typeof value.discovery_basis === "string"
    && discoveryBases.includes(value.discovery_basis as DiscoveryBasis)
    && isNonEmptyString(value.evidence_note, 180)
    && isSafeSourceUrl(sourceUrl)
    && (reviewDate === null || isIsoDate(reviewDate))
    && value.status === "discovery_only"
    && value.compatibility_verified === false
    && value.live_adapter_available === false
  );
}

function isSafeAdapter(value: unknown): value is DeviceAdapter {
  if (!isRecord(value) || !hasOnlyKeys(value, adapterKeys)) return false;
  if (
    typeof value.adapter_id !== "string"
    || !Object.prototype.hasOwnProperty.call(safeAdapterStatuses, value.adapter_id)
  ) {
    return false;
  }
  const expectedStatus = safeAdapterStatuses[value.adapter_id as keyof typeof safeAdapterStatuses];
  return (
    isNonEmptyString(value.label, 120)
    && value.status === expectedStatus
    && value.connects_to_physical_device === false
  );
}

/** Parse only the reviewed, non-connectable Bangladesh discovery-library response. */
export function parseDeviceLibrary(value: unknown): DeviceLibrary | null {
  if (!isRecord(value) || !hasOnlyKeys(value, libraryKeys)) return null;
  if (!Array.isArray(value.candidates) || !Array.isArray(value.device_adapters)) return null;
  if (
    value.mode !== "synthetic_only"
    || value.country_focus !== "BD"
    || value.installed_base_ranked !== false
    || value.physical_device_connections_enabled !== false
    || value.endpoint_fields_supported !== false
    || value.credential_fields_supported !== false
    || !Number.isInteger(value.candidate_count)
    || value.candidate_count !== value.candidates.length
    || value.device_adapters.length !== Object.keys(safeAdapterStatuses).length
    || !value.device_adapters.every(isSafeAdapter)
  ) {
    return null;
  }

  const adapterIds = value.device_adapters.map((adapter) => (adapter as DeviceAdapter).adapter_id);
  if (new Set(adapterIds).size !== adapterIds.length) return null;

  const candidates: DeviceDiscoveryCandidate[] = [];
  const candidateIds = new Set<string>();
  for (const candidate of value.candidates) {
    if (!isCandidate(candidate) || candidateIds.has(candidate.candidate_id)) return null;
    candidateIds.add(candidate.candidate_id);
    candidates.push(candidate);
  }

  return {
    mode: "synthetic_only",
    country_focus: "BD",
    candidate_count: value.candidate_count as number,
    installed_base_ranked: false,
    physical_device_connections_enabled: false,
    endpoint_fields_supported: false,
    credential_fields_supported: false,
    device_adapters: value.device_adapters as DeviceAdapter[],
    candidates,
  };
}
