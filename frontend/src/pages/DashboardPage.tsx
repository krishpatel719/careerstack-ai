import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { getSavedAnalysis, saveAnalysis } from "@/lib/score";
import type { Analysis, User } from "@/lib/api";
import { cn } from "@/lib/utils";

/** The original four components, in the original order and wording. */
const COMPONENTS = [
  { key: "keyword", label: "Keyword coverage" },
  { key: "semantic", label: "Semantic fit" },
  { key: "format", label: "Format compliance" },
  { key: "experience", label: "Experience alignment" },
] as const;

const COMPONENT_LOWER: Record<string, string> = {
  keyword: "keyword coverage",
  semantic: "semantic fit",
  format: "format compliance",
  experience: "experience alignment",
};

const HEADLINES: Record<string, string> = {
  keyword: "Strong structure, weak keyword coverage",
  semantic: "Right keywords, thin supporting evidence",
  format: "Good content, parser-hostile formatting",
  experience: "Solid resume, under the market's experience bar",
};

const TYPE_LABELS: Record<string, string> = {
  missing_skill: "Missing skill",
  format_issue: "Format issue",
  weak_evidence: "Weak evidence",
};

/** Role Fit uses a four-tier market band. */
function bandTier(score: number) {
  if (score < 40) return "red";
  if (score < 60) return "amber";
  if (score < 80) return "indigo";
  return "green";
}

/**
 * ATS Parse Score has its own three-tier scale: it is a pass/fail-flavoured
 * parseability check, not a market-fit band, so it never shows the middle
 * "indigo" tier that Role Fit uses.
 */
function parseTier(score: number) {
  if (score < 70) return "red";
  if (score < 90) return "amber";
  return "green";
}

