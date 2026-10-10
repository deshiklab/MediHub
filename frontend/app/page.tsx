"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Language = "en" | "bn";

type EventRow = {
  event_id: string;
  device_id: string;
  received_at: string;
  label: string;
  value: number;
};

type DeliveryRow = {
  event_id: string;
  status: string;
  attempts: number;
  updated_at: string;
};

type Snapshot = {
  mode: string;
  ready: boolean;
  updated_at: string;
  source: { adapter_id: string; status: string; detail_code: string };
  receiver: { status: string };
  totals: {
    events_inserted: number;
    duplicate_events: number;
    delivery_attempts: number;
    acknowledged_deliveries: number;
    pending_deliveries: number;
    blocked_routes: number;
  };
  recent_events: EventRow[];
  recent_deliveries: DeliveryRow[];
  recent_holds: Array<{ event_id: string; reason_code: string }>;
};

const copy = {
  en: {
    language: "Interface language",
    navLabel: "Dashboard pages",
    operations: "Operations",
    devices: "Device management",
    mappings: "Data mapping",
    api: "EMR / EMS APIs",
    labReview: "Lab review (demo)",
    help: "Help / user guide",
    eyebrow: "SYNTHETIC OPERATIONS",
    title: "Integration operations",
    description: "A live view of the local synthetic pipeline, with no physical device or external receiver connected.",
    preview: "Synthetic-only preview",
    source: "Synthetic source",
    receiver: "Test receiver",
    refreshed: "Last updated",
    loading: "Connecting to the local demo…",
    retry: "Refreshes every two seconds",
    events: "Events ingested",
    duplicates: "Duplicates detected",
    attempts: "Delivery attempts",
    acknowledged: "Acknowledged",
    pending: "Pending delivery",
    holds: "Policy holds",
    activity: "Recent synthetic events",
    activityHint: "The table contains generated demo values only.",
    time: "Received",
    device: "Device",
    reading: "Reading",
    empty: "Waiting for the next synthetic event…",
    deliveries: "Recent deliveries",
    noDeliveries: "No delivery attempts yet.",
    synthetic: "Synthetic",
    safety: "Safety boundary",
    safeCopy: "This preview uses generated synthetic values only; it does not operate hardware or connect to an EMR / EMS. Bangladesh is the required deployment target; facility integration remains unconfigured.",
    footer: "MediHub · Local synthetic demonstration · No external network delivery",
    error: "The local API is unavailable. Start the FastAPI dashboard on port 8000, then reload.",
    healthy: "Healthy",
    starting: "Starting",
    degraded: "Degraded",
    connected: "In process",
    acknowledgedState: "Acknowledged",
    queued: "Queued",
    sent: "Sent",
    retryable: "Retryable failure",
    rejected: "Rejected",
    permanent: "Permanent failure",
    failed: "Unavailable",
  },
  bn: {
    language: "ইন্টারফেসের ভাষা",
    navLabel: "ড্যাশবোর্ডের পৃষ্ঠা",
    operations: "কার্যক্রম",
    devices: "ডিভাইস ব্যবস্থাপনা",
    mappings: "ডেটা ম্যাপিং",
    api: "EMR / EMS API",
    labReview: "ল্যাব পর্যালোচনা (ডেমো)",
    help: "সহায়তা / ব্যবহারকারী নির্দেশিকা",
    eyebrow: "সিন্থেটিক কার্যক্রম",
    title: "ইন্টিগ্রেশন কার্যক্রম",
    description: "স্থানীয় সিন্থেটিক ডেটা প্রবাহের সরাসরি চিত্র; কোনো বাস্তব ডিভাইস বা বাহ্যিক রিসিভার সংযুক্ত নয়।",
    preview: "শুধু সিন্থেটিক ডেটার প্রিভিউ",
    source: "সিন্থেটিক উৎস",
    receiver: "পরীক্ষামূলক রিসিভার",
    refreshed: "সর্বশেষ হালনাগাদ",
    loading: "স্থানীয় ডেমোর সঙ্গে সংযোগ হচ্ছে…",
    retry: "প্রতি দুই সেকেন্ডে হালনাগাদ হয়",
    events: "গ্রহণ করা ইভেন্ট",
    duplicates: "শনাক্ত করা ডুপ্লিকেট",
    attempts: "ডেলিভারির চেষ্টা",
    acknowledged: "রিসিভারের স্বীকৃতি",
    pending: "পাঠানোর অপেক্ষায়",
    holds: "নীতির কারণে আটকে রাখা",
    activity: "সাম্প্রতিক সিন্থেটিক ইভেন্ট",
    activityHint: "এই সারণিতে শুধু ডেমোর জন্য তৈরি কৃত্রিম (সিন্থেটিক) মান রয়েছে।",
    time: "গ্রহণের সময়",
    device: "ডিভাইস",
    reading: "পরিমাপ",
    empty: "পরবর্তী সিন্থেটিক ইভেন্টের অপেক্ষায়…",
    deliveries: "সাম্প্রতিক ডেলিভারি",
    noDeliveries: "এখনো কোনো ডেলিভারির চেষ্টা হয়নি।",
    synthetic: "সিন্থেটিক",
    safety: "নিরাপত্তার সীমা",
    safeCopy: "এই প্রিভিউতে শুধু ডেমোর জন্য তৈরি কৃত্রিম (সিন্থেটিক) মান ব্যবহার করা হয়। এটি কোনো হার্ডওয়্যার চালায় না এবং EMR / EMS-এর সঙ্গে সংযুক্ত নয়। বাংলাদেশে স্থাপন করাই MediHub-এর লক্ষ্য; তবে কোনো স্বাস্থ্যপ্রতিষ্ঠানের সঙ্গে সংযোগ এখনো কনফিগার করা হয়নি।",
    footer: "MediHub · স্থানীয় সিন্থেটিক প্রদর্শনী · বাহ্যিক নেটওয়ার্কে ডেলিভারি নেই",
    error: "স্থানীয় API পাওয়া যাচ্ছে না। FastAPI ড্যাশবোর্ড 8000 পোর্টে চালু করে পৃষ্ঠা রিলোড করুন।",
    healthy: "স্বাভাবিক",
    starting: "শুরু হচ্ছে",
    degraded: "আংশিক বিঘ্নিত",
    connected: "একই প্রসেসে চলছে",
    acknowledgedState: "রিসিভার গ্রহণ করেছে",
    queued: "সারিতে আছে",
    sent: "পাঠানো হয়েছে",
    retryable: "ব্যর্থ—আবার চেষ্টা করা যাবে",
    rejected: "প্রত্যাখ্যাত",
    permanent: "স্থায়ী ব্যর্থতা",
    failed: "অনুপলব্ধ",
  },
} satisfies Record<Language, Record<string, string>>;

