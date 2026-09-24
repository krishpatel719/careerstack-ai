import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  ChevronRight,
  MapPinned,
  MoveUpRight,
  Search,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { WorkspaceShell } from "@/components/SiteChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import {
  getDiscovery,
  searchOpportunities,
  startDiscovery,
  type Analysis,
  type Job,
  type OpportunitySearch,
  type User,
} from "@/lib/api";
import { getSavedAnalysis } from "@/lib/score";

export function JobsPage({
  user,
  onSignOut,
}: {
  user: User;
  onSignOut: () => void;
}) {
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<Analysis | null>(getSavedAnalysis);
  const [run, setRun] = useState<{
    status?: string;
    jobs: Job[];
    widened?: boolean | { from: string; to: string; reason: string } | null;
    stats?: Record<string, number>;
    target?: { role: string; location: string };
    notice?: string;
  } | null>(null);
  const [opportunityMode, setOpportunityMode] = useState(false);
  const [opportunityRole, setOpportunityRole] = useState(
    getSavedAnalysis()?.role || "Backend Developer",
  );
  const [opportunityLocation, setOpportunityLocation] = useState(
    getSavedAnalysis()?.location || "Ahmedabad",
  );
  const [remote, setRemote] = useState(false);
  const [salary, setSalary] = useState(false);
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState<"match" | "recent">("match");
  const [busy, setBusy] = useState(false);
  const [searchStage, setSearchStage] = useState("Preparing your search");
  const pollGeneration = useRef(0);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  const locationSummary = useMemo(() => {
    const counts = new Map<string, number>();
    for (const job of run?.jobs || []) {
      const location = job.location?.split(",")[0]?.trim() || "Location not listed";
      counts.set(location, (counts.get(location) || 0) + 1);
    }
    return [...counts.entries()].sort((left, right) => right[1] - left[1]);
  }, [run?.jobs]);
  const filtered = useMemo(
    () =>
      (run?.jobs || [])
        .filter(
          (job) =>
            (!remote || job.is_remote) &&
            (!salary || job.salary_max) &&
            job.match_score >= minScore,
        )
        .sort((left, right) =>
          sortBy === "match"
            ? right.match_score - left.match_score
            : new Date(right.posted_at || 0).getTime() -
              new Date(left.posted_at || 0).getTime(),
        ),
    [run, remote, salary, minScore, sortBy],
  );

  useEffect(() => {
    const saved = getSavedAnalysis();
    if (saved) setAnalysis(saved);
    return () => {
      pollGeneration.current += 1;
    };
  }, []);

  async function exploreMarket() {
    setBusy(true);
    setError("");
    setOpportunityMode(true);
    setRun(null);
    setSearchStage("Searching approved job sources");
    try {
      const result = await searchOpportunities(
        opportunityRole,
        opportunityLocation,
        50,
      );
      setRun(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't search the approved job sources right now.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function discover() {
    if (!analysis) {
      navigate("/upload");
      return;
    }
    setOpportunityMode(false);
    setBusy(true);
    setRun(null);
    setError("");
    setSearchStage("Building search queries");
    const generation = ++pollGeneration.current;
    try {
      const started = await startDiscovery(analysis.analysis_id);
      if (generation !== pollGeneration.current) return;
      let current: Awaited<ReturnType<typeof getDiscovery>> | null = null;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        if (attempt < 5) setSearchStage("Building search queries");
        else if (attempt < 14) setSearchStage("Collecting live postings");
        else if (attempt < 24) setSearchStage("Scoring your resume");
        else setSearchStage("Preparing your results");
        await new Promise((resolve) => setTimeout(resolve, 900));
        if (generation !== pollGeneration.current) return;
        current = await getDiscovery(started.run_id);
        if (generation !== pollGeneration.current) return;
        if (
          current.status !== "pending" &&
          current.status !== "running"
        ) {
          break;
        }
      }
      if (!current) throw new Error("The job search timed out. Please retry.");
      if (current.status === "pending" || current.status === "running") {
        throw new Error(
          "The job search is taking longer than expected. Please retry in a moment.",
        );
      }
      if (current.error) throw new Error(current.error);
      setRun(current);
    } catch (err) {
      if (generation !== pollGeneration.current) return;
      setError(
        err instanceof Error ? err.message : "We couldn't find jobs right now.",
      );
    } finally {
      if (generation === pollGeneration.current) setBusy(false);
    }
  }

  return (
    <WorkspaceShell user={user} onSignOut={onSignOut}>
      <div className="jobs-head">
        <div>
          <p className="section-kicker">Market view</p>
          <h1 className="page-title mt-3">Roles worth a look.</h1>
          <p className="page-copy mt-3">
            {analysis ? (
              <>
                Comparing against{" "}
                <span className="font-semibold text-foreground">
                  {analysis.role}
                </span>{" "}
                in {analysis.location}.
              </>
            ) : (
              "Start with an analysis to unlock a tailored market view."
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {analysis && (
            <Button onClick={discover} disabled={busy}>
              {busy && !opportunityMode
                ? "Searching the market…"
                : opportunityMode
                  ? "Match my resume"
                  : run
                    ? "Refresh results"
                    : "Find matching roles"}
              <Search data-icon="inline-start" />
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => navigate("/app/jobs/map")}
          >
            Open job map
            <MapPinned data-icon="inline-end" />
          </Button>
          <Button
            variant="outline"
            onClick={exploreMarket}
            disabled={busy}
          >
            {busy && opportunityMode
              ? "Exploring sources…"
              : "Explore opportunities"}
            <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      </div>
      <div className="opportunity-search mt-8">
        <div className="opportunity-search-copy">
          <p className="section-kicker">Opportunity map</p>
          <h2>Search the live market, then match later.</h2>
          <p>
            Browse approved APIs and official company ATS boards without
            uploading a resume. We widen thin city searches to India for
            better coverage.
          </p>
        </div>
        <form
          className="opportunity-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            void exploreMarket();
          }}
        >
          <label>
            <span>Role</span>
            <input
              value={opportunityRole}
              onChange={(event) => setOpportunityRole(event.target.value)}
              placeholder="e.g. Backend Developer"
              required
              minLength={2}
            />
          </label>
          <label>
            <span>Location</span>
            <input
              value={opportunityLocation}
              onChange={(event) => setOpportunityLocation(event.target.value)}
              placeholder="e.g. Ahmedabad"
              required
              minLength={2}
            />
          </label>
          <Button type="submit" disabled={busy}>
            Search sources
            <ArrowRight data-icon="inline-end" />
          </Button>
        </form>
      </div>
      {run && (
        <div className="filter-bar mt-8">
          <span className="mr-auto text-sm font-semibold">Refine results</span>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Sort
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as "match" | "recent")}
              className="h-8 rounded-md border border-border bg-card px-2 text-xs font-semibold text-foreground"
              aria-label="Sort job results"
            >
              <option value="match">Best match</option>
              <option value="recent">Most recent</option>
            </select>
          </label>
          <FilterCheck checked={remote} onChange={setRemote}>
            Remote only
          </FilterCheck>
          <FilterCheck checked={salary} onChange={setSalary}>
            Has salary
          </FilterCheck>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Min match
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={minScore}
              onChange={(event) => setMinScore(Number(event.target.value))}
              className="w-24 accent-[hsl(226_92%_56%)]"
            />
            <span className="font-mono font-semibold text-foreground">
              {minScore}%
            </span>
          </label>
          {(remote || salary || minScore > 0) && (
            <button
              type="button"
              className="text-xs font-semibold text-accent underline underline-offset-4"
              onClick={() => {
                setRemote(false);
                setSalary(false);
                setMinScore(0);
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="form-error mt-6">
          {error}
        </p>
      )}
      {busy && (
        <div
          className="job-skeletons mt-10"
          role="status"
          aria-live="polite"
          aria-label="Searching the market"
        >
          <p className="mb-2 text-sm text-muted-foreground">{searchStage}</p>
          {[1, 2, 3].map((item) => (
            <div key={item} className="h-28 animate-pulse rounded-2xl bg-muted" />
          ))}
        </div>
      )}
      {run && !busy && (
        <>
          <div className="results-meta mt-8">
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">
                {filtered.length}
              </span>{" "}
              roles surfaced
              {run.widened ? " · search was widened for better coverage" : ""}
            </p>
            <span className="font-mono text-xs text-muted-foreground">
              {opportunityMode ? "ranked by market freshness" : "sorted by match"}
            </span>
          </div>
          {opportunityMode && locationSummary.length > 0 && (
            <div className="opportunity-map mt-4" aria-label="Opportunity locations">
              <div className="opportunity-map-heading">
                <div>
                  <p className="section-kicker">Coverage map</p>
                  <h2>Where the opportunities are</h2>
                </div>
                <span>{run.target?.location || opportunityLocation}</span>
              </div>
              <div className="opportunity-location-list">
                {locationSummary.map(([location, count]) => (
                  <div className="opportunity-location" key={location}>
                    <span className="opportunity-location-dot" />
                    <span>{location}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="jobs-list mt-4">
            {filtered.map((job) => (
              <JobCard
                key={job.fingerprint}
                job={job}
                opportunityMode={opportunityMode}
                onOpen={() => setSelected(job)}
              />
            ))}
            {!filtered.length && (
              <div className="empty-panel">
                <Search className="size-7 text-muted-foreground" />
                <h2 className="mt-4 font-display text-3xl tracking-[-.04em]">
                  No roles match those filters.
                </h2>
                <button
                  className="mt-3 text-sm font-semibold text-accent underline underline-offset-4"
                  onClick={() => {
                    setRemote(false);
                    setSalary(false);
                    setMinScore(0);
                  }}
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>
        </>
      )}
      {!run && !busy && !error && (
        <div className="empty-panel mt-10">
          <div className="empty-icon">
            <BriefcaseBusiness className="size-6" />
          </div>
          <h2 className="mt-5 font-display text-3xl tracking-[-.04em]">
            Search the live market.
          </h2>
          <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
            We’ll sample current postings and rank them against the resume you
            just analysed.
          </p>
          <Button className="mt-6" onClick={discover} disabled={!analysis}>
            Start the search
            <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      )}
      {selected && (
        <JobDialog
          job={selected}
          opportunityMode={opportunityMode}
          onClose={() => setSelected(null)}
        />
      )}
    </WorkspaceShell>
  );
}

function FilterCheck({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-[hsl(226_92%_56%)]"
      />
      {children}
    </label>
  );
}
function JobCard({
  job,
  onOpen,
  opportunityMode = false,
}: {
  job: Job;
  onOpen: () => void;
  opportunityMode?: boolean;
}) {
  return (
    <article className="job-card group relative">
      <button
        type="button"
        className="absolute inset-0 z-10 rounded-[var(--radius)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={onOpen}
        aria-label={`View details for ${job.title} at ${job.company}`}
      />
      <div className="pointer-events-none">
      <div className="job-match">
        <span>{Math.round(job.match_score)}</span>
        <small>{opportunityMode ? "market" : "match"}</small>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3>{job.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {job.company} · {job.location}
            </p>
          </div>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-1 group-hover:text-accent" />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {job.matched_skills.slice(0, 5).map((skill) => (
            <Badge key={skill} variant="success">
              {skill}
            </Badge>
          ))}
          {job.missing_skills.slice(0, 3).map((skill) => (
            <Badge key={skill} variant="warning">
              {skill}
            </Badge>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <span>{job.is_remote ? "Remote" : "On-site / hybrid"}</span>
          {job.salary_min && (
            <span className="font-mono">
              {job.salary_currency || "$"}
              {Math.round(job.salary_min).toLocaleString()}
              {job.salary_max
                ? ` – ${Math.round(job.salary_max).toLocaleString()}`
                : "+"}
            </span>
          )}
          <span>{job.source_label}</span>
          {job.meta.low_confidence && (
            <Badge variant="warning">Low confidence</Badge>
          )}
        </div>
      </div>
      </div>
    </article>
  );
}
function JobDialog({
  job,
  onClose,
  opportunityMode = false,
}: {
  job: Job;
  onClose: () => void;
  opportunityMode?: boolean;
}) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <p className="section-kicker">{job.source_label}</p>
          <DialogTitle className="pr-6">{job.title}</DialogTitle>
          <DialogDescription>
            {job.company} · {job.location} · {Math.round(job.match_score)}%
            {opportunityMode ? " market score" : " match"}
          </DialogDescription>
        </DialogHeader>
        <div className="job-dialog-score">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">
              {opportunityMode ? "Market signal" : "Your match"}
            </span>
            <span className="font-display text-3xl">
              {Math.round(job.match_score)}
              <span className="text-base text-muted-foreground">/100</span>
            </span>
          </div>
          <Progress
            className="mt-3"
            value={job.match_score}
            aria-label={`Job match ${Math.round(job.match_score)} out of 100`}
          />
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <p className="section-kicker">Matched</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {job.matched_skills.length ? (
                job.matched_skills.map((skill) => (
                  <Badge key={skill} variant="success">
                    {skill}
                  </Badge>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  No matched skills named in the visible description.
                </p>
              )}
            </div>
          </div>
          <div>
            <p className="section-kicker">To strengthen</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {job.missing_skills.length ? (
                job.missing_skills.map((skill) => (
                  <Badge key={skill} variant="warning">
                    {skill}
                  </Badge>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  No missing skills named.
                </p>
              )}
            </div>
          </div>
        </div>
        <div>
          <p className="section-kicker">Role context</p>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
            {job.description ||
              "The provider did not include a role description in this result."}
          </p>
        </div>
        {job.url && (
          <Button asChild variant="outline">
            <a href={job.url} target="_blank" rel="noreferrer">
              Open original posting
              <MoveUpRight data-icon="inline-end" />
            </a>
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
