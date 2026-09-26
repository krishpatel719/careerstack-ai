import { useEffect, useRef, useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import { getAnalysis, listAnalyses, type Analysis } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Sections the sidebar scroll-spies, in page order. */
export const DASH_SECTIONS = [
  { id: "overviewSection", label: "Overview" },
  { id: "breakdownSection", label: "Detailed Breakdown" },
  { id: "skillCoverageSection", label: "Skill Coverage" },
  { id: "formatSection", label: "Format" },
  { id: "improvementsSection", label: "Improvements" },
] as const;

const ICONS: Record<string, ReactElement> = {
  overviewSection: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  ),
  breakdownSection: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="9" width="2.5" height="5" rx="0.5" fill="currentColor" />
      <rect x="6.75" y="5" width="2.5" height="9" rx="0.5" fill="currentColor" />
      <rect x="11.5" y="2" width="2.5" height="12" rx="0.5" fill="currentColor" />
    </svg>
  ),
  skillCoverageSection: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4" />
      <path d="M5.3 8.2L7.2 10.1L10.8 6.1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  formatSection: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2.5" y="1.5" width="11" height="13" rx="1.3" stroke="currentColor" strokeWidth="1.4" />
      <line x1="5" y1="5.5" x2="11" y2="5.5" stroke="currentColor" strokeWidth="1.3" />
      <line x1="5" y1="8.5" x2="11" y2="8.5" stroke="currentColor" strokeWidth="1.3" />
      <line x1="5" y1="11.5" x2="9" y2="11.5" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  ),
  improvementsSection: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8.6 1.5L3.5 9h3.4l-1 5.5L12.5 7H9.1l1.5-5.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  ),
};

function formatHistoryDate(iso?: string) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/**
 * The original left rail: Analysis links that scroll-spy the page, then an
 * About group holding How Scoring Works, History and New Analysis, with the
 * analysed filename pinned to the bottom.
 */
export function DashboardSidebar({
  filename,
  role,
  location,
  onSelectAnalysis,
  showSections = true,
}: {
  filename?: string;
  role?: string;
  location?: string;
  onSelectAnalysis?: (analysis: Analysis) => void;
  /** The Analysis section links scroll-spy the dashboard's own headings,
      so pages without those headings (Jobs, Job Map, Account) hide them
      and show only the Jobs and About groups. */
  showSections?: boolean;
}) {
  const navigate = useNavigate();
  const [active, setActive] = useState<string>(DASH_SECTIONS[0].id);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<Analysis[] | null>(null);
  const [historyError, setHistoryError] = useState(false);
  const observer = useRef<IntersectionObserver | null>(null);

  // Scroll-spy: highlight whichever section is currently in view. The
  // rootMargin keeps a section "active" while it occupies the upper part
  // of the viewport, rather than flipping the moment its edge crosses.
  useEffect(() => {
    if (!showSections) return;
    observer.current?.disconnect();
    observer.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(entry.target.id);
        });
      },
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 },
    );
    DASH_SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.current?.observe(el);
    });
    return () => observer.current?.disconnect();
  }, [showSections]);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function toggleHistory() {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (!next) return;
    // Refetch on every open so a just-finished analysis appears.
    setHistory(null);
    setHistoryError(false);
    listAnalyses()
      .then(setHistory)
      .catch(() => setHistoryError(true));
  }

  function openFromHistory(id: string) {
    getAnalysis(id)
      .then((analysis) => onSelectAnalysis?.(analysis))
      .catch(() => setHistoryError(true));
  }

  return (
    <aside className="cs-dash-sidebar">
      <div className="cs-wordmark">
        CareerStack<span className="cs-wordmark-accent">AI</span>
      </div>

      {showSections && (
        <>
          <div className="cs-sidebar-group-label">Analysis</div>
          {DASH_SECTIONS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={cn("cs-sidebar-item", active === id && "is-active")}
              onClick={() => scrollTo(id)}
            >
              {ICONS[id]}
              {label}
            </button>
          ))}
        </>
      )}

      <div className="cs-sidebar-group-label">Jobs</div>
      <button type="button" className="cs-sidebar-item" onClick={() => navigate("/app/jobs")}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="4.5" width="12" height="9.5" rx="1.3" stroke="currentColor" strokeWidth="1.4" />
          <path d="M5.6 4.4V3.2c0-.66.54-1.2 1.2-1.2h2.4c.66 0 1.2.54 1.2 1.2v1.2" stroke="currentColor" strokeWidth="1.4" />
        </svg>
        Find Matching Jobs
      </button>
      <button type="button" className="cs-sidebar-item" onClick={() => navigate("/app/jobs/map")}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M1.5 4.2 5.5 2.4l5 1.8 4-1.8v9.4l-4 1.8-5-1.8-4 1.8V4.2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M5.5 2.4v9.4M10.5 4.2v9.4" stroke="currentColor" strokeWidth="1.3" />
        </svg>
        Job Map
      </button>

      <div className="cs-sidebar-group-label">About</div>
      <button type="button" className="cs-sidebar-item" onClick={() => navigate("/#methodologySection")}>
        How Scoring Works
      </button>
      <button type="button" className="cs-sidebar-item" onClick={toggleHistory}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.4" />
          <path d="M8 4.5V8L10.5 9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        History
      </button>

      {historyOpen && (
        <div className="cs-sidebar-history">
          {historyError && <div className="cs-history-empty">Could not load your history.</div>}
          {!historyError && history === null && <div className="cs-history-empty">Loading…</div>}
          {!historyError && history?.length === 0 && (
            <div className="cs-history-empty">No previous analyses yet.</div>
          )}
          {!historyError &&
            history?.map((item) => (
              <button
                key={item.analysis_id}
                type="button"
                className="cs-history-row"
                onClick={() => openFromHistory(item.analysis_id)}
              >
                <div className="cs-history-fname">{item.filename || "Untitled"}</div>
                <div className="cs-history-meta">
                  {item.role} · {formatHistoryDate(item.created_at)}
                </div>
                <div className="cs-history-pills">
                  <span className="cs-history-pill">
                    Parse {typeof item.parse_score === "number" ? item.parse_score.toFixed(0) : "—"}
                  </span>
                  <span className="cs-history-pill">
                    Fit {typeof item.overall_score === "number" ? item.overall_score.toFixed(0) : "—"}
                  </span>
                </div>
              </button>
            ))}
        </div>
      )}

      <button type="button" className="cs-sidebar-item" onClick={() => navigate("/upload")}>
        New Analysis
      </button>

      <div className="cs-sidebar-bottom">
        <div className="cs-sidebar-fname">{filename}</div>
        <div className="cs-sidebar-role">
          {role}
          {location ? ` · ${location}` : ""}
        </div>
      </div>
    </aside>
  );
}
