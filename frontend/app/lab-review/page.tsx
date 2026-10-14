"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import styles from "./page.module.css";

type Language = "en" | "bn";

type DemoResult = {
  id: string;
  accession: string;
  assay: string;
  value: string;
  unit: string;
  receivedAt: string;
  sourceMessageId: string;
};

type ViewFilter = "all" | "not-viewed" | "viewed";
type FollowUpFilter = "all" | "flagged" | "not-flagged";

const demoResults: DemoResult[] = [
  {
    id: "SYNTH-RESULT-001",
    accession: "SYNTH-ACC-1001",
    assay: "DEMO-ASSAY-A",
    value: "2.30",
    unit: "demo units",
    receivedAt: "2026-10-11T09:15:00Z",
    sourceMessageId: "SYNTH-MSG-001",
  },
  {
    id: "SYNTH-RESULT-002",
    accession: "SYNTH-ACC-1002",
    assay: "DEMO-ASSAY-B",
    value: "DEMO-POSITIVE",
    unit: "—",
    receivedAt: "2026-10-11T09:17:00Z",
    sourceMessageId: "SYNTH-MSG-002",
  },
  {
    id: "SYNTH-RESULT-003",
    accession: "SYNTH-ACC-1003",
    assay: "DEMO-ASSAY-C",
    value: "7.10",
    unit: "demo units",
    receivedAt: "2026-10-11T09:19:00Z",
    sourceMessageId: "SYNTH-MSG-003",
  },
];

