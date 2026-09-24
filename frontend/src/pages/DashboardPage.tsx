import { useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  FileText,
  Gauge,
  Search,
  Upload,
  Zap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { WorkspaceShell } from "@/components/SiteChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { Analysis, User } from "@/lib/api";
import {
  componentMeta,
  formatActionType,
  getSavedAnalysis,
  verdictText,
  weakestKey,
} from "@/lib/score";
import { cn } from "@/lib/utils";

export function DashboardPage({
  user,
  onSignOut,
}: {
  user: User;
  onSignOut: () => void;
}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(getSavedAnalysis);
  const navigate = useNavigate();

  useEffect(() => {
    if (analysis)
      sessionStorage.setItem("careerstack_analysis", JSON.stringify(analysis));
  }, [analysis]);

  if (!analysis)
    return (
      <WorkspaceShell user={user} onSignOut={onSignOut}>
        <EmptyAnalysis onUpload={() => navigate("/upload")} />
      </WorkspaceShell>
    );

  const score = Number(analysis.overall_score ?? 0);
  const parseScore = Math.round(
    Number(analysis.format_detail?.score ?? 0) * 100,
  );
  const meta = analysis.role_profile_meta || {};
  const subscores = analysis.subscores || {};
  const actionItems = analysis.action_plan?.items || [];
  const lowest = componentMeta.find(
    (item) => item.key === weakestKey(subscores),
  );

  return (
    <WorkspaceShell user={user} onSignOut={onSignOut}>
      <div className="dashboard-head">
        <div>
          <p className="section-kicker">Analysis workspace</p>
          <h1 className="page-title mt-3">Your resume analysis.</h1>
          <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <FileText className="size-4" />
            {analysis.filename}
            <span className="text-border">/</span>
            {analysis.role}
            <span className="text-border">/</span>
            {analysis.location}
          </p>
        </div>
        <div className="sample-status">
          <span className="status-dot" />
          {meta.postings_sampled ?? "N/A"} postings sampled
          {meta.sampled_at
            ? ` · ${new Date(meta.sampled_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
            : ""}
        </div>
      </div>
      <section className="dashboard-hero-grid mt-8">
        <div className="score-panel">
          <div className="score-panel-copy">
            <div className="flex items-center gap-3">
              <Badge variant="accent">{analysis.band || "Needs review"}</Badge>
              <span className="font-mono text-[10px] uppercase tracking-[.14em] text-muted-foreground">
                Role fit
              </span>
            </div>
            <h2 className="mt-5 max-w-lg font-display text-3xl leading-tight tracking-[-.04em] sm:text-4xl">
              {verdictText(subscores)}
            </h2>
            <p className="mt-4 max-w-md text-sm leading-7 text-muted-foreground">
              Your lowest signal is{" "}
              <span className="font-semibold text-foreground">
                {lowest?.label.toLowerCase()}
              </span>
              . Fixing it is the clearest path to a stronger application.
            </p>
            <div className="score-metrics">
              <Metric
                label="ATS parse score"
                value={parseScore}
                suffix="/ 100"
              />
              <Metric
                label="Potential after fixes"
                value={Number(
                  analysis.action_plan?.projected_score_under_our_model ??
                    score,
                ).toFixed(1)}
                suffix="projected"
                accent
              />
            </div>
            <ScoreContext meta={analysis.role_profile_meta} />
          </div>
          <ScoreRing score={score} />
        </div>
        <div className="next-move-panel">
          <div className="panel-topline">
            <div>
              <p className="section-kicker">The short version</p>
              <h2 className="mt-2 font-display text-3xl tracking-[-.04em]">
                What to do next
              </h2>
            </div>
            <Zap className="size-5 text-accent" aria-hidden="true" />
          </div>
          <div className="mt-7 grid gap-4">
            {actionItems.slice(0, 3).map((item, index) => (
              <div key={`${item.action}-${index}`} className="next-move-item">
                <span className="next-move-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <p>{item.action}</p>
              </div>
            ))}
            {!actionItems.length && (
              <p className="text-sm leading-6 text-muted-foreground">
                No critical changes found. Your resume is in good shape.
              </p>
            )}
          </div>
          <Button
            variant="outline"
            className="mt-7 w-full"
            onClick={() =>
              document
                .getElementById("improvements")
                ?.scrollIntoView({ behavior: "smooth" })
            }
          >
            View full action plan
            <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      </section>
      <section className="signals-section mt-5">
        <div className="section-inline-head">
          <div>
            <p className="section-kicker">Signal breakdown</p>
            <h2 className="mt-2 font-display text-3xl tracking-[-.04em]">
              The four numbers behind the fit.
            </h2>
          </div>
          <span className="font-mono text-xs text-muted-foreground">
            weighted model · v2.4
          </span>
        </div>
        <div className="signals-grid mt-5">
          {componentMeta.map((item) => {
            const value = Number(subscores[item.key] ?? 0);
            return (
              <div key={item.key} className="signal-card">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold">{item.label}</p>
                  <span className="font-mono text-xs text-muted-foreground">
                    {Math.round(
                      Number(
                        analysis.weights?.[item.key] ?? item.weight / 100,
                      ) * 100,
                    )}
                    %
                  </span>
                </div>
                <p className="signal-number">{value.toFixed(1)}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {item.note}
                </p>
                <Progress
                  className="mt-5"
                  value={value}
                  aria-label={`${item.label} score ${value.toFixed(1)} out of 100`}
                />
              </div>
            );
          })}
        </div>
      </section>
      <section className="detail-grid mt-5">
        <div id="improvements" className="detail-panel">
          <div className="panel-topline">
            <div>
              <p className="section-kicker">Action plan</p>
              <h2 className="mt-2 font-display text-3xl tracking-[-.04em]">
                Suggested improvements
              </h2>
            </div>
            <Badge variant="secondary">{actionItems.length} found</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Ranked by the impact each change is expected to make.
          </p>
          <div className="mt-6 grid gap-3">
            {actionItems.map((item, index) => (
              <div key={`${item.action}-${index}`} className="action-row">
                <span className="action-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-6">
                    {item.action}
                  </p>
                  <p className="mt-1 text-xs capitalize text-muted-foreground">
                    {formatActionType(item.type)}
                    {item.effort ? ` · ${item.effort} effort` : ""}
                    {item.quantified === false ? " · evidence action" : ""}
                  </p>
                </div>
                {item.quantified === false ? (
                  <Badge
                    variant="warning"
                    className="shrink-0 whitespace-nowrap"
                    title="This evidence action is not assigned an estimated score gain."
                  >
                    Unquantified
                  </Badge>
                ) : (
                  <span className="shrink-0 text-xs font-semibold text-emerald-700">
                    +{Number(item.estimated_gain ?? 0).toFixed(1)}
                  </span>
                )}
              </div>
            ))}
            {!actionItems.length && (
              <p className="py-4 text-sm text-muted-foreground">
                No changes recommended.
              </p>
            )}
          </div>
        </div>
        <div className="detail-panel">
          <div className="panel-topline">
            <div>
              <p className="section-kicker">Coverage</p>
              <h2 className="mt-2 font-display text-3xl tracking-[-.04em]">
                What the market sees
              </h2>
            </div>
            <Gauge className="size-5 text-primary" />
          </div>
          <div className="mt-7 grid gap-7">
            <SkillCategory
              title="Technical skills"
              group={analysis.keyword_detail?.by_category?.technical}
            />
            <SkillCategory
              title="Professional skills"
              group={analysis.keyword_detail?.by_category?.professional}
            />
            <div className="border-t border-border/70 pt-5">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">Format checks</p>
                <span className="font-mono text-sm">
                  {analysis.format_detail?.points_earned ?? "N/A"}
                  <span className="text-muted-foreground">
                    /{analysis.format_detail?.points_possible ?? "N/A"}
                  </span>
                </span>
              </div>
              <div className="mt-3 grid gap-2">
                {analysis.format_detail?.issues?.length ? (
                  analysis.format_detail.issues.map((issue) => (
                    <div
                      key={issue.message}
                      className="flex items-start gap-2 text-xs leading-5 text-muted-foreground"
                    >
                      <span className="mt-1 size-1.5 shrink-0 rounded-full bg-amber-600" />
                      {issue.message}
                      <span className="ml-auto shrink-0 font-mono text-amber-700">
                        −{issue.penalty}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="flex items-center gap-2 text-xs text-emerald-700">
                    <Check className="size-3.5" />
                    All parser checks passed.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="jobs-cta mt-5">
        <div>
          <p className="section-kicker">Keep moving</p>
          <h2 className="mt-2 font-display text-2xl">
            See the roles your resume is ready for.
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Compare your current signal against live opportunities.
          </p>
        </div>
        <Button variant="accent" onClick={() => navigate("/app/jobs")}>
          Find matching roles
          <ArrowRight data-icon="inline-end" />
        </Button>
      </section>
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Scores are arithmetic under our weighted model, not a prediction of any
        specific employer’s ATS.
      </p>
    </WorkspaceShell>
  );
}

function ScoreContext({
  meta,
}: {
  meta: Analysis["role_profile_meta"];
}) {
  const quality = meta?.sample_quality?.toLowerCase();
  const isLimited = quality === "low" || quality === "limited";
  const fallback = meta?.location_fallback;
  if (!isLimited && !fallback) return null;

  const confidence = Number(meta?.score_confidence);
  const confidencePercent = Number.isFinite(confidence)
    ? `${Math.round(Math.max(0, Math.min(1, confidence)) * 100)}%`
    : null;
  const qualityLabel = quality
    ? `${quality.charAt(0).toUpperCase()}${quality.slice(1)}`
    : "Limited";

  return (
    <aside
      className="mt-5 max-w-lg rounded-xl border border-white/20 bg-white/10 p-4 text-sm text-primary-foreground"
      aria-label="Market sample confidence"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="warning">
          {isLimited ? `${qualityLabel} sample confidence` : "Location fallback used"}
        </Badge>
        {isLimited && confidencePercent && (
          <span className="font-mono text-xs text-primary-foreground/75">
            Sample quality: {qualityLabel} · Score confidence: {confidencePercent}
          </span>
        )}
      </div>
      {fallback?.used_location && (
        <p className="mt-3 text-xs leading-5 text-primary-foreground/75">
          Market data used <strong className="font-semibold text-primary-foreground">{fallback.used_location}</strong>
          {fallback.requested_location ? (
            <>
              {" "}instead of {fallback.requested_location}
            </>
          ) : null}
          {fallback.requested_postings_sampled !== undefined
            ? ` (${fallback.requested_postings_sampled} requested-location postings were usable).`
            : "."}
        </p>
      )}
      {isLimited && meta?.confidence_reasons?.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-primary-foreground/75">
          {meta.confidence_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}

function Metric({
  label,
  value,
  suffix,
  accent = false,
}: {
  label: string;
  value: number | string;
  suffix: string;
  accent?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-2 font-display text-3xl", accent && "text-accent")}>
        {value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{suffix}</p>
    </div>
  );
}
function ScoreRing({ score }: { score: number }) {
  const reduceMotion = useReducedMotion();
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  return (
    <div
      className="score-ring"
      role="img"
      aria-label={`Role fit ${Math.round(score)} out of 100`}
    >
      <svg
        className="absolute inset-0 size-full -rotate-90"
        viewBox="0 0 112 112"
      >
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke="hsl(214 26% 91%)"
          strokeWidth="7"
        />
        <motion.circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{
            strokeDashoffset: circumference - (circumference * score) / 100,
          }}
          transition={{ duration: reduceMotion ? 0 : 1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="text-center">
        <p className="font-display text-5xl tracking-[-.07em]">
          {Math.round(score)}
        </p>
        <p className="text-[10px] text-muted-foreground">out of 100</p>
      </div>
    </div>
  );
}
function EmptyAnalysis({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="empty-panel">
      <Search className="size-7 text-muted-foreground" />
      <h2 className="mt-4 font-display text-3xl tracking-[-.04em]">
        No analysis selected.
      </h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
        Upload a resume to see your score, the evidence behind it, and a short
        list of changes worth making.
      </p>
      <Button className="mt-6" onClick={onUpload}>
        <Upload data-icon="inline-start" />
        Analyse a resume
      </Button>
    </div>
  );
}
function SkillCategory({
  title,
  group,
}: {
  title: string;
  group?: {
    matched?: Array<{ skill: string; count: number }>;
    missing?: Array<{ skill: string; count: number; frequency: number }>;
    coverage?: number;
  };
}) {
  const matched = group?.matched || [];
  const missing = group?.missing || [];
  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold">{title}</p>
        <span className="text-xs text-muted-foreground">
          {Math.round(Number(group?.coverage ?? 0) * 100)}% covered
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {matched.slice(0, 8).map((item) => (
          <Badge key={item.skill} variant="success">
            {item.skill}
          </Badge>
        ))}
        {missing.slice(0, 5).map((item) => (
          <Badge key={item.skill} variant="warning">
            {item.skill}
          </Badge>
        ))}
        {!matched.length && !missing.length && (
          <span className="text-xs text-muted-foreground">
            No skills surfaced in this category.
          </span>
        )}
      </div>
    </div>
  );
}
