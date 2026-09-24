import { Component, lazy, Suspense, useEffect, useState, type ErrorInfo, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { Toaster, toast } from "sonner";
import {
  AUTH_EXPIRED_EVENT,
  clearUserSession,
  getMe,
  getToken,
  type User,
} from "@/lib/api";
import { LandingPage } from "@/pages/LandingPage";

const AuthPage = lazy(() =>
  import("@/pages/AuthPage").then((module) => ({ default: module.AuthPage })),
);
const UploadPage = lazy(() =>
  import("@/pages/UploadPage").then((module) => ({
    default: module.UploadPage,
  })),
);
const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((module) => ({
    default: module.DashboardPage,
  })),
);
const JobsPage = lazy(() =>
  import("@/pages/JobsPage").then((module) => ({ default: module.JobsPage })),
);
const LegalPage = lazy(() =>
  import("@/pages/LegalPage").then((module) => ({ default: module.LegalPage })),
);
const AccountPage = lazy(() =>
  import("@/pages/AccountPage").then((module) => ({
    default: module.AccountPage,
  })),
);

class AppErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("CareerStack UI error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main
          id="main-content"
          className="site-container flex min-h-screen flex-col items-center justify-center text-center"
        >
          <p className="section-kicker">Something went wrong</p>
          <h1 className="page-title mt-4">This page needs a refresh.</h1>
          <p className="page-copy mt-4 max-w-md">
            Your saved work is still in this browser. Refresh the page to
            continue.
          </p>
          <button
            type="button"
            className="button button-primary mt-7"
            onClick={() => window.location.reload()}
          >
            Refresh page
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}

function App() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authError, setAuthError] = useState("");

  async function checkSession() {
    if (!getToken()) {
      setUser(null);
      setAuthChecked(true);
      return;
    }
    setAuthChecked(false);
    setAuthError("");
    try {
      setUser(await getMe());
    } catch (error) {
      if (error instanceof Error && "status" in error && error.status === 401) {
        clearUserSession();
        setUser(null);
      } else {
        setAuthError(
          "We couldn't verify your saved session. Your sign-in was not changed.",
        );
      }
    } finally {
      setAuthChecked(true);
    }
  }

  useEffect(() => {
    void checkSession();
  }, []);

  useEffect(() => {
    function handleExpiredSession() {
      setAuthError("");
      setUser(null);
      navigate("/auth", { replace: true });
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpiredSession);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpiredSession);
  }, [navigate]);

  function signOut() {
    clearUserSession();
    setUser(null);
    toast.success("Signed out");
  }

  if (!authChecked)
    return (
      <div
        className="app-loading"
        role="status"
        aria-label="Loading CareerStack"
      >
        <span />
        <span>Loading your workspace</span>
      </div>
    );

  if (authError)
    return (
      <main
        id="main-content"
        className="site-container flex min-h-screen flex-col items-center justify-center text-center"
      >
        <p className="section-kicker">Connection interrupted</p>
        <h1 className="page-title mt-4">Your saved session is still here.</h1>
        <p className="page-copy mt-4 max-w-md">{authError}</p>
        <button
          type="button"
          className="button button-primary mt-7"
          onClick={() => void checkSession()}
        >
          Retry connection
        </button>
      </main>
    );

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <AppErrorBoundary>
        <Suspense fallback={<PageLoader />}>
          <Routes>
          <Route
            path="/"
            element={<LandingPage user={user} onSignOut={signOut} />}
          />
          <Route
            path="/auth"
            element={
              <AuthPage
                onAuth={(nextUser) => {
                  setUser(nextUser);
                  toast.success("Your workspace is ready");
                }}
              />
            }
          />
          <Route
            path="/upload"
            element={
              user ? (
                <UploadPage user={user} onSignOut={signOut} />
              ) : (
                <Navigate to="/auth" replace />
              )
            }
          />
          <Route
            path="/app"
            element={
              user ? (
                <DashboardPage user={user} onSignOut={signOut} />
              ) : (
                <Navigate to="/auth" replace />
              )
            }
          />
          <Route
            path="/app/jobs"
            element={
              user ? (
                <JobsPage user={user} onSignOut={signOut} />
              ) : (
                <Navigate to="/auth" replace />
              )
            }
          />
          <Route
            path="/account"
            element={
              user ? (
                <AccountPage
                  user={user}
                  onSignOut={signOut}
                  onAccountDeleted={() => {
                    clearUserSession();
                    setUser(null);
                    toast.success("Account deleted");
                    navigate("/", { replace: true });
                  }}
                />
              ) : (
                <Navigate to="/auth" replace />
              )
            }
          />
          <Route path="/privacy" element={<LegalPage kind="privacy" />} />
          <Route path="/terms" element={<LegalPage kind="terms" />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        </Suspense>
      </AppErrorBoundary>
      <Toaster
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "!rounded-xl !border-border !bg-card !text-foreground !shadow-xl",
          },
        }}
      />
    </>
  );
}

function PageLoader() {
  return (
    <div className="app-loading" role="status" aria-label="Loading page">
      <span />
      <span>Loading page</span>
    </div>
  );
}

function NotFound() {
  return (
    <div className="min-h-screen">
      <main
        id="main-content"
        className="site-container flex min-h-screen flex-col justify-center"
      >
        <p className="section-kicker">404 · Wrong turn</p>
        <h1 className="page-title mt-4">This page is not in the stack.</h1>
        <p className="page-copy mt-4 max-w-md">
          The link may have moved, or it may have been a placeholder. Head back
          to the analysis workspace.
        </p>
        <a className="button button-primary mt-7 inline-flex w-fit" href="/">
          Back to home
        </a>
      </main>
    </div>
  );
}

export default function RootApp() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}
