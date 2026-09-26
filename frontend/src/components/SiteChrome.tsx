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
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { cn } from "@/lib/utils";

export function Brand({ compact = false }: { compact?: boolean }) {
  // Plain wordmark, matching the original UI: "CareerStack" in ink with
  // "AI" in indigo, and no logo tile. `compact` is kept for callers that
  // pass it, but the mark is already a single line of text.
  void compact;
  return (
    <Link to="/" className="cs-wordmark" aria-label="CareerStack home">
      CareerStack<span className="cs-wordmark-accent">AI</span>
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
  const navigate = useNavigate();

  // The original nav: wordmark on the left, and on the right just the
  // signed-in name + Sign out, then one indigo pill CTA. No section
  // links and no hamburger -- the CTA is the only navigation, which is
  // what kept it readable on a phone without a menu.
  return (
    <header className={cn("cs-nav", theme === "dark" && "site-header-dark")}>
      <Brand />
      <div className="cs-nav-right">
        {user && (
          <div className="cs-nav-user">
            <span className="cs-nav-user-name">{user.name}</span>
            <button type="button" className="cs-btn cs-btn-ghost cs-btn-pill" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        )}
        <button
          type="button"
          className="cs-btn cs-btn-indigo cs-btn-pill"
          onClick={() => navigate(user ? "/upload" : "/auth")}
        >
          Analyse my resume
        </button>
      </div>
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

  // Same left rail as the dashboard, so every signed-in page shares one
  // navigation instead of the workspace pages carrying a second sidebar
  // and top bar of their own. showSections is off because the Analysis
  // links scroll-spy headings that only the dashboard has, and
  // DashboardSidebar owns its own history loading -- which is why none of
  // that state lives here any more.
  return (
    <div className="cs-dash">
      <DashboardSidebar
        showSections={false}
        onSelectAnalysis={() => navigate("/app")}
      />
      <main className="cs-dash-main">
        <div className="cs-dash-inner">{children}</div>
      </main>
      <button type="button" className="cs-dash-signout" onClick={onSignOut}>
        Sign out
      </button>
    </div>
  );
}
