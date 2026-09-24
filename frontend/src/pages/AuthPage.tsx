import { useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Check, LockKeyhole } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Brand } from "@/components/SiteChrome";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { login, register, type User } from "@/lib/api";

export function AuthPage({ onAuth }: { onAuth: (user: User) => void }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user =
        mode === "login"
          ? await login(email, password)
          : await register(name, email, password);
      onAuth(user);
      navigate("/upload");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We couldn't complete that request.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main-content" className="auth-page">
      <div className="auth-story">
        <div className="relative z-10">
          <Brand />
          <div className="mt-auto max-w-lg">
            <p className="section-kicker text-accent-soft">
              <span className="kicker-line bg-accent" />
              Your private workspace
            </p>
            <h1 className="mt-5 font-display text-6xl leading-[.92] tracking-[-.06em] text-white sm:text-7xl">
              Make the signal easier to see.
            </h1>
            <p className="mt-7 max-w-md text-base leading-7 text-white/60">
              Save each analysis, compare the evidence, and come back to the
              next edit when you are ready.
            </p>
          </div>
          <p className="flex items-center gap-2 text-xs text-white/45">
            <LockKeyhole className="size-3.5 text-accent" />
            Your file is used only for this analysis.
          </p>
        </div>
        <img
          className="auth-story-photo"
          src="/career-workspace.jpg"
          alt=""
          aria-hidden="true"
        />
      </div>
      <div className="auth-form-side">
        <div className="w-full max-w-[420px]">
          <div className="mb-12 flex items-center justify-between lg:hidden">
            <Brand />
            <Link to="/" className="nav-link inline-flex items-center gap-1.5">
              <ArrowLeft className="size-3.5" />
              Home
            </Link>
          </div>
          <p className="section-kicker">CareerStack account</p>
          <h2 className="mt-4 font-display text-4xl tracking-[-.05em]">
            {mode === "login" ? "Welcome back." : "Make your next move."}
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {mode === "login"
              ? "Sign in to return to your saved analyses."
              : "Create a private space for the work behind your next application."}
          </p>
          <Tabs
            value={mode}
            onValueChange={(value) => {
              setMode(value as "login" | "register");
              setError("");
            }}
            className="mt-8"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Sign in</TabsTrigger>
              <TabsTrigger value="register">Create account</TabsTrigger>
            </TabsList>
            <TabsContent value="login">
              <form onSubmit={submit} className="grid gap-5" aria-busy={busy}>
                <AuthField
                  id="login-email"
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={setEmail}
                  placeholder="you@company.com"
                  required
                />
                <AuthField
                  id="login-password"
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={setPassword}
                  placeholder="Your password"
                  required
                />
                {error && (
                  <p role="alert" className="form-error">
                    {error}
                  </p>
                )}
                <Button size="lg" type="submit" disabled={busy}>
                  {busy ? "Signing you in…" : "Sign in"}
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </form>
            </TabsContent>
            <TabsContent value="register">
              <form onSubmit={submit} className="grid gap-5" aria-busy={busy}>
                <AuthField
                  id="register-name"
                  label="Full name"
                  autoComplete="name"
                  value={name}
                  onChange={setName}
                  placeholder="Your name"
                  required
                />
                <AuthField
                  id="register-email"
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={setEmail}
                  placeholder="you@company.com"
                  required
                />
                <AuthField
                  id="register-password"
                  label="Password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={setPassword}
                  placeholder="8 characters minimum"
                  required
                  minLength={8}
                />
                {error && (
                  <p role="alert" className="form-error">
                    {error}
                  </p>
                )}
                <Button size="lg" type="submit" disabled={busy}>
                  {busy ? "Creating your space…" : "Create account"}
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </form>
            </TabsContent>
          </Tabs>
          <p className="mt-8 flex items-start gap-2 text-xs leading-5 text-muted-foreground">
            <Check className="mt-0.5 size-3.5 shrink-0 text-accent" />
            By continuing, you agree to our{" "}
            <Link to="/terms" className="underline underline-offset-4">
              terms
            </Link>{" "}
            and{" "}
            <Link to="/privacy" className="underline underline-offset-4">
              privacy policy
            </Link>
            .
          </p>
        </div>
      </div>
    </main>
  );
}

function AuthField({
  id,
  label,
  type = "text",
  autoComplete,
  value,
  onChange,
  placeholder,
  required,
  minLength,
}: {
  id: string;
  label: string;
  type?: string;
  autoComplete?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  required?: boolean;
  minLength?: number;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