function formatSampledDate(iso?: string) {
  if (!iso) return "recently";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** Ring that animates its stroke and its number off one eased value, so the
 *  two can never drift apart mid-animation. */
function ScoreRing({ score, tier }: { score: number; tier: string }) {
  const [shown, setShown] = useState(0);
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const reduce =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (reduce) {
      setShown(score);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const duration = 900;
    const ease = (t: number) => 1 - Math.pow(1 - t, 3);
    const frame = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(score * ease(t));
      if (t < 1) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [score, reduce]);

  return (
    <div className="cs-ring-wrap">
      <svg className="cs-ring-svg" viewBox="0 0 84 84">
        <circle className="cs-ring-track" cx="42" cy="42" r={radius} />
        <circle
          className={cn("cs-ring-fill", `cs-band-${tier}`)}
          cx="42"
          cy="42"
          r={radius}
          style={{ strokeDasharray: `${circumference * (shown / 100)} ${circumference}` }}
        />
      </svg>
      <div className="cs-ring-overlay">{Math.round(shown)}</div>
    </div>
  );
}

export function DashboardPage({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<Analysis | null>(getSavedAnalysis);
  const [openItem, setOpenItem] = useState(0);

  useEffect(() => {
    document.title = "Your results · CareerStack AI";
  }, []);

  if (!analysis) {
    return (
      <div className="cs-dash-empty">
        <h2>No analysis yet</h2>
        <p>Upload a resume to see your score against live postings.</p>
        <button type="button" className="cs-btn cs-btn-indigo" onClick={() => navigate("/upload")}>
          Analyse my resume
        </button>
      </div>
    );
  }

  const score = Number(analysis.overall_score ?? 0);
  const format = analysis.format_detail || {};
  const parseScore = Number(format.score ?? 0) * 100;
  const meta = analysis.role_profile_meta || {};
  const subscores = analysis.subscores || {};
  const weights = analysis.weights || {};
  const postings = meta.postings_sampled;
  const postingsLabel = typeof postings === "number" ? postings : "?";
  const actionItems = analysis.action_plan?.items || [];
  const byCategory = analysis.keyword_detail?.by_category || {};

  const ordered = COMPONENTS.map((c) => ({ ...c, value: Number(subscores[c.key] ?? 0) })).sort(
    (a, b) => a.value - b.value,
  );
  const weakest = ordered[0];
  const secondWeakest = ordered[1];
  const allStrong = COMPONENTS.every((c) => Number(subscores[c.key] ?? 0) > 75);
  const headline = allStrong
    ? "Competitive across the board"
    : HEADLINES[weakest.key] || "Room to improve";

  // "What's holding it back": format issues worst-first, then missing
  // skills by frequency, then weak-evidence requirements -- top 3.
  const holdingBack: string[] = [
    ...(format.issues || []).slice().sort((a, b) => b.penalty - a.penalty).map((i) => i.message),
    ...Object.values(byCategory)
      .flatMap((group) => group.missing || [])
      .slice()
      .sort((a, b) => b.frequency - a.frequency)
      .map((s) => `"${s.skill}" is missing — appears in ${s.count} of ${postingsLabel} sampled postings.`),
    ...(analysis.semantic_detail?.weakest_requirements || []).map(
      (r) => `Weak evidence for: "${r.requirement}"`,
    ),
  ].slice(0, 3);

  const projected = analysis.action_plan?.projected_score_under_our_model ?? score;

  return (
    <div className="cs-dash">
      <DashboardSidebar
        filename={analysis.filename}
        role={analysis.role}
        location={analysis.location}
        onSelectAnalysis={(next) => {
          saveAnalysis(next);
          setAnalysis(next);
          window.scrollTo(0, 0);
        }}
      />

      <main className="cs-dash-main">
        <div className="cs-dash-inner">
          {(analysis.degraded || meta.location_fallback || meta.sparse_profile) && (
            <div className="cs-degraded-banner">
              {analysis.degraded && analysis.degraded_message && <p>{analysis.degraded_message}</p>}
              {meta.location_fallback && (
                <p>
                  Only {meta.location_fallback.requested_postings_sampled} postings found in{" "}
                  {meta.location_fallback.requested_location} — showing{" "}
                  {meta.location_fallback.used_location} instead.
                </p>
              )}
              {meta.sparse_profile && (
                <p>
                  The role profile used to score this resume was built from a smaller-than-usual
                  sample of postings.
                </p>
              )}
            </div>
          )}

          {/* ---------- Overview ---------- */}
          <section id="overviewSection" className="cs-result-section">
            {user?.name && <div className="cs-greeting-hi">Hi, {user.name.split(" ")[0]}</div>}
            <div className="cs-greeting-title">Your resume analysis</div>
            <div className="cs-greeting-sub">
              {analysis.role} &nbsp;·&nbsp; {analysis.location}
              {typeof postings === "number" && (
                <> &nbsp;·&nbsp; {postings} postings sampled {formatSampledDate(meta.sampled_at)}</>
              )}
            </div>

            <div className="cs-verdict-card">
              <div className="cs-verdict-ring-group">
                <div
                  className="cs-verdict-ring-label"
                  title="Measured from 9 deterministic checks on document structure: text extractability, columns, tables, contact details, section headings, dates, length."
                >
                  ATS Parse Score
                </div>
                <ScoreRing score={parseScore} tier={parseTier(parseScore)} />
                <div className="cs-verdict-sublabel">
                  {format.points_earned ?? "—"} of {format.points_possible ?? "—"} parse checks
                </div>
                <p className="cs-verdict-explain">
                  Whether an applicant tracking system can read your document.
                </p>
              </div>

              <div className="cs-verdict-ring-group">
                <div
                  className="cs-verdict-ring-label"
                  title="A weighted composite across four components. Not a prediction of any specific employer's ATS."
                >
                  Role Fit Score
                </div>
                <ScoreRing score={score} tier={bandTier(score)} />
                <div className="cs-verdict-sublabel">vs {postingsLabel} live postings</div>
                <p className="cs-verdict-explain">
                  How well your experience matches this role in this market.
                </p>
                <div className={cn("cs-band-pill", `cs-band-${bandTier(score)}`)}>
                  {analysis.band || "—"}
                </div>
              </div>

              <div className="cs-verdict-text">
                <h2 className="cs-verdict-headline">{headline}</h2>
                <p className="cs-verdict-sentence">
                  Your weakest areas are {COMPONENT_LOWER[weakest.key]}{" "}
                  <span className="cs-num">{weakest.value.toFixed(1)}</span> and{" "}
                  {COMPONENT_LOWER[secondWeakest.key]}{" "}
                  <span className="cs-num">{secondWeakest.value.toFixed(1)}</span>.
                </p>
              </div>
            </div>

            <div className="cs-subscore-grid">
              {COMPONENTS.map((c) => {
                const value = Number(subscores[c.key] ?? 0);
                return (
                  <div key={c.key} className="cs-subscore-card">
                    <div className="cs-subscore-top">
                      <span className="cs-subscore-label">{c.label}</span>
                      <span className="cs-subscore-weight">
                        {Math.round((weights[c.key] ?? 0) * 100)}% weight
                      </span>
                    </div>
                    <div className="cs-subscore-value">{value.toFixed(1)}</div>
                    <div className="cs-subscore-track">
                      <div
                        className="cs-subscore-fill"
                        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* ---------- Detailed breakdown ---------- */}
          <section id="breakdownSection" className="cs-result-section">
            <div className="cs-section-head">
              <h2>Detailed breakdown</h2>
            </div>

            <div className="cs-two-col">
              <div className="cs-panel">
                <div className="cs-section-head cs-section-head-flush">
                  <h2>What&apos;s holding it back</h2>
                  <span className="cs-count-badge">{holdingBack.length}</span>
                </div>
                <ol className="cs-holding-list">
                  {holdingBack.length === 0 && (
                    <li className="cs-chip-empty">Nothing significant holding this resume back.</li>
                  )}
                  {holdingBack.map((text, i) => (
                    <li key={text} className="cs-holding-item">
                      <span className="cs-holding-num">{i + 1}</span>
                      <span>{text}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="cs-panel">
                <div className="cs-section-head cs-section-head-flush">
                  <h2>Highest-impact fixes</h2>
                  <span className="cs-count-badge">{Math.min(3, actionItems.length)}</span>
                </div>
                <ul className="cs-impact-list">
                  {actionItems.length === 0 && (
                    <li className="cs-chip-empty">No further recommendations.</li>
                  )}
                  {actionItems.slice(0, 3).map((item) => (
                    <li key={item.action} className="cs-impact-item">
                      <svg className="cs-impact-check" width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M2.5 7.3L5.5 10.3L11.5 3.7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span>{item.action}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="cs-dimension-grid">
              {(analysis.dimensions || []).map((d) => (
                <div key={d.name} className="cs-dimension-row">
                  <span className={cn("cs-dimension-dot", `cs-status-${d.status}`)} />
                  <span className="cs-dimension-body">
                    <span className="cs-dimension-top">
                      <span className="cs-dimension-name">{d.name}</span>
                      <span className={cn("cs-dimension-score", `cs-status-${d.status}`)}>
                        {d.score.toFixed(1)}
                        <span className="cs-muted-suffix">/100</span>
                      </span>
                    </span>
                    <span className="cs-dimension-note">{d.note}</span>
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* ---------- Improvements ---------- */}
          <section id="improvementsSection" className="cs-result-section">
            <div className="cs-section-head">
              <h2>Suggested improvements</h2>
              <span className="cs-count-badge">{actionItems.length} found</span>
            </div>
            <div className="cs-improvements-header">
              <strong>{score.toFixed(1)}</strong> → <strong>{projected.toFixed(1)}</strong> projected
            </div>

            {actionItems.length === 0 && (
              <p className="cs-chip-empty">
                No further recommendations — this resume is in good shape.
              </p>
            )}

            {actionItems.map((item, i) => {
              const detail = item.detail || {};
              const isOpen = openItem === i;
              const summary =
                item.type === "missing_skill" && typeof detail.count === "number"
                  ? `Missing skill · in ${detail.count} of ${postingsLabel} postings`
                  : `${TYPE_LABELS[item.type] || item.type} · ${item.effort || ""} effort`;

              return (
                <div key={item.action} className={cn("cs-accordion", isOpen && "is-open")}>
                  <button
                    type="button"
                    className="cs-accordion-header"
                    onClick={() => setOpenItem(isOpen ? -1 : i)}
                  >
                    <span className={cn("cs-accordion-icon", `cs-type-${item.type}`)}>
                      {item.type === "missing_skill" ? "+" : item.type === "format_issue" ? "!" : "❝"}
                    </span>
                    <span className="cs-accordion-body-col">
                      <span className="cs-accordion-title">{item.action}</span>
                      <span className="cs-accordion-summary">{summary}</span>
                    </span>
                    <span className="cs-accordion-gain">
                      +{Number(item.estimated_gain ?? 0).toFixed(1)}
                    </span>
                    <svg className="cs-accordion-chevron" width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <path d="M5 7l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {isOpen && (
                    <div className="cs-accordion-panel">
                      {item.type === "missing_skill" && (
                        <>
                          <div>
                            <div className="cs-evidence-label">Market demand</div>
                            <p className="cs-evidence-text">
                              {detail.skill} appears in {detail.count ?? "?"} of {postingsLabel}{" "}
                              sampled postings
                            </p>
                          </div>
                          <div>
                            <div className="cs-evidence-label">Your resume</div>
                            <p className="cs-evidence-text">
                              Not found in skills, experience, or projects
                            </p>
                          </div>
                        </>
                      )}
                      {item.type === "format_issue" && (
                        <>
                          <div>
                            <div className="cs-evidence-label">What we detected</div>
                            <p className="cs-evidence-text">{detail.check}</p>
                          </div>
                          <div>
                            <div className="cs-evidence-label">Why it matters</div>
                            <p className="cs-evidence-text">
                              {detail.message}
                              <br />
                              <strong>−{detail.penalty ?? "?"} points</strong>
                            </p>
                          </div>
                        </>
                      )}
                      {item.type === "weak_evidence" && (
                        <>
                          <div>
                            <div className="cs-evidence-label">Requirement from postings</div>
                            <p className="cs-evidence-text cs-weak-quote">“{detail.requirement}”</p>
                          </div>
                          <div>
                            <div className="cs-evidence-label">Evidence strength</div>
                            <p className="cs-evidence-text">
                              {Number(detail.evidence_strength ?? 0).toFixed(2)}
                            </p>
                            <div className="cs-evidence-track">
                              <div
                                className="cs-evidence-fill"
                                style={{
                                  width: `${Math.max(0, Math.min(100, Number(detail.evidence_strength ?? 0) * 100))}%`,
                                }}
                              />
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* The old UI's second entry point into discovery: a CTA at
                the end of the action plan, so the next step after reading
                your fixes is visible without going back to the sidebar. */}
            <div className="cs-findjobs-cta">
              <div>
                <div className="cs-findjobs-title">See who&apos;s hiring for this role</div>
                <div className="cs-findjobs-sub">
                  Live postings, ranked against the resume you just analysed.
                </div>
              </div>
              <button
                type="button"
                className="cs-btn cs-btn-indigo"
                onClick={() => navigate("/app/jobs")}
              >
                Find matching jobs
              </button>
            </div>
          </section>

          {/* ---------- Skill coverage + Format ---------- */}
          <section className="cs-result-section cs-two-col">
            <div className="cs-panel" id="skillCoverageSection">
              <div className="cs-section-head cs-section-head-flush">
                <h2>Skill coverage</h2>
              </div>
              {(["technical", "professional"] as const).map((category) => {
                const group = byCategory[category] || {};
                const matched = group.matched || [];
                const missing = group.missing || [];
                const total = matched.length + missing.length;
                const muted = category === "professional";
                const label = category === "technical" ? "technical skills" : "professional skills";

                return (
                  <div
                    key={category}
                    className={cn("cs-skill-block", muted && "cs-skill-block-muted")}
                  >
                    <div className="cs-skill-heading">
                      <span className="cs-skill-title">
                        {category === "technical" ? "Technical skills" : "Professional skills"}
                      </span>
                      {total > 0 && (
                        <span className="cs-skill-stats">
                          {matched.length} of {total} matched ·{" "}
                          {Math.round((group.coverage ?? 0) * 100)}% coverage
                        </span>
                      )}
                    </div>

                    {total === 0 ? (
                      <div className="cs-chip-empty">
                        No {label} appeared in the sampled postings
                      </div>
                    ) : (
                      <>
                        <div className="cs-chip-group">
                          <div className="cs-chip-group-label">Matched</div>
                          <div className="cs-chip-row">
                            {matched.length === 0 && (
                              <span className="cs-chip-empty">No skills matched yet</span>
                            )}
                            {matched.map((s) => (
                              <span
                                key={s.skill}
                                className={cn("cs-chip cs-chip-matched", muted && "cs-chip-muted")}
                              >
                                {s.skill} · {s.count} of {postingsLabel}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="cs-chip-group">
                          <div className="cs-chip-group-label">Missing</div>
                          <div className="cs-chip-row">
                            {missing.length === 0 && (
                              <span className="cs-chip-empty">No missing skills — full coverage</span>
                            )}
                            {missing.map((s) => (
                              <span
                                key={s.skill}
                                className={cn(
                                  "cs-chip",
                                  s.frequency >= 0.3 ? "cs-chip-missing-high" : "cs-chip-missing-low",
                                  muted && "cs-chip-muted",
                                )}
                              >
                                {s.skill} · {s.count} of {postingsLabel}
                              </span>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="cs-panel" id="formatSection">
              <div className="cs-section-head cs-section-head-flush">
                <h2>Format</h2>
              </div>
              {(format.issues || []).length === 0 ? (
                <div className="cs-all-clear">✓ All 9 parseability checks passed</div>
              ) : (
                (format.issues || []).map((issue) => (
                  <div key={issue.message} className="cs-issue-row">
                    <span className="cs-issue-message">{issue.message}</span>
                    <span className="cs-issue-penalty">−{issue.penalty} pts</span>
                  </div>
                ))
              )}
            </div>
          </section>

          <div className="cs-results-footer">
            <div>
              Based on <strong>{postingsLabel}</strong> postings sampled{" "}
              {formatSampledDate(meta.sampled_at)}. Weights: keyword{" "}
              {(weights.keyword ?? 0).toFixed(2)}, semantic {(weights.semantic ?? 0).toFixed(2)},
              format {(weights.format ?? 0).toFixed(2)}, experience{" "}
              {(weights.experience ?? 0).toFixed(2)}.
            </div>
            <div>
              Projected scores are arithmetic under our own weighted model — not a guarantee of how
              any real ATS or recruiter will respond.
            </div>
          </div>
        </div>
      </main>

      <button type="button" className="cs-dash-signout" onClick={onSignOut}>
        Sign out
      </button>
    </div>
  );
}
