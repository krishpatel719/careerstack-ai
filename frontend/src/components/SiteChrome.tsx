import { useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BriefcaseBusiness,
  ChevronDown,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  MapPinned,
  Menu,
  Plus,
  Settings2,
  UserRound,
  X,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getAnalysis, listAnalyses, type Analysis, type User } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="brand-mark group" aria-label="CareerStack home">
      <span className="brand-symbol" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {!compact && (
        <span className="brand-wordmark">
          CareerStack <span>AI</span>
        </span>
      )}
    </Link>
  );
}

export function SiteHeader({
  user,
  onSignOut,
  theme = "light",
}: {
  user?: User | null;
  onSignOut?: () => void;
  theme?: "light" | "dark";
}) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  function goToMethod() {
    setOpen(false);
    navigate("/#method");
  }

  return (
    <header className={cn("site-header", theme === "dark" && "site-header-dark")}>
      <div className="site-container flex h-18 items-center justify-between">
        <Brand />
        <nav
          className="hidden items-center gap-7 md:flex"
          aria-label="Primary navigation"
        >
          <button className="nav-link" onClick={goToMethod}>
            How it works
          </button>
          <button className="nav-link" onClick={goToMethod}>
            Scoring method
          </button>
          <span className="nav-divider" aria-hidden="true" />
          {user ? (
            <>
              <span className="max-w-40 truncate text-sm text-muted-foreground">
                {user.name.split(" ")[0]}
              </span>
              <ButtonLike onClick={onSignOut}>Sign out</ButtonLike>
            </>
          ) : (
            <button
              className="nav-link inline-flex items-center gap-2"
              onClick={() => navigate("/auth")}
            >
              <UserRound className="size-4" aria-hidden="true" /> Sign in
            </button>
          )}
        </nav>
        <div className="flex items-center gap-2 md:hidden">
          <button
            className="button button-primary h-10 px-4"
            onClick={() => navigate(user ? "/upload" : "/auth")}
          >
            {user ? "New analysis" : "Start"}
          </button>
          <button
            className="button button-quiet size-10 p-0"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border md:hidden"
          >
            <nav
              className="site-container flex flex-col gap-1 py-4"
              aria-label="Mobile navigation"
            >
              <button className="mobile-nav-link" onClick={goToMethod}>
                How it works
              </button>
              <button
                className="mobile-nav-link"
                onClick={() => {
                  setOpen(false);
                  navigate(user ? "/upload" : "/auth");
                }}
              >
                {user ? "New analysis" : "Start an analysis"}
              </button>
              {user && (
                <button className="mobile-nav-link" onClick={onSignOut}>
                  Sign out
                </button>
              )}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

function ButtonLike({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      className="nav-link inline-flex items-center gap-2"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function WorkspaceShell({
  user,
  onSignOut,
  children,
}: {
  user: User;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [history, setHistory] = useState<Analysis[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyState, setHistoryState] = useState<"loading" | "ready" | "error">("loading");
  const [openingAnalysisId, setOpeningAnalysisId] = useState<string | null>(null);
  const [failedAnalysis, setFailedAnalysis] = useState<Analysis | null>(null);
  const [historyOpenError, setHistoryOpenError] = useState("");
  const historyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistoryState("loading");
    listAnalyses()
      .then((items) => {
        setHistory(items);
        setHistoryState("ready");
      })
      .catch(() => {
        setHistory([]);
        setHistoryState("error");
      });
  }, [location.pathname]);

  useEffect(() => {
    if (!historyOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setHistoryOpen(false);
    }
    function closeOnOutsideClick(event: PointerEvent) {
      if (!historyRef.current?.contains(event.target as Node)) {
        setHistoryOpen(false);
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOnOutsideClick);
    };
  }, [historyOpen]);

  const nav = [
    { to: "/app", label: "Overview", icon: LayoutDashboard },
    { to: "/app/jobs", label: "Matching roles", icon: BriefcaseBusiness },
    { to: "/app/jobs/map", label: "Job map", icon: MapPinned },
    { to: "/account", label: "Account", icon: Settings2 },
  ];

  async function openAnalysis(analysis: Analysis) {
    setOpeningAnalysisId(analysis.analysis_id);
    setFailedAnalysis(null);
    setHistoryOpenError("");
    try {
      const fullAnalysis = await getAnalysis(analysis.analysis_id);
      sessionStorage.setItem(
        "careerstack_analysis",
        JSON.stringify(fullAnalysis),
      );
      setHistoryOpen(false);
      navigate("/app");
    } catch {
      setFailedAnalysis(analysis);
      setHistoryOpenError(
        "We couldn't open that analysis. Your saved data is still available. Try again.",
      );
    } finally {
      setOpeningAnalysisId(null);
    }
  }

  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <div className="site-container flex h-16 items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-5">
            <Brand />
            <span
              className="hidden h-5 w-px bg-border sm:block"
              aria-hidden="true"
            />
            <span className="hidden text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:block">
              Workspace
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="relative" ref={historyRef}>
              <button
                className="history-trigger"
                onClick={() => setHistoryOpen((value) => !value)}
                aria-expanded={historyOpen}
                aria-haspopup="menu"
                aria-controls="analysis-history-menu"
              >
                <History className="size-4" aria-hidden="true" />
                <span className="hidden sm:inline">Recent</span>
                <ChevronDown
                  className={cn(
                    "size-3.5 transition-transform",
                    historyOpen && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
              <AnimatePresence>
                {historyOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    id="analysis-history-menu"
                    role="menu"
                    aria-label="Saved analyses"
                    className="history-popover"
                  >
                    <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Saved analyses
                    </p>
                    {historyState === "loading" ? (
                      <p className="px-3 py-2 text-xs text-muted-foreground">Loading recent analyses...</p>
                    ) : historyState === "error" ? (
                      <p className="px-3 py-2 text-xs text-muted-foreground">Recent analyses are temporarily unavailable.</p>
                    ) : history.length ? (
                      history.map((item) => (
                        <button
                          key={item.analysis_id}
                          role="menuitem"
                          className="history-item"
                          onClick={() => void openAnalysis(item)}
                          disabled={openingAnalysisId !== null}
                          aria-busy={openingAnalysisId === item.analysis_id}
                        >
                          <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <span className="min-w-0 truncate">
                            {openingAnalysisId === item.analysis_id
                              ? "Loading analysis…"
                              : `${item.role} · ${item.filename}`}
                          </span>
                        </button>
                      ))
                    ) : (
                      <p className="px-3 py-2 text-xs text-muted-foreground">Your saved analyses will appear here.</p>
                    )}
                    {historyOpenError && failedAnalysis && (
                      <div className="border-t border-border px-3 py-3" role="alert">
                        <p className="text-xs leading-5 text-destructive">
                          {historyOpenError}
                        </p>
                        <button
                          type="button"
                          className="mt-2 text-xs font-semibold text-accent underline underline-offset-4 disabled:opacity-60"
                          onClick={() => void openAnalysis(failedAnalysis)}
                          disabled={openingAnalysisId !== null}
                        >
                          {openingAnalysisId ? "Retrying…" : "Retry opening analysis"}
                        </button>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <button
              className="button button-secondary h-9 px-3"
              onClick={() => navigate("/upload")}
            >
              <Plus className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">New analysis</span>
            </button>
            <Link
              to="/account"
              className="user-avatar"
              title={`Account settings for ${user.name}`}
              aria-label={`Open account settings for ${user.name}`}
            >
              {user.name.slice(0, 1).toUpperCase()}
            </Link>
            <button
              className="button button-quiet size-9 p-0 lg:hidden"
              onClick={onSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="size-4" />
            </button>
            <button
              className="button button-quiet hidden size-9 p-0 lg:inline-flex"
              onClick={onSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </header>
      <div className="site-container flex min-h-14 items-center gap-1 overflow-x-auto border-b border-border/70">
        {nav.map((item) => {
          const active = location.pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "workspace-nav-item",
                active && "workspace-nav-item-active",
              )}
              aria-current={active ? "page" : undefined}
            >
              <item.icon className="size-4" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </div>
      <main id="main-content" className="site-container py-7 sm:py-10">
        {children}
      </main>
    </div>
  );
}
