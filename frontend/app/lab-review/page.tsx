"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
      "No patient data is present. This page does not associate accessions with patients, verify or finalize results, release results, or send data to another system. Do not use it for clinical care.",
    queueTitle: "Results awaiting review",
    queueHint: "Every row is fabricated and remains unverified in this browser-only demonstration.",
    accession: "Synthetic accession",
    assay: "Demo assay code",
    result: "Raw demo value",
    received: "Received (demo time)",
    reviewState: "Review state",
    actions: "Details",
    pending: "Pending technician review",
    viewed: "Viewed locally · still unverified",
    openDetails: "Open demo details",
    closeDetails: "Hide details",
    acknowledge: "Acknowledge demo view",
    viewedNotice: "Viewed in this browser only. The result remains pending and unverified.",
    detailTitle: "Opaque synthetic source fields",
    sourceMessage: "Synthetic message ID",
    source: "Source",
    sourceValue: "Synthetic fixture",
    noPatient: "Patient context: none",
    noInterpretation: "No reference interval or clinical interpretation is supplied.",
    noActions: "No verify, finalize, release, or send actions are available in this prototype.",
    count: "Synthetic records",
    footer: "MediHub · Static synthetic review prototype · No device or receiver connection",
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
      "এখানে কোনো রোগীর তথ্য নেই। এই পৃষ্ঠা accession-এর সঙ্গে রোগী মেলায় না, ফলাফল যাচাই বা চূড়ান্ত করে না, প্রকাশ করে না, এবং অন্য কোনো সিস্টেমে পাঠায় না। চিকিৎসার কাজে এটি ব্যবহার করবেন না।",
    queueTitle: "পর্যালোচনার অপেক্ষায় থাকা ফলাফল",
    queueHint: "প্রতিটি সারি কৃত্রিমভাবে তৈরি; এই ব্রাউজারভিত্তিক প্রদর্শনীতে সব ফলাফল যাচাইহীন থাকে।",
    accession: "সিন্থেটিক accession",
    assay: "ডেমো অ্যাসে কোড",
    result: "কাঁচা ডেমো মান",
    received: "গ্রহণের সময় (ডেমো)",
    reviewState: "পর্যালোচনার অবস্থা",
    actions: "বিস্তারিত",
    pending: "ল্যাব টেকনিশিয়ানের পর্যালোচনার অপেক্ষায়",
    viewed: "এখানে দেখা হয়েছে · এখনো যাচাইহীন",
    openDetails: "ডেমোর বিস্তারিত দেখুন",
    closeDetails: "বিস্তারিত লুকান",
    acknowledge: "ডেমোতে দেখা হয়েছে চিহ্নিত করুন",
    viewedNotice: "শুধু এই ব্রাউজারে দেখা হয়েছে। ফলাফল এখনো অপেক্ষমাণ ও যাচাইহীন।",
    detailTitle: "অব্যাখ্যাকৃত সিন্থেটিক উৎসের ক্ষেত্র",
    sourceMessage: "সিন্থেটিক বার্তার আইডি",
    source: "উৎস",
    sourceValue: "সিন্থেটিক নমুনা",
    noPatient: "রোগীর তথ্য: নেই",
    noInterpretation: "কোনো রেফারেন্স সীমা বা চিকিৎসাগত ব্যাখ্যা দেওয়া হয়নি।",
    noActions: "এই প্রোটোটাইপে যাচাই, চূড়ান্তকরণ, প্রকাশ বা পাঠানোর কোনো ব্যবস্থা নেই।",
    count: "সিন্থেটিক রেকর্ড",
    footer: "MediHub · স্থির সিন্থেটিক পর্যালোচনা প্রোটোটাইপ · কোনো ডিভাইস বা রিসিভার সংযোগ নেই",
  },
} satisfies Record<Language, Record<string, string>>;

export default function LabReviewPage() {
  const [language, setLanguage] = useState<Language>("en");
  const [preferenceLoaded, setPreferenceLoaded] = useState(false);
  const [openResultId, setOpenResultId] = useState<string | null>(null);
  const [viewedResultIds, setViewedResultIds] = useState<string[]>([]);
  const text = copy[language];
  const number = new Intl.NumberFormat(language === "bn" ? "bn-BD" : "en");

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

  const acknowledgeView = (resultId: string) => {
    setViewedResultIds((previous) =>
      previous.includes(resultId) ? previous : [...previous, resultId],
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
              {demoResults.map((result) => {
                const isOpen = openResultId === result.id;
                const wasViewed = viewedResultIds.includes(result.id);
                const detailId = `details-${result.id}`;
                return (
                  <ResultRows
                    key={result.id}
                    result={result}
                    text={text}
                    language={language}
                    isOpen={isOpen}
                    wasViewed={wasViewed}
                    detailId={detailId}
                    onToggle={() => setOpenResultId(isOpen ? null : result.id)}
                    onAcknowledge={() => acknowledgeView(result.id)}
                  />
                );
              })}
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
  detailId: string;
  onToggle: () => void;
  onAcknowledge: () => void;
};

function ResultRows({
  result,
  text,
  language,
  isOpen,
  wasViewed,
  detailId,
  onToggle,
  onAcknowledge,
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
        <td><span className={styles.pendingBadge}>{wasViewed ? text.viewed : text.pending}</span></td>
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
            </section>
          </td>
        </tr>
      )}
    </>
  );
}
