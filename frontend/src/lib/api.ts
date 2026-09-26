export type User = {
  user_id: string;
  email: string;
  name: string;
  created_at: string;
};
export type Analysis = {
  analysis_id: string;
  filename: string;
  role: string;
  location: string;
  created_at: string;
  overall_score?: number;
  band?: string;
  subscores?: Record<string, number>;
  weights?: Record<string, number>;
  dimensions?: Array<{
    name: string;
    score: number;
    status: "good" | "fair" | "weak";
    note: string;
  }>;
  format_detail?: {
    score?: number;
    points_earned?: number;
    points_possible?: number;
    issues?: Array<{ message: string; penalty: number }>;
  };
  keyword_detail?: {
    by_category?: Record<
      string,
      {
        matched?: Array<{ skill: string; count: number }>;
        missing?: Array<{ skill: string; count: number; frequency: number }>;
        coverage?: number;
      }
    >;
  };
  semantic_detail?: { weakest_requirements?: Array<{ requirement: string }> };
  action_plan?: {
    projected_score_under_our_model?: number;
    items?: Array<{
      action: string;
      type: string;
      effort?: string;
      estimated_gain?: number;
      quantified?: boolean;
      /** Shape varies by `type`; ats.py emits exactly these fields per
          kind, which is what the dashboard's evidence panels render. */
      detail?: {
        // missing_skill
        skill?: string;
        count?: number;
        // format_issue
        check?: string;
        message?: string;
        penalty?: number;
        // weak_evidence
        requirement?: string;
        evidence_strength?: number;
      };
    }>;
  };
  role_profile_meta?: {
    postings_sampled?: number;
    sampled_at?: string;
    sample_quality?: "low" | "limited" | "normal" | string;
    score_confidence?: number;
    confidence_reasons?: string[];
    sparse_profile?: boolean;
    location_fallback?: {
      requested_location?: string;
      used_location?: string;
      requested_postings_sampled?: number;
    } | null;
  };
  degraded?: boolean;
  degraded_message?: string | null;
  /** Only present on /api/analyses summary rows: format_detail.score
      rescaled to 0-100, so history can show both scores as pills. */
  parse_score?: number | null;
};

export type OpportunitySearch = {
  target: { role: string; location: string };
  requested_location: string;
  queries: string[];
  jobs: Job[];
  stats: Record<string, number>;
  widened?: { from: string; to: string; reason: string } | null;
  generated_at: string;
  notice: string;
};

export type Job = {
  fingerprint: string;
  source_label: string;
  title: string;
  company: string;
  location: string;
  is_remote: boolean;
  description?: string;
  url?: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  posted_at?: string;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  score_breakdown: Record<string, number>;
  meta: {
    description_truncated: boolean;
    low_confidence: boolean;
    skills_unscored: boolean;
  };
};

export type MapJob = {
  job_id: string;
  title: string;
  company: string;
  location: string;
  city?: string | null;
  state?: string | null;
  country: string;
  location_quality: "curated" | "unmapped";
  source: string;
  source_label: string;
  url?: string | null;
  description?: string;
  description_truncated: boolean;
  is_remote?: boolean | null;
  employment_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  posted_at?: string | null;
  last_seen_at: string;
  longitude?: number;
  latitude?: number;
};

export type JobMapResponse = {
  jobs: MapJob[];
  meta: {
    count: number;
    limit: number;
    mapped: number;
    last_ingested_at?: string | null;
  };
  notice: string;
};

const TOKEN_KEY = "careerstack_token";
const SESSION_KEY_PREFIX = "careerstack_";
export const AUTH_EXPIRED_EVENT = "careerstack:auth-expired";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) =>
  localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export function clearUserSession() {
  clearToken();
  try {
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key?.startsWith(SESSION_KEY_PREFIX)) sessionStorage.removeItem(key);
    }
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}

function formatDetailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail.trim();
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return null;
        const validation = item as {
          loc?: Array<string | number>;
          msg?: string;
          message?: string;
        };
        const location = validation.loc
          ?.filter(
            (part) =>
              typeof part === "string" &&
              part !== "body" &&
              part !== "query" &&
              part !== "path",
          )
          .at(-1);
        const message = validation.msg || validation.message;
        if (!message) return null;
        if (location === undefined) return message;
        const label = String(location).replaceAll("_", " ");
        return `${label.charAt(0).toUpperCase()}${label.slice(1)}: ${message}`;
      })
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join(" ");
  }
  if (detail && typeof detail === "object") {
    const record = detail as { message?: unknown; error?: unknown };
    if (record.message !== undefined) return formatDetailMessage(record.message);
    if (record.error !== undefined) return formatDetailMessage(record.error);
  }
  return "Something went wrong. Please try again.";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const authenticated = Boolean(token);
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail =
      (data as { detail?: unknown }).detail === undefined
        ? "Something went wrong. Please try again."
        : formatDetailMessage((data as { detail?: unknown }).detail);
    const error = new Error(detail) as Error & { status?: number };
    error.status = response.status;
    if (response.status === 401 && authenticated) {
      clearUserSession();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      }
    }
    throw error;
  }
  return data as T;
}

export async function login(email: string, password: string) {
  const result = await api<{ access_token: string; user: User }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
  setToken(result.access_token);
  return result.user;
}

export async function register(name: string, email: string, password: string) {
  const result = await api<{ access_token: string; user: User }>(
    "/api/auth/register",
    { method: "POST", body: JSON.stringify({ name, email, password }) },
  );
  setToken(result.access_token);
  return result.user;
}

export async function getMe() {
  return api<User>("/api/auth/me");
}

export async function deleteAccount() {
  return api<void>("/api/account", {
    method: "DELETE",
    body: JSON.stringify({ confirm: true }),
  });
}

export async function analyzeResume(
  file: File,
  role: string,
  location: string,
) {
  const form = new FormData();
  form.append("file", file);
  form.append("role", role);
  form.append("location", location);
  return api<Analysis>("/api/analyze", { method: "POST", body: form });
}

export async function listAnalyses() {
  return api<Analysis[]>("/api/analyses");
}

export async function getAnalysis(id: string) {
  return api<Analysis>(`/api/analyze/${id}`);
}

export async function searchOpportunities(
  role: string,
  location: string,
  limit = 50,
) {
  const params = new URLSearchParams({ role, location, limit: String(limit) });
  return api<OpportunitySearch>(`/api/opportunities?${params.toString()}`);
}

export async function getJobMap(filters: {
  role?: string;
  location?: string;
  company?: string;
  source?: string;
  remote?: boolean;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const suffix = params.size ? `?${params.toString()}` : "";
  return api<JobMapResponse>(`/api/job-map${suffix}`);
}

export async function startDiscovery(analysisId: string) {
  return api<{ run_id: string; status: string }>("/api/discovery/run", {
    method: "POST",
    body: JSON.stringify({ analysis_id: analysisId }),
  });
}

export async function getDiscovery(runId: string) {
  return api<{
    run_id: string;
    status: string;
    target: { role: string; location: string };
    stats?: Record<string, number>;
    widened?: boolean;
    jobs: Job[];
    error?: string | null;
  }>(`/api/discovery/${runId}`);
}
