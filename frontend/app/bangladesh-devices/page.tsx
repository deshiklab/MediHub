"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  deviceFamilies,
  discoveryBases,
  parseDeviceLibrary,
  type DeviceFamily,
  type DeviceLibrary,
  type DiscoveryBasis,
} from "@/lib/device-library";
import { buildDeviceDiscoveryCsv } from "@/lib/device-library-csv";
import { sortDeviceDiscoveryCandidates } from "@/lib/device-library-sort";
import {
  discoverySortOrders,
  readSharedFilters,
  shareableFilterUrl,
  type DiscoverySortOrder,
} from "@/lib/device-discovery-url";

type Language = "en" | "bn";
type CatalogDateFilter = "" | "recorded" | "not-recorded";

const copy = {
  en: {
    language: "Interface language",
    navLabel: "MediHub pages",
    operations: "Operations",
    discovery: "Bangladesh device discovery",
    management: "Device management",
    eyebrow: "BANGLADESH DEVICE DISCOVERY",
    title: "Browse device discovery leads",
    description: "Search the Bangladesh-oriented catalog by device family, evidence basis, and available catalog metadata.",
    scopeLabel: "Discovery leads only.",
    scopeCopy: "These records are not installed-base estimates, verified compatibility, supported drivers, or proof of current market availability. Physical-device connections remain disabled.",
    filtersTitle: "Search and filter",
    search: "Search manufacturer, model, family, or evidence note",
    searchPlaceholder: "For example: Mindray or hematology",
    family: "Device family",
    allFamilies: "All device families",
    evidence: "Evidence basis",
    allEvidence: "All evidence bases",
    catalogDate: "Catalog date metadata",
    sortResults: "Sort results",
    catalogOrder: "Catalog order",
    manufacturerOrder: "Manufacturer A–Z",
    modelOrder: "Model A–Z",
    familyOrder: "Device family A–Z",
    evidenceOrder: "Evidence basis A–Z",
    anyCatalogDate: "Any metadata status",
    dateRecorded: "Date metadata recorded",
    dateNotRecorded: "No date metadata recorded",
    dateHint: "A recorded catalog date is metadata only. It does not establish claim freshness, current availability, compatibility, or prevalence.",
    clearFilters: "Clear filters",
    shareHint: "The share link includes your search text and selected filter/sort choices in the URL. Share only if you're comfortable sharing those values; no device connection is made.",
    copyShareLink: "Copy filtered-view link",
    shareCopied: "Filtered-view link copied. It includes only search/filter/sort settings; no catalog data was uploaded.",
    shareFailed: "Could not copy the link. The address bar still shows the shareable filtered view.",
    showing: "Showing {shown} of {total} discovery leads",
    resultsTitle: "Discovery leads",
    loading: "Loading the Bangladesh discovery catalog…",
    unavailable: "The discovery catalog is unavailable or outside the approved synthetic-only scope. No device connection has been attempted.",
    noResults: "No discovery leads match this search and filter combination.",
    exportCsv: "Export filtered leads CSV",
    csvScopeLimit: "Discovery lead only; not installed-base prevalence, verified compatibility, supported drivers, or current availability. Physical-device connections remain disabled.",
    exportedCsv: "Exported {count} visible discovery leads to CSV. No exact catalog dates or survey responses were included.",
    exportUnavailable: "CSV export is unavailable in this browser.",
    discoveryOnly: "Discovery only",
    evidenceNote: "Evidence note",
    sourceLink: "Open public source",
    sourceUnavailable: "No public source link recorded",
    dateStatus: "Catalog date metadata",
    datePresent: "Recorded",
    dateAbsent: "Not recorded",
    familyLabels: {
      immunoassay: "Immunoassay",
      hematology: "Hematology / CBC",
      clinical_chemistry: "Clinical chemistry",
      urinalysis: "Urinalysis",
      electrolyte: "Electrolyte",
      coagulation: "Coagulation",
      hba1c: "HbA1c",
      blood_gas: "Blood gas",
      point_of_care: "Point of care",
      other: "Other",
    } satisfies Record<DeviceFamily, string>,
    evidenceLabels: {
      user_selected_target: "User-selected target",
      bangladesh_seller_listing: "Bangladesh seller listing",
      bangladesh_supplier_category: "Bangladesh supplier-category lead",
      bangladesh_facility_self_report: "Bangladesh facility self-report",
    } satisfies Record<DiscoveryBasis, string>,
    footer: "MediHub · Local synthetic demonstration · No external network delivery",
  },
  bn: {
    language: "ইন্টারফেসের ভাষা",
    navLabel: "MediHub-এর পৃষ্ঠাগুলো",
    operations: "কার্যক্রম",
    discovery: "বাংলাদেশে ডিভাইস অনুসন্ধান",
    management: "ডিভাইস ব্যবস্থাপনা",
    eyebrow: "বাংলাদেশে ডিভাইস অনুসন্ধান",
    title: "ডিভাইস অনুসন্ধানের সূত্র দেখুন",
    description: "ডিভাইসের ধরন, তথ্যের ভিত্তি এবং ক্যাটালগের তারিখ-সংক্রান্ত মেটাডেটা দিয়ে বাংলাদেশকেন্দ্রিক ক্যাটালগ খুঁজুন।",
    scopeLabel: "এগুলো শুধু অনুসন্ধানের সূত্র।",
    scopeCopy: "এই নথিগুলো স্থাপিত ডিভাইসের সংখ্যা, যাচাইকৃত সামঞ্জস্য, সমর্থিত ড্রাইভার বা বর্তমান বাজারে প্রাপ্যতার প্রমাণ নয়। বাস্তব ডিভাইসের সংযোগ বন্ধ রয়েছে।",
    filtersTitle: "খুঁজুন ও ফিল্টার করুন",
    search: "প্রস্তুতকারক, মডেল, ধরন বা তথ্যের নোট দিয়ে খুঁজুন",
    searchPlaceholder: "যেমন: Mindray বা hematology",
    family: "ডিভাইসের ধরন",
    allFamilies: "সব ধরনের ডিভাইস",
    evidence: "তথ্যের ভিত্তি",
    allEvidence: "সব তথ্যের ভিত্তি",
    catalogDate: "ক্যাটালগের তারিখ-সংক্রান্ত মেটাডেটা",
    sortResults: "ফলাফল সাজান",
    catalogOrder: "ক্যাটালগে থাকা ক্রম",
    manufacturerOrder: "প্রস্তুতকারক A–Z",
    modelOrder: "মডেল A–Z",
    familyOrder: "ডিভাইসের ধরন A–Z",
    evidenceOrder: "তথ্যের ভিত্তি A–Z",
    anyCatalogDate: "যেকোনো মেটাডেটা অবস্থা",
    dateRecorded: "তারিখের মেটাডেটা আছে",
    dateNotRecorded: "তারিখের মেটাডেটা নেই",
    dateHint: "ক্যাটালগে তারিখ থাকলেও তা শুধু মেটাডেটা। এতে তথ্যের সাম্প্রতিকতা, বর্তমান প্রাপ্যতা, সামঞ্জস্য বা বাজারে প্রচলন প্রমাণিত হয় না।",
    clearFilters: "ফিল্টার মুছুন",
    shareHint: "শেয়ার লিংকে সার্চের লেখা ও নির্বাচিত ফিল্টার/সাজানোর ক্রম URL-এ থাকবে। এসব মান শেয়ার করতে স্বচ্ছন্দ হলেই লিংকটি শেয়ার করুন; কোনো ডিভাইস সংযোগ করা হয় না।",
    copyShareLink: "ফিল্টার করা ভিউয়ের লিংক কপি করুন",
    shareCopied: "ফিল্টার করা ভিউয়ের লিংক কপি হয়েছে। এতে শুধু সার্চ/ফিল্টার/সাজানোর মান আছে; ক্যাটালগের তথ্য আপলোড হয়নি।",
    shareFailed: "লিংক কপি করা যায়নি। ঠিকানার বারে শেয়ারযোগ্য ফিল্টার করা ভিউটি রয়েছে।",
    showing: "{total}টি অনুসন্ধান-সূত্রের মধ্যে {shown}টি দেখানো হচ্ছে",
    resultsTitle: "ডিভাইস অনুসন্ধানের সূত্র",
    loading: "বাংলাদেশি ডিভাইস অনুসন্ধানের ক্যাটালগ লোড হচ্ছে…",
    unavailable: "অনুসন্ধানের ক্যাটালগ পাওয়া যাচ্ছে না অথবা অনুমোদিত শুধু-সিন্থেটিক সীমার বাইরে। কোনো ডিভাইসের সঙ্গে সংযোগের চেষ্টা করা হয়নি।",
    noResults: "এই অনুসন্ধান ও ফিল্টারে কোনো সূত্র মেলেনি।",
    exportCsv: "ফিল্টার করা সূত্রের CSV রপ্তানি করুন",
    csvScopeLimit: "শুধু অনুসন্ধানের সূত্র; স্থাপিত ডিভাইসের প্রচলন, যাচাইকৃত সামঞ্জস্য, সমর্থিত ড্রাইভার বা বর্তমান প্রাপ্যতার প্রমাণ নয়। বাস্তব ডিভাইসের সংযোগ বন্ধ।",
    exportedCsv: "দেখানো {count}টি ডিভাইস-সূত্র CSV-তে রপ্তানি হয়েছে। কোনো নির্দিষ্ট ক্যাটালগ-তারিখ বা জরিপের উত্তর যোগ করা হয়নি।",
    exportUnavailable: "এই ব্রাউজারে CSV রপ্তানি করা যাচ্ছে না।",
    discoveryOnly: "শুধু অনুসন্ধানের সূত্র",
    evidenceNote: "তথ্যের নোট",
    sourceLink: "প্রকাশ্য সূত্র খুলুন",
    sourceUnavailable: "প্রকাশ্য সূত্রের লিংক নথিভুক্ত নেই",
    dateStatus: "ক্যাটালগের তারিখ-সংক্রান্ত মেটাডেটা",
    datePresent: "নথিভুক্ত আছে",
    dateAbsent: "নথিভুক্ত নেই",
    familyLabels: {
      immunoassay: "ইমিউনোঅ্যাসে",
      hematology: "হেমাটোলজি / CBC",
      clinical_chemistry: "ক্লিনিক্যাল কেমিস্ট্রি",
      urinalysis: "মূত্র বিশ্লেষণ",
      electrolyte: "ইলেক্ট্রোলাইট",
      coagulation: "রক্ত জমাট পরীক্ষা",
      hba1c: "HbA1c",
      blood_gas: "রক্তের গ্যাস",
      point_of_care: "পয়েন্ট-অফ-কেয়ার",
      other: "অন্যান্য",
    } satisfies Record<DeviceFamily, string>,
    evidenceLabels: {
      user_selected_target: "ব্যবহারকারীর নির্বাচিত লক্ষ্য",
      bangladesh_seller_listing: "বাংলাদেশি বিক্রেতার তালিকা",
      bangladesh_supplier_category: "বাংলাদেশি সরবরাহকারী বিভাগের সূত্র",
      bangladesh_facility_self_report: "বাংলাদেশি প্রতিষ্ঠানের স্ব-প্রতিবেদন",
    } satisfies Record<DiscoveryBasis, string>,
    footer: "MediHub · স্থানীয় সিন্থেটিক প্রদর্শনী · বাহ্যিক নেটওয়ার্কে ডেলিভারি নেই",
  },
} satisfies Record<Language, {
  language: string;
  navLabel: string;
  operations: string;
  discovery: string;
  management: string;
  eyebrow: string;
  title: string;
  description: string;
  scopeLabel: string;
  scopeCopy: string;
  filtersTitle: string;
  search: string;
  searchPlaceholder: string;
  family: string;
  allFamilies: string;
  evidence: string;
  allEvidence: string;
  catalogDate: string;
  sortResults: string;
  catalogOrder: string;
  manufacturerOrder: string;
  modelOrder: string;
  familyOrder: string;
  evidenceOrder: string;
  anyCatalogDate: string;
  dateRecorded: string;
  dateNotRecorded: string;
  dateHint: string;
  clearFilters: string;
  shareHint: string;
  copyShareLink: string;
  shareCopied: string;
  shareFailed: string;
  showing: string;
  resultsTitle: string;
  loading: string;
  unavailable: string;
  noResults: string;
  exportCsv: string;
  csvScopeLimit: string;
  exportedCsv: string;
  exportUnavailable: string;
  discoveryOnly: string;
  evidenceNote: string;
  sourceLink: string;
  sourceUnavailable: string;
  dateStatus: string;
  datePresent: string;
  dateAbsent: string;
  familyLabels: Record<DeviceFamily, string>;
  evidenceLabels: Record<DiscoveryBasis, string>;
  footer: string;
}>;