const copy = {
  en: {
    language: "Interface language",
    nav: "Dashboard pages",
    operations: "Operations",
    devices: "Device management",
    mappings: "Data mapping",
    api: "EMR / EMS APIs",
    labReview: "Lab review (demo)",
    help: "Help / user guide",
    preview: "Synthetic-only preview",
    eyebrow: "SYNTHETIC WORKFLOW PROTOTYPE",
    title: "Synthetic lab-result review",
    description:
      "A visual prototype of pending results for technician review. These fixtures are not received from a CL-900i or any clinical system.",
    safetyTitle: "Demo boundary",
    safetyCopy:
      "No patient data is present. This page does not associate accessions with patients, verify or finalize results, release results, or send data to another system. View acknowledgements and fixed follow-up flags are temporary demo-only browser state; they are not clinical decisions or saved review records. Do not use it for clinical care.",
    queueTitle: "Results awaiting review",
    queueHint: "Every row is fabricated and remains pending and unverified. View acknowledgements and fixed follow-up flags reset when this page reloads.",
    controlsTitle: "Synthetic queue controls",
    searchLabel: "Search synthetic accession, assay, or source ID",
    searchPlaceholder: "e.g. SYNTH-ACC-1001",
    viewFilterLabel: "Local view acknowledgement",
    allRows: "All demo rows",
    notViewed: "Not acknowledged in this browser",
    viewedOnly: "Viewed in this browser",
    followUpFilterLabel: "Local demo follow-up flag",
    allFollowUp: "All demo rows",
    flaggedOnly: "Flagged for additional demo review",
    notFlagged: "Not flagged",
    clearFilters: "Clear filters",
    showingCount: "Showing {shown} of {total} synthetic records.",
    noMatches: "No synthetic rows match the current search and filter.",
    accession: "Synthetic accession",
    assay: "Demo assay code",
    result: "Raw demo value",
    received: "Received (demo time)",
    reviewState: "Review state",
    actions: "Details",
    pending: "Pending technician review",
    viewed: "Viewed locally · still unverified",
    followUpPending: "Follow-up flagged locally · still pending",
    openDetails: "Open demo details",
    closeDetails: "Hide details",
    acknowledge: "Acknowledge demo view",
    viewedNotice: "Viewed in this browser only. The result remains pending and unverified.",
    flagForFollowUp: "Flag for additional demo review",
    clearFollowUp: "Clear demo review flag",
    followUpNotice: "Flag stored only in this page's temporary browser state. The result remains pending and unverified; nothing is transmitted.",
    detailTitle: "Opaque synthetic source fields",
    sourceMessage: "Synthetic message ID",
    source: "Source",
    sourceValue: "Synthetic fixture",
    noPatient: "Patient context: none",
    noInterpretation: "No reference interval or clinical interpretation is supplied.",
    noActions: "No clinical verification, finalization, release, disposition, or send action is available. The local demo flag is not an escalation or saved review record.",
    count: "Synthetic records",
    footer: "MediHub · Static synthetic review prototype · Local view/flag state only · No device or receiver connection",
  },
  bn: {
    language: "ইন্টারফেসের ভাষা",
    nav: "ড্যাশবোর্ডের পৃষ্ঠা",
    operations: "কার্যক্রম",
    devices: "ডিভাইস ব্যবস্থাপনা",
    mappings: "ডেটা ম্যাপিং",
    api: "EMR / EMS API",
    labReview: "ল্যাব পর্যালোচনা (ডেমো)",
    help: "সহায়তা / ব্যবহারকারী নির্দেশিকা",
    preview: "শুধু সিন্থেটিক ডেটার প্রিভিউ",
    eyebrow: "সিন্থেটিক কর্মপ্রবাহের প্রোটোটাইপ",
    title: "সিন্থেটিক ল্যাব ফলাফল পর্যালোচনা",
    description:
      "ল্যাব টেকনিশিয়ানের পর্যালোচনার অপেক্ষায় থাকা ফলাফলের একটি দৃশ্যমান প্রোটোটাইপ। এই নমুনাগুলো CL-900i বা কোনো ক্লিনিক্যাল সিস্টেম থেকে আসেনি।",
    safetyTitle: "ডেমোর সীমা",
    safetyCopy:
      "এখানে কোনো রোগীর তথ্য নেই। এই পৃষ্ঠা accession-এর সঙ্গে রোগী মেলায় না, ফলাফল যাচাই বা চূড়ান্ত করে না, প্রকাশ করে না, এবং অন্য কোনো সিস্টেমে পাঠায় না। দেখার স্বীকৃতি ও নির্দিষ্ট follow-up চিহ্ন শুধু সাময়িক ডেমো ব্রাউজার-অবস্থা; এগুলো ক্লিনিক্যাল সিদ্ধান্ত বা সংরক্ষিত পর্যালোচনা নয়। চিকিৎসার কাজে এটি ব্যবহার করবেন না।",
    queueTitle: "পর্যালোচনার অপেক্ষায় থাকা ফলাফল",
    queueHint: "প্রতিটি সারি কৃত্রিম; সব ফলাফল অপেক্ষমাণ ও যাচাইহীন। পৃষ্ঠা পুনরায় লোড হলে দেখার স্বীকৃতি ও follow-up চিহ্ন মুছে যায়।",
    controlsTitle: "সিন্থেটিক সারির নিয়ন্ত্রণ",
    searchLabel: "সিন্থেটিক accession, অ্যাসে বা উৎসের ID খুঁজুন",
    searchPlaceholder: "যেমন SYNTH-ACC-1001",
    viewFilterLabel: "এই ব্রাউজারে দেখার স্বীকৃতি",
    allRows: "সব ডেমো সারি",
    notViewed: "এই ব্রাউজারে এখনো দেখা হয়নি",
    viewedOnly: "এই ব্রাউজারে দেখা হয়েছে",
    followUpFilterLabel: "স্থানীয় ডেমো follow-up চিহ্ন",
    allFollowUp: "সব ডেমো সারি",
    flaggedOnly: "আরও ডেমো পর্যালোচনার জন্য চিহ্নিত",
    notFlagged: "চিহ্নিত নয়",
    clearFilters: "ফিল্টার মুছুন",
    showingCount: "মোট {total}টি সিন্থেটিক রেকর্ডের মধ্যে {shown}টি দেখানো হচ্ছে।",
    noMatches: "বর্তমান অনুসন্ধান ও ফিল্টারে কোনো সিন্থেটিক সারি মেলেনি।",
    accession: "সিন্থেটিক accession",
    assay: "ডেমো অ্যাসে কোড",
    result: "কাঁচা ডেমো মান",
    received: "গ্রহণের সময় (ডেমো)",
    reviewState: "পর্যালোচনার অবস্থা",
    actions: "বিস্তারিত",
    pending: "ল্যাব টেকনিশিয়ানের পর্যালোচনার অপেক্ষায়",
    viewed: "এখানে দেখা হয়েছে · এখনো যাচাইহীন",
    followUpPending: "স্থানীয় follow-up চিহ্ন · এখনো অপেক্ষমাণ",
    openDetails: "ডেমোর বিস্তারিত দেখুন",
    closeDetails: "বিস্তারিত লুকান",
    acknowledge: "ডেমোতে দেখা হয়েছে চিহ্নিত করুন",
    viewedNotice: "শুধু এই ব্রাউজারে দেখা হয়েছে। ফলাফল এখনো অপেক্ষমাণ ও যাচাইহীন।",
    flagForFollowUp: "আরও ডেমো পর্যালোচনার জন্য চিহ্নিত করুন",
    clearFollowUp: "ডেমো follow-up চিহ্ন মুছুন",
    followUpNotice: "চিহ্নটি শুধু এই পৃষ্ঠার সাময়িক ব্রাউজার অবস্থায় থাকে। ফলাফল অপেক্ষমাণ ও যাচাইহীন; কিছু পাঠানো হয় না।",
    detailTitle: "অব্যাখ্যাকৃত সিন্থেটিক উৎসের ক্ষেত্র",
    sourceMessage: "সিন্থেটিক বার্তার আইডি",
    source: "উৎস",
    sourceValue: "সিন্থেটিক নমুনা",
    noPatient: "রোগীর তথ্য: নেই",
    noInterpretation: "কোনো রেফারেন্স সীমা বা চিকিৎসাগত ব্যাখ্যা দেওয়া হয়নি।",
    noActions: "ক্লিনিক্যাল যাচাই, চূড়ান্তকরণ, প্রকাশ, সিদ্ধান্ত বা পাঠানোর ব্যবস্থা নেই। স্থানীয় ডেমো চিহ্নটি এস্কেলেশন বা সংরক্ষিত পর্যালোচনা নয়।",
    count: "সিন্থেটিক রেকর্ড",
    footer: "MediHub · স্থির সিন্থেটিক পর্যালোচনা প্রোটোটাইপ · স্থানীয় দেখা/চিহ্নের অবস্থা · কোনো ডিভাইস বা রিসিভার সংযোগ নেই",
  },
} satisfies Record<Language, Record<string, string>>;

