import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  Clock3,
  MapPin,
  Radio,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { JobMap } from "@/components/JobMap";
import { WorkspaceShell } from "@/components/SiteChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getJobMap, type JobMapResponse, type MapJob, type User } from "@/lib/api";

const SOURCE_OPTIONS = [
  { value: "", label: "All approved sources" },
  { value: "greenhouse", label: "Greenhouse" },
  { value: "lever", label: "Lever" },
  { value: "ashby", label: "Ashby" },
  { value: "jsearch", label: "JSearch" },
  { value: "adzuna", label: "Adzuna" },
];

function safeHttpUrl(value?: string | null) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:"
      ? parsed.href
      : null;
  } catch {
    return null;
  }
}

function formatDate(value?: string | null) {
  if (!value) return "Recently refreshed";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently refreshed";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function JobMapPage({
  user,
  onSignOut,
}: {
  user: User;
  onSignOut: () => void;
}) {
  const navigate = useNavigate();
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("Gujarat");
  const [source, setSource] = useState("");
  const [remote, setRemote] = useState(false);
  const [result, setResult] = useState<JobMapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<MapJob | null>(null);

  async function loadMap(filters = { role, location, source, remote }) {
    setLoading(true);
    setError("");
    try {
      const next = await getJobMap({ ...filters, limit: 250 });
      setResult(next);
      setSelected((current) =>
        current && next.jobs.some((job) => job.job_id === current.job_id)
          ? current
          : null,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The persisted job map is temporarily unavailable.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMap();
  }, []);

  const mappedJobs = useMemo(
    () => (result?.jobs || []).filter((job) => typeof job.latitude === "number"),
    [result?.jobs],
  );
  const companies = useMemo(
    () => new Set((result?.jobs || []).map((job) => job.company.toLowerCase())).size,
    [result?.jobs],
  );
  const onSelect = useCallback((job: MapJob) => setSelected(job), []);

  return (
    <WorkspaceShell user={user} onSignOut={onSignOut}>
      <div className="jobs-head">
        <div>
          <p className="section-kicker">Opportunity atlas</p>
          <h1 className="page-title mt-3">See where work is opening up.</h1>
          <p className="page-copy mt-3">
            A precomputed map from approved job APIs and official company ATS
            boards. Search first, then match a role against your résumé.
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/app/jobs")}>
          Resume matching
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>

      <form
        className="job-map-filters mt-8"
        onSubmit={(event) => {
          event.preventDefault();
          void loadMap();
        }}
      >
        <label>
          <span>Role or skill</span>
          <input
            type="search"
            value={role}
            onChange={(event) => setRole(event.target.value)}
            placeholder="Frontend developer"
          />
        </label>
        <label>
          <span>Location</span>
          <input
            type="search"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            placeholder="Ahmedabad or Bengaluru"
          />
        </label>
        <label>
          <span>Source</span>
          <select
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            {SOURCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="job-map-remote">
          <input
            type="checkbox"
            checked={remote}
            onChange={(event) => setRemote(event.target.checked)}
          />
          Remote only
        </label>
        <Button type="submit" disabled={loading}>
          {loading ? "Loading map…" : "Update map"}
          <Search data-icon="inline-start" />
        </Button>
      </form>

      {error && (
        <div className="form-error mt-6" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => void loadMap()}>
            Try again
          </button>
        </div>
      )}

      {loading && !result ? (
        <div className="job-map-loading mt-6" role="status" aria-live="polite">
          <span />
          <p>Loading the latest approved-source snapshot…</p>
        </div>
      ) : result ? (
        <>
          <div className="job-map-stats mt-7" aria-label="Job map summary">
            <div>
              <BriefcaseBusiness aria-hidden="true" />
              <strong>{result.jobs.length}</strong>
              <span>roles in view</span>
            </div>
            <div>
              <Building2 aria-hidden="true" />
              <strong>{companies}</strong>
              <span>companies hiring</span>
            </div>
            <div>
              <MapPin aria-hidden="true" />
              <strong>{mappedJobs.length}</strong>
              <span>mapped locations</span>
            </div>
            <div>
              <Clock3 aria-hidden="true" />
              <strong>{formatDate(result.meta.last_ingested_at)}</strong>
              <span>last snapshot</span>
            </div>
          </div>

          <section className="job-map-panel mt-5" aria-label="Job opportunity map and list">
            <div className="job-map-visual">
              <JobMap jobs={mappedJobs} selected={selected} onSelect={onSelect} />
            </div>
            <div className="job-map-list" aria-label="Mapped jobs">
              <div className="job-map-list-head">
                <div>
                  <p className="section-kicker">Live snapshot</p>
                  <h2>Roles on the map</h2>
                </div>
                <SlidersHorizontal aria-hidden="true" />
              </div>
              <div className="job-map-list-scroll">
                {result.jobs.map((job) => {
                  const applyUrl = safeHttpUrl(job.url);
                  return (
                    <article
                      key={job.job_id}
                      className={selected?.job_id === job.job_id ? "job-map-item job-map-item-active" : "job-map-item"}
                    >
                      <button
                        type="button"
                        onClick={() => setSelected(job)}
                        aria-label={`Show ${job.title} at ${job.company} on the map`}
                      >
                        <span className="job-map-item-title">{job.title}</span>
                        <span className="job-map-item-company">{job.company}</span>
                        <span className="job-map-item-location">
                          <MapPin aria-hidden="true" />
                          {job.location}
                        </span>
                        <span className="job-map-item-meta">
                          <Badge variant="secondary">{job.source_label}</Badge>
                          {job.is_remote && <Badge variant="success">Remote</Badge>}
                          <time dateTime={job.posted_at || job.last_seen_at}>
                            {formatDate(job.posted_at || job.last_seen_at)}
                          </time>
                        </span>
                      </button>
                      {applyUrl && (
                        <a href={applyUrl} target="_blank" rel="noreferrer noopener">
                          View posting
                          <ArrowRight aria-hidden="true" />
                        </a>
                      )}
                    </article>
                  );
                })}
                {!result.jobs.length && (
                  <div className="job-map-empty">
                    <Radio aria-hidden="true" />
                    <h3>No mapped roles match yet.</h3>
                    <p>
                      Run the scheduled ingestion command or widen the location
                      filter to India.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>
          <p className="job-map-notice mt-4">{result.notice}</p>
        </>
      ) : null}
    </WorkspaceShell>
  );
}