function statusKey(status: string): keyof (typeof copy)["en"] {
  const keys: Record<string, keyof (typeof copy)["en"]> = {
    healthy: "healthy",
    in_process: "connected",
    starting: "starting",
    degraded: "degraded",
    acknowledged: "acknowledgedState",
    queued: "queued",
    sent: "sent",
    retryable_failure: "retryable",
    permanent_failure: "permanent",
    rejected: "rejected",
  };
  return keys[status] ?? "failed";
}

function formatTime(value: string, language: Language): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString(language === "bn" ? "bn-BD" : "en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function HomePage() {
  const [language, setLanguage] = useState<Language>("en");
  const [preferenceLoaded, setPreferenceLoaded] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [unavailable, setUnavailable] = useState(false);
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

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch("/api/dashboard", { cache: "no-store" });
        if (!response.ok) throw new Error("dashboard unavailable");
        const data = (await response.json()) as Snapshot;
        if (active) {
          setSnapshot(data);
          setUnavailable(false);
        }
      } catch {
        if (active) setUnavailable(true);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const metrics = [
    { label: text.events, value: snapshot?.totals.events_inserted },
    { label: text.duplicates, value: snapshot?.totals.duplicate_events },
    { label: text.attempts, value: snapshot?.totals.delivery_attempts },
    { label: text.pending, value: snapshot?.totals.pending_deliveries },
    { label: text.holds, value: snapshot?.totals.blocked_routes },
  ];

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
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="en">English</option>
              <option value="bn">বাংলা</option>
            </select>
          </label>
          <span className="mode-badge"><span className="pulse" aria-hidden="true" />{text.preview}</span>
        </div>
      </header>

      <nav className="nav" aria-label={text.navLabel}>
        <Link className="nav-link active" href="/">{text.operations}</Link>
        <Link className="nav-link" href="/devices">{text.devices}</Link>
        <Link className="nav-link" href="/mappings">{text.mappings}</Link>
        <Link className="nav-link" href="/api-setup">{text.api}</Link>
        <Link className="nav-link" href="/lab-review">{text.labReview}</Link>
        <Link className="nav-link" href="/help">{text.help}</Link>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">{text.eyebrow}</p>
          <h1 id="page-title">{text.title}</h1>
          <p className="hero-copy">{text.description}</p>
        </div>
        <div className="hero-meta">
          <span className="live-dot" aria-hidden="true" />
          <span>{text.retry}</span>
        </div>
      </section>

      {unavailable && <p className="notice error" role="status">{text.error}</p>}

      <section className="status-grid" aria-label={text.preview}>
        <article className="status-card">
          <span className={`status-icon ${snapshot?.source.status === "healthy" ? "is-good" : "is-waiting"}`} aria-hidden="true">●</span>
          <div><span className="card-label">{text.source}</span><strong>{snapshot ? text[statusKey(snapshot.source.status)] : text.loading}</strong><small>{snapshot?.source.adapter_id ?? "medihub.synthetic-device"}</small></div>
        </article>
        <article className="status-card">
          <span className={`status-icon ${snapshot?.receiver.status === "in_process" ? "is-good" : "is-waiting"}`} aria-hidden="true">●</span>
          <div><span className="card-label">{text.receiver}</span><strong>{snapshot ? text[statusKey(snapshot.receiver.status)] : text.loading}</strong><small>{snapshot?.mode ?? "synthetic_demo"}</small></div>
        </article>
        <article className="status-card updated-card">
          <span className="card-label">{text.refreshed}</span>
          <strong>{snapshot ? formatTime(snapshot.updated_at, language) : "—"}</strong>
          <small>{text.acknowledged}: {number.format(snapshot?.totals.acknowledged_deliveries ?? 0)}</small>
        </article>
      </section>

      <section className="metrics-grid" aria-label={text.activity}>
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value === undefined ? "—" : number.format(metric.value)}</strong>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="panel events-panel">
          <div className="panel-heading">
            <div><h2>{text.activity}</h2><p>{text.activityHint}</p></div>
            <span className="count-badge">{number.format(snapshot?.recent_events.length ?? 0)}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>{text.time}</th><th>{text.device}</th><th>{text.reading}</th><th>{text.synthetic}</th></tr></thead>
              <tbody>
                {snapshot?.recent_events.length ? snapshot.recent_events.slice(0, 8).map((event) => (
                  <tr key={event.event_id}>
                    <td>{formatTime(event.received_at, language)}</td>
                    <td className="mono">{event.device_id}</td>
                    <td className="reading">{Number(event.value).toFixed(2)}</td>
                    <td><span className="synthetic-chip">{text.synthetic}</span></td>
                  </tr>
                )) : <tr><td className="empty" colSpan={4}>{snapshot ? text.empty : text.loading}</td></tr>}
              </tbody>
            </table>
          </div>
        </article>

        <aside className="side-stack">
          <article className="panel">
            <div className="panel-heading"><div><h2>{text.deliveries}</h2><p>{text.attempts}</p></div></div>
            <div className="delivery-list">
              {snapshot?.recent_deliveries.length ? snapshot.recent_deliveries.slice(0, 5).map((delivery) => (
                <div className="delivery-row" key={delivery.event_id}>
                  <span className={`delivery-dot state-${delivery.status}`} aria-hidden="true" />
                  <div className="delivery-copy"><strong>{text[statusKey(delivery.status)]}</strong><small>{formatTime(delivery.updated_at, language)} · {number.format(delivery.attempts)}</small></div>
                </div>
              )) : <p className="empty-copy">{snapshot ? text.noDeliveries : text.loading}</p>}
            </div>
          </article>

          <article className="panel safety-panel">
            <div className="safety-icon" aria-hidden="true">✓</div>
            <div><h2>{text.safety}</h2><p>{text.safeCopy}</p></div>
            <div className="hold-count"><span>{text.holds}</span><strong>{number.format(snapshot?.recent_holds.length ?? 0)}</strong></div>
          </article>
        </aside>
      </section>

      <footer className="footer"><span>{text.footer}</span><span>{text.refreshed}: {snapshot ? formatTime(snapshot.updated_at, language) : "—"}</span></footer>
    </main>
  );
}