export default function LabReviewPage() {
  const [language, setLanguage] = useState<Language>("en");
  const [preferenceLoaded, setPreferenceLoaded] = useState(false);
  const [openResultId, setOpenResultId] = useState<string | null>(null);
  const [viewedResultIds, setViewedResultIds] = useState<string[]>([]);
  const [followUpResultIds, setFollowUpResultIds] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewFilter, setViewFilter] = useState<ViewFilter>("all");
  const [followUpFilter, setFollowUpFilter] = useState<FollowUpFilter>("all");
  const text = copy[language];
  const number = new Intl.NumberFormat(language === "bn" ? "bn-BD" : "en");
  const filteredResults = useMemo(() => {
    const query = searchTerm.trim().normalize("NFKC").toLocaleLowerCase();
    return demoResults.filter((result) => {
      const wasViewed = viewedResultIds.includes(result.id);
      const followUpFlagged = followUpResultIds.includes(result.id);
      if (viewFilter === "not-viewed" && wasViewed) return false;
      if (viewFilter === "viewed" && !wasViewed) return false;
      if (followUpFilter === "flagged" && !followUpFlagged) return false;
      if (followUpFilter === "not-flagged" && followUpFlagged) return false;
      if (!query) return true;
      const searchableText = [result.accession, result.assay, result.id, result.sourceMessageId]
        .join(" ")
        .normalize("NFKC")
        .toLocaleLowerCase();
      return searchableText.includes(query);
    });
  }, [followUpFilter, followUpResultIds, searchTerm, viewFilter, viewedResultIds]);
  const showingCount = text.showingCount
    .replace("{shown}", number.format(filteredResults.length))
    .replace("{total}", number.format(demoResults.length));

  useEffect(() => {
    try {
      setLanguage(window.localStorage.getItem("medihub-language") === "bn" ? "bn" : "en");
    } catch {
      setLanguage("en");
    }
    setPreferenceLoaded(true);
  }, []);

  useEffect(() => {
    if (!preferenceLoaded) return;
    document.documentElement.lang = language;
    try {
      window.localStorage.setItem("medihub-language", language);
    } catch {
      // The language control remains usable when storage is disabled.
    }
  }, [language, preferenceLoaded]);

  useEffect(() => {
    if (openResultId && !filteredResults.some((result) => result.id === openResultId)) {
      setOpenResultId(null);
    }
  }, [filteredResults, openResultId]);

  const acknowledgeView = (resultId: string) => {
    setViewedResultIds((previous) =>
      previous.includes(resultId) ? previous : [...previous, resultId],
    );
  };

  const toggleFollowUpFlag = (resultId: string) => {
    setFollowUpResultIds((previous) =>
      previous.includes(resultId)
        ? previous.filter((previousId) => previousId !== resultId)
        : [...previous, resultId],
    );
  };

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="MediHub operations home">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span className="brand-name">MediHub<span className="brand-subtitle">INTEGRATION GATEWAY</span></span>
        </Link>
        <div className="top-actions">
          <label className="language-control">
            <span>{text.language}</span>
            <select
              aria-label={text.language}
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="en">English</option>
              <option value="bn">বাংলা</option>
            </select>
          </label>
          <span className="mode-badge"><span className="pulse" aria-hidden="true" />{text.preview}</span>
        </div>
      </header>

      <nav className="nav" aria-label={text.nav}>
        <Link className="nav-link" href="/">{text.operations}</Link>
        <Link className="nav-link" href="/devices">{text.devices}</Link>
        <Link className="nav-link" href="/mappings">{text.mappings}</Link>
        <Link className="nav-link" href="/api-setup">{text.api}</Link>
        <Link className="nav-link active" href="/lab-review" aria-current="page">{text.labReview}</Link>
        <Link className="nav-link" href="/help">{text.help}</Link>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">{text.eyebrow}</p>
          <h1 id="page-title">{text.title}</h1>
          <p className="hero-copy">{text.description}</p>
        </div>
      </section>

      <section className={styles.safetyPanel} aria-labelledby="safety-title">
        <span className={styles.safetyIcon} aria-hidden="true">!</span>
        <div>
          <h2 id="safety-title">{text.safetyTitle}</h2>
          <p>{text.safetyCopy}</p>
        </div>
      </section>

      <section className={`panel ${styles.queuePanel}`} aria-labelledby="queue-title">
        <div className="panel-heading">
          <div>
            <h2 id="queue-title">{text.queueTitle}</h2>
            <p>{text.queueHint}</p>
          </div>
          <span className="count-badge" aria-label={`${text.count}: ${demoResults.length}`}>
            {number.format(demoResults.length)}
          </span>
        </div>

        <div className={styles.queueTools} role="search" aria-label={text.controlsTitle}>
          <label className={styles.filterField}>
            <span>{text.searchLabel}</span>
            <input
              className={styles.filterInput}
              type="search"
              maxLength={100}
              autoComplete="off"
              placeholder={text.searchPlaceholder}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </label>
          <label className={styles.filterField}>
            <span>{text.viewFilterLabel}</span>
            <select
              className={styles.filterInput}
              value={viewFilter}
              onChange={(event) => setViewFilter(event.target.value as ViewFilter)}
            >
              <option value="all">{text.allRows}</option>
              <option value="not-viewed">{text.notViewed}</option>
              <option value="viewed">{text.viewedOnly}</option>
            </select>
          </label>
          <label className={styles.filterField}>
            <span>{text.followUpFilterLabel}</span>
            <select
              className={styles.filterInput}
              value={followUpFilter}
              onChange={(event) => setFollowUpFilter(event.target.value as FollowUpFilter)}
            >
              <option value="all">{text.allFollowUp}</option>
              <option value="flagged">{text.flaggedOnly}</option>
              <option value="not-flagged">{text.notFlagged}</option>
            </select>
          </label>
          <button
            className={styles.clearFilters}
            type="button"
            onClick={() => {
              setSearchTerm("");
              setViewFilter("all");
              setFollowUpFilter("all");
              setOpenResultId(null);
            }}
          >
            {text.clearFilters}
          </button>
        </div>
        <p className={styles.queueCount} role="status" aria-live="polite">{showingCount}</p>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">{text.accession}</th>
                <th scope="col">{text.assay}</th>
                <th scope="col">{text.result}</th>
                <th scope="col">{text.received}</th>
                <th scope="col">{text.reviewState}</th>
                <th scope="col">{text.actions}</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.length > 0 ? (
                filteredResults.map((result) => {
                  const isOpen = openResultId === result.id;
                  const wasViewed = viewedResultIds.includes(result.id);
                  const followUpFlagged = followUpResultIds.includes(result.id);
                  const detailId = `details-${result.id}`;
                  return (
                    <ResultRows
                      key={result.id}
                      result={result}
                      text={text}
                      language={language}
                      isOpen={isOpen}
                      wasViewed={wasViewed}
                      followUpFlagged={followUpFlagged}
                      detailId={detailId}
                      onToggle={() => setOpenResultId(isOpen ? null : result.id)}
                      onAcknowledge={() => acknowledgeView(result.id)}
                      onToggleFollowUpFlag={() => toggleFollowUpFlag(result.id)}
                    />
                  );
                })
              ) : (
                <tr>
                  <td className={styles.emptyRow} colSpan={6}>{text.noMatches}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <p className={styles.noActions} role="note">{text.noActions}</p>
      </section>

      <footer className="footer"><span>{text.footer}</span><span>{text.count}: {number.format(demoResults.length)}</span></footer>
    </main>
  );
}

