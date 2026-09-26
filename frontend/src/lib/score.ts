import type { Analysis } from "@/lib/api";

export const componentMeta = [
  {
    key: "keyword",
    label: "Market language",
    shortLabel: "Keywords",
    note: "Evidence of role-specific skills",
    weight: 40,
  },
  {
    key: "semantic",
    label: "Evidence quality",
    shortLabel: "Semantics",
    note: "How specifically your experience supports the role",
    weight: 25,
  },
  {
    key: "format",
    label: "Parser readiness",
    shortLabel: "Format",
    note: "Whether an ATS can read the document cleanly",
    weight: 20,
  },
  {
    key: "experience",
    label: "Seniority fit",
    shortLabel: "Experience",
    note: "Alignment with the role's expected background",
    weight: 15,
  },
] as const;

export function weakestKey(subscores: Record<string, number>) {
  return componentMeta.reduce(
    (lowest, item) =>
      Number(subscores[item.key] ?? 0) < Number(subscores[lowest.key] ?? 0)
        ? item
        : lowest,
    componentMeta[0],
  ).key;
}

export function verdictText(subscores: Record<string, number>) {
  const key = weakestKey(subscores);
  const labels: Record<string, string> = {
    keyword: "Your market language needs attention.",
    semantic: "Your evidence needs to be more specific.",
    format: "Your formatting is costing reach.",
    experience: "Your experience signal is a little thin.",
  };
  return labels[key];
}

export function getSavedAnalysis(): Analysis | null {
  try {
    const raw = sessionStorage.getItem("careerstack_analysis");
    return raw ? (JSON.parse(raw) as Analysis) : null;
  } catch {
    return null;
  }
}

/** Persist the analysis the dashboard is showing, so opening one from
    History survives a reload the same way a fresh analysis does. */
export function saveAnalysis(analysis: Analysis) {
  try {
    sessionStorage.setItem("careerstack_analysis", JSON.stringify(analysis));
  } catch {
    // Private-mode storage or a quota limit: the page still renders from
    // component state, it just will not survive a reload.
  }
}

export function formatActionType(value: string) {
  return value.replaceAll("_", " ");
}