function normalizeSearch(value: string, language: Language): string {
  return value.normalize("NFKC").toLocaleLowerCase(language === "bn" ? "bn-BD" : "en").trim();
}

export default function BangladeshDevicesPage() {
  const [language, setLanguage] = useState<Language>("en");
  const [preferenceLoaded, setPreferenceLoaded] = useState(false);
  const [library, setLibrary] = useState<DeviceLibrary | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [search, setSearch] = useState("");
  const [familyFilter, setFamilyFilter] = useState<DeviceFamily | "">("");
  const [evidenceFilter, setEvidenceFilter] = useState<DiscoveryBasis | "">("");
  const [dateFilter, setDateFilter] = useState<CatalogDateFilter>("");
  const [sortOrder, setSortOrder] = useState<DiscoverySortOrder>("catalog");
  const [filtersLoaded, setFiltersLoaded] = useState(false);
  const [shareStatus, setShareStatus] = useState<"copied" | "error" | null>(null);
  const [exportStatus, setExportStatus] = useState<{ kind: "success"; count: number } | { kind: "error" } | null>(null);
  const text = copy[language];
  const number = new Intl.NumberFormat(language === "bn" ? "bn-BD" : "en");
  const sortLabels: Record<DiscoverySortOrder, string> = {
    catalog: text.catalogOrder,
    manufacturer: text.manufacturerOrder,
    model: text.modelOrder,
    family: text.familyOrder,
    evidence: text.evidenceOrder,
  };

  useEffect(() => {
    try {
      setLanguage(window.localStorage.getItem("medihub-language") === "bn" ? "bn" : "en");
    } catch {
      setLanguage("en");
    }
    setPreferenceLoaded(true);
  }, []);

  useEffect(() => {
    const sharedFilters = readSharedFilters(window.location.search);
    setSearch(sharedFilters.search);
    setFamilyFilter(sharedFilters.familyFilter);
    setEvidenceFilter(sharedFilters.evidenceFilter);
    setDateFilter(sharedFilters.dateFilter);
    setSortOrder(sharedFilters.sortOrder);
    setFiltersLoaded(true);
  }, []);

  useEffect(() => {
    if (!filtersLoaded) return;
    const nextUrl = shareableFilterUrl(new URL(window.location.href), {
      search,
      familyFilter,
      evidenceFilter,
      dateFilter,
      sortOrder,
    });
    const nextLocation = `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`;
    const currentLocation = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (nextLocation !== currentLocation) {
      window.history.replaceState(window.history.state, "", nextLocation);
    }
  }, [dateFilter, evidenceFilter, familyFilter, filtersLoaded, search, sortOrder]);

  useEffect(() => {
    if (!preferenceLoaded) return;
    document.documentElement.lang = language;
    try {
      window.localStorage.setItem("medihub-language", language);
    } catch {
      // The language selector remains usable when storage is disabled.
    }
  }, [language, preferenceLoaded]);

  useEffect(() => {
    let active = true;
    const loadLibrary = async () => {
      try {
        const response = await fetch("/api/management/device-library", { cache: "no-store" });
        if (!response.ok) throw new Error("discovery catalog unavailable");
        const data = parseDeviceLibrary(await response.json());
        if (!data) throw new Error("discovery catalog outside approved scope");
        if (active) {
          setLibrary(data);
          setUnavailable(false);
        }
      } catch {
        if (active) {
          setLibrary(null);
          setUnavailable(true);
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    void loadLibrary();
    return () => {
      active = false;
    };
  }, []);

  const filteredCandidates = useMemo(() => {
    if (!library) return [];
    const query = normalizeSearch(search, language);
    const filtered = library.candidates.filter((candidate) => {
      if (familyFilter && candidate.device_family !== familyFilter) return false;
      if (evidenceFilter && candidate.discovery_basis !== evidenceFilter) return false;
      if (dateFilter === "recorded" && candidate.evidence_reviewed_on === null) return false;
      if (dateFilter === "not-recorded" && candidate.evidence_reviewed_on !== null) return false;
      if (!query) return true;
      const searchText = normalizeSearch([
        candidate.manufacturer,
        candidate.model,
        candidate.device_family.replaceAll("_", " "),
        text.familyLabels[candidate.device_family],
        text.evidenceLabels[candidate.discovery_basis],
        candidate.evidence_note,
      ].join(" "), language);
      return searchText.includes(query);
    });
    return sortDeviceDiscoveryCandidates(
      filtered,
      sortOrder,
      language === "bn" ? "bn-BD" : "en",
      text,
    );
  }, [dateFilter, evidenceFilter, familyFilter, language, library, search, sortOrder, text]);

  const hasFilters = Boolean(search.trim() || familyFilter || evidenceFilter || dateFilter || sortOrder !== "catalog");
  const clearFilters = () => {
    setSearch("");
    setFamilyFilter("");
    setEvidenceFilter("");
    setDateFilter("");
    setSortOrder("catalog");
    setExportStatus(null);
    setShareStatus(null);
  };
  const copyFilteredViewLink = async () => {
    const url = shareableFilterUrl(new URL(window.location.href), {
      search,
      familyFilter,
      evidenceFilter,
      dateFilter,
      sortOrder,
    });
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(url.toString());
      setShareStatus("copied");
    } catch {
      setShareStatus("error");
    }
  };
  const shareStatusMessage = shareStatus === "copied"
    ? text.shareCopied
    : shareStatus === "error" ? text.shareFailed : "";
  const exportFilteredCandidates = () => {
    if (filteredCandidates.length === 0) return;
    try {
      const csv = buildDeviceDiscoveryCsv(filteredCandidates, text.csvScopeLimit);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "medihub-bangladesh-device-discovery-leads.csv";
      link.hidden = true;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 1000);
      setExportStatus({ kind: "success", count: filteredCandidates.length });
    } catch {
      setExportStatus({ kind: "error" });
    }
  };
  const exportStatusMessage = exportStatus?.kind === "success"
    ? text.exportedCsv.replace("{count}", number.format(exportStatus.count))
    : exportStatus?.kind === "error" ? text.exportUnavailable : "";
  const resultsMessage = text.showing
    .replace("{shown}", number.format(filteredCandidates.length))
    .replace("{total}", number.format(library?.candidates.length ?? 0));

  return (
    <main className="shell device-discovery-page">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="MediHub operations home">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span className="brand-name">MediHub<span className="brand-subtitle">INTEGRATION GATEWAY</span></span>
        </Link>
        <div className="top-actions">
          <label className="language-control">
            <span>{text.language}</span>
            <select value={language} onChange={(event) => {
              setLanguage(event.target.value as Language);
              setExportStatus(null);
              setShareStatus(null);
            }}>
              <option value="en">English</option>
              <option value="bn">বাংলা</option>
            </select>
          </label>
        </div>
      </header>

      <nav className="nav" aria-label={text.navLabel}>
        <Link className="nav-link" href="/">{text.operations}</Link>
        <Link className="nav-link active" href="/bangladesh-devices" aria-current="page">{text.discovery}</Link>
        <Link className="nav-link" href="/devices">{text.management}</Link>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">{text.eyebrow}</p>
          <h1 id="page-title">{text.title}</h1>
          <p className="hero-copy">{text.description}</p>
        </div>
        <span className="mode-badge"><span className="pulse" aria-hidden="true" />{text.discoveryOnly}</span>
      </section>

      <aside className="device-discovery-boundary" aria-label={text.scopeLabel}>
        <strong>{text.scopeLabel}</strong> {text.scopeCopy}
      </aside>

      <section className="panel device-filter-panel" aria-labelledby="device-filter-heading">
        <div className="panel-heading">
          <div><h2 id="device-filter-heading">{text.filtersTitle}</h2></div>
          <button className="device-clear-filters" type="button" onClick={clearFilters} disabled={!hasFilters}>
            {text.clearFilters}
          </button>
        </div>
        <div className="device-filter-grid">
          <label className="device-filter device-search-filter">
            <span>{text.search}</span>
            <input
              type="search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setExportStatus(null);
                setShareStatus(null);
              }}
              placeholder={text.searchPlaceholder}
              maxLength={100}
              disabled={!library}
            />
          </label>
          <label className="device-filter">
            <span>{text.family}</span>
            <select value={familyFilter} onChange={(event) => {
              setFamilyFilter(event.target.value as DeviceFamily | "");
              setExportStatus(null);
              setShareStatus(null);
            }} disabled={!library}>
              <option value="">{text.allFamilies}</option>
              {deviceFamilies.map((family) => <option key={family} value={family}>{text.familyLabels[family]}</option>)}
            </select>
          </label>
          <label className="device-filter">
            <span>{text.evidence}</span>
            <select value={evidenceFilter} onChange={(event) => {
              setEvidenceFilter(event.target.value as DiscoveryBasis | "");
              setExportStatus(null);
              setShareStatus(null);
            }} disabled={!library}>
              <option value="">{text.allEvidence}</option>
              {discoveryBases.map((basis) => <option key={basis} value={basis}>{text.evidenceLabels[basis]}</option>)}
            </select>
          </label>
          <label className="device-filter">
            <span>{text.catalogDate}</span>
            <select value={dateFilter} onChange={(event) => {
              setDateFilter(event.target.value as CatalogDateFilter);
              setExportStatus(null);
              setShareStatus(null);
            }} disabled={!library}>
              <option value="">{text.anyCatalogDate}</option>
              <option value="recorded">{text.dateRecorded}</option>
              <option value="not-recorded">{text.dateNotRecorded}</option>
            </select>
          </label>
          <label className="device-filter">
            <span>{text.sortResults}</span>
            <select value={sortOrder} onChange={(event) => {
              setSortOrder(event.target.value as DiscoverySortOrder);
              setExportStatus(null);
              setShareStatus(null);
            }} disabled={!library}>
              {discoverySortOrders.map((order) => <option key={order} value={order}>{sortLabels[order]}</option>)}
            </select>
          </label>
        </div>
        <p className="device-date-hint">{text.dateHint}</p>
        <p className="device-share-hint">{text.shareHint}</p>
      </section>

      {loading && <p className="device-library-status" role="status">{text.loading}</p>}
      {unavailable && <p className="notice error" role="alert">{text.unavailable}</p>}

      {library && !unavailable && (
        <section className="device-results-section" aria-labelledby="device-results-heading">
          <div className="device-results-heading">
            <div>
              <h2 id="device-results-heading">{text.resultsTitle}</h2>
              <p className="device-results-count" role="status" data-testid="device-results-count">{resultsMessage}</p>
            </div>
            <div className="device-result-actions">
              <button
                className="device-share-link"
                type="button"
                onClick={() => void copyFilteredViewLink()}
                disabled={!filtersLoaded}
              >
                {text.copyShareLink}
              </button>
              <button
                className="device-export-csv"
                type="button"
                onClick={exportFilteredCandidates}
                disabled={filteredCandidates.length === 0}
              >
                {text.exportCsv}
              </button>
            </div>
          </div>
          {shareStatusMessage && <p className="device-share-status" role="status" aria-live="polite">{shareStatusMessage}</p>}
          {exportStatusMessage && <p className="device-export-status" role="status" aria-live="polite">{exportStatusMessage}</p>}
          {filteredCandidates.length > 0 ? (
            <div className="device-result-grid" data-testid="device-result-grid">
              {filteredCandidates.map((candidate) => (
                <article className="device-result-card" key={candidate.candidate_id} data-testid="device-result-card">
                  <div className="device-result-card-heading">
                    <div>
                      <span className="device-evidence-badge">{text.evidenceLabels[candidate.discovery_basis]}</span>
                      <h3>{candidate.manufacturer} <span>{candidate.model}</span></h3>
                    </div>
                    <span className="device-discovery-status">{text.discoveryOnly}</span>
                  </div>
                  <p className="device-family-label">{text.familyLabels[candidate.device_family]}</p>
                  <div className="device-result-details">
                    <div>
                      <span>{text.evidenceNote}</span>
                      <p>{candidate.evidence_note}</p>
                    </div>
                    <div>
                      <span>{text.dateStatus}</span>
                      <p>{candidate.evidence_reviewed_on ? text.datePresent : text.dateAbsent}</p>
                    </div>
                  </div>
                  {candidate.source_url ? (
                    <a className="device-source-link" href={candidate.source_url} target="_blank" rel="noopener noreferrer">
                      {text.sourceLink}<span aria-hidden="true"> ↗</span>
                    </a>
                  ) : <p className="device-no-source">{text.sourceUnavailable}</p>}
                </article>
              ))}
            </div>
          ) : (
            <p className="device-no-results" role="status">{text.noResults}</p>
          )}
        </section>
      )}

      <footer className="footer"><span>{text.footer}</span></footer>
    </main>
  );
}