type ResultRowProps = {
  result: DemoResult;
  text: (typeof copy)[Language];
  language: Language;
  isOpen: boolean;
  wasViewed: boolean;
  followUpFlagged: boolean;
  detailId: string;
  onToggle: () => void;
  onAcknowledge: () => void;
  onToggleFollowUpFlag: () => void;
};

function ResultRows({
  result,
  text,
  language,
  isOpen,
  wasViewed,
  followUpFlagged,
  detailId,
  onToggle,
  onAcknowledge,
  onToggleFollowUpFlag,
}: ResultRowProps) {
  return (
    <>
      <tr>
        <td className="mono">{result.accession}<br /><span className="synthetic-chip">{text.sourceValue}</span></td>
        <td className="mono">{result.assay}</td>
        <td className={styles.resultValue}>{result.value}<small>{result.unit}</small></td>
        <td>{new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en", {
          dateStyle: "medium",
          timeStyle: "short",
          timeZone: "UTC",
        }).format(new Date(result.receivedAt))}</td>
        <td>
          <span className={followUpFlagged ? `${styles.pendingBadge} ${styles.followUpBadge}` : styles.pendingBadge}>
            {followUpFlagged ? text.followUpPending : wasViewed ? text.viewed : text.pending}
          </span>
        </td>
        <td>
          <button
            className={styles.actionButton}
            type="button"
            aria-expanded={isOpen}
            aria-controls={isOpen ? detailId : undefined}
            onClick={onToggle}
          >
            {isOpen ? text.closeDetails : text.openDetails}
          </button>
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={6}>
            <section className={styles.details} id={detailId} aria-label={text.detailTitle}>
              <h3>{text.detailTitle}</h3>
              <dl className={styles.detailGrid}>
                <div><dt>{text.accession}</dt><dd>{result.accession}</dd></div>
                <div><dt>{text.assay}</dt><dd>{result.assay}</dd></div>
                <div><dt>{text.result}</dt><dd>{result.value} {result.unit}</dd></div>
                <div><dt>{text.sourceMessage}</dt><dd>{result.sourceMessageId}</dd></div>
                <div><dt>{text.source}</dt><dd>{text.sourceValue}</dd></div>
                <div><dt>{text.noPatient}</dt><dd>{language === "bn" ? "নেই" : "None"}</dd></div>
              </dl>
              <p className={styles.detailNote}>{text.noInterpretation}</p>
              {wasViewed ? (
                <p className={styles.viewedNote} role="status">{text.viewedNotice}</p>
              ) : (
                <button className={styles.secondaryButton} type="button" onClick={onAcknowledge}>
                  {text.acknowledge}
                </button>
              )}
              {followUpFlagged && (
                <p className={styles.followUpNote} role="status">{text.followUpNotice}</p>
              )}
              <button
                className={styles.followUpButton}
                type="button"
                onClick={onToggleFollowUpFlag}
              >
                {followUpFlagged ? text.clearFollowUp : text.flagForFollowUp}
              </button>
            </section>
          </td>
        </tr>
      )}
    </>
  );
}
