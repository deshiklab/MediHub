import {
  deviceFamilies,
  discoveryBases,
  type DeviceFamily,
  type DiscoveryBasis,
} from "./device-library";

export type DiscoveryFilters = {
  search: string;
  familyFilter: DeviceFamily | "";
  evidenceFilter: DiscoveryBasis | "";
  dateFilter: "" | "recorded" | "not-recorded";
};

/** Read only bounded search text and allowlisted filter values from a shared URL. */
export function readSharedFilters(searchParams: string): DiscoveryFilters {
  const params = new URLSearchParams(searchParams);
  const family = params.get("family");
  const basis = params.get("basis");
  const date = params.get("catalogDate");
  return {
    search: (params.get("q") ?? "").slice(0, 100).trim(),
    familyFilter: deviceFamilies.includes(family as DeviceFamily) ? family as DeviceFamily : "",
    evidenceFilter: discoveryBases.includes(basis as DiscoveryBasis) ? basis as DiscoveryBasis : "",
    dateFilter: date === "recorded" || date === "not-recorded" ? date : "",
  };
}

/** Build a URL that contains only the current search text and valid catalog filters. */
export function shareableFilterUrl(currentUrl: URL, filters: DiscoveryFilters): URL {
  const url = new URL(currentUrl.toString());
  const params = new URLSearchParams();
  const query = filters.search.trim().slice(0, 100);
  if (query) params.set("q", query);
  if (filters.familyFilter) params.set("family", filters.familyFilter);
  if (filters.evidenceFilter) params.set("basis", filters.evidenceFilter);
  if (filters.dateFilter) params.set("catalogDate", filters.dateFilter);
  url.search = params.toString();
  return url;
}
