import type { DeviceDiscoveryCandidate, DeviceFamily, DiscoveryBasis } from "./device-library";
import type { DiscoverySortOrder } from "./device-discovery-url";

export type DeviceSortLabels = {
  familyLabels: Record<DeviceFamily, string>;
  evidenceLabels: Record<DiscoveryBasis, string>;
};

/** Sort a filtered discovery lead list locally, preserving source order by default. */
export function sortDeviceDiscoveryCandidates(
  candidates: readonly DeviceDiscoveryCandidate[],
  sortOrder: DiscoverySortOrder,
  locale: string,
  labels: DeviceSortLabels,
): DeviceDiscoveryCandidate[] {
  const sorted = [...candidates];
  if (sortOrder === "catalog") return sorted;

  const collator = new Intl.Collator(locale, { sensitivity: "base", numeric: true });
  const compareStableTie = (left: DeviceDiscoveryCandidate, right: DeviceDiscoveryCandidate) => {
    const manufacturer = collator.compare(left.manufacturer, right.manufacturer);
    if (manufacturer !== 0) return manufacturer;
    const model = collator.compare(left.model, right.model);
    return model || collator.compare(left.candidate_id, right.candidate_id);
  };

  if (sortOrder === "review-date") {
    return sorted.sort((left, right) => {
      const leftDate = left.evidence_reviewed_on;
      const rightDate = right.evidence_reviewed_on;
      if (leftDate !== rightDate) {
        if (leftDate === null) return 1;
        if (rightDate === null) return -1;
        const newestFirst = rightDate.localeCompare(leftDate);
        if (newestFirst !== 0) return newestFirst;
      }
      return compareStableTie(left, right);
    });
  }

  const sortKey = (candidate: DeviceDiscoveryCandidate) => {
    if (sortOrder === "manufacturer") return candidate.manufacturer;
    if (sortOrder === "model") return candidate.model;
    if (sortOrder === "family") return labels.familyLabels[candidate.device_family];
    return labels.evidenceLabels[candidate.discovery_basis];
  };
  return sorted.sort((left, right) => {
    const primary = collator.compare(sortKey(left), sortKey(right));
    if (primary !== 0) return primary;
    return compareStableTie(left, right);
  });
}
