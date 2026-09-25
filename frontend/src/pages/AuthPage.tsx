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
      const user = mode === "login" ? await login(email, password) : await register(name, email, password);
      onAuth(user);
      navigate("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't complete that request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main-content" className="auth-page auth-reference-page">
      <div className="auth-reference-shell">
        <div className="auth-reference-topbar">
          <Brand />
          <Link to="/" className="nav-link inline-flex items-center gap-1.5"><ArrowLeft className="size-3.5" />Home</Link>
        </div>
        <section className="auth-reference-card">
          <div className="text-center">
            <p className="section-kicker">Your private workspace</p>
            <h1 className="mt-3 font-display text-4xl tracking-[-.05em]">{mode === "login" ? "Welcome back." : "Make your next move."}</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{mode === "login" ? "Sign in to return to your saved analyses." : "Create a private space for the work behind your next application."}</p>
          </div>
          <Tabs value={mode} onValueChange={(value) => { setMode(value as "login" | "register"); setError(""); }} className="mt-7">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Sign in</TabsTrigger>
              <TabsTrigger value="register">Create account</TabsTrigger>
            </TabsList>
            <TabsContent value="login">
              <form onSubmit={submit} className="grid gap-5" aria-busy={busy}>
                <AuthField id="login-email" label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} placeholder="you@company.com" required />
                <AuthField id="login-password" label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} placeholder="Your password" required />
                {error && <p role="alert" className="form-error">{error}</p>}
                <Button size="lg" type="submit" disabled={busy}>{busy ? "Signing you in…" : "Sign in"}<ArrowRight data-icon="inline-end" /></Button>
              </form>
            </TabsContent>
            <TabsContent value="register">
              <form onSubmit={submit} className="grid gap-5" aria-busy={busy}>
                <AuthField id="register-name" label="Full name" autoComplete="name" value={name} onChange={setName} placeholder="Your name" required />
                <AuthField id="register-email" label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} placeholder="you@company.com" required />
                <AuthField id="register-password" label="Password" type="password" autoComplete="new-password" value={password} onChange={setPassword} placeholder="8 characters minimum" required minLength={8} />
                {error && <p role="alert" className="form-error">{error}</p>}
                <Button size="lg" type="submit" disabled={busy}>{busy ? "Creating your space…" : "Create account"}<ArrowRight data-icon="inline-end" /></Button>
              </form>
            </TabsContent>
          </Tabs>
          <div className="auth-reference-divider"><span>Private by design</span></div>
          <div className="auth-reference-note"><LockKeyhole className="size-4" /><span>Your file is used only to produce your analysis. It is not used to train a model.</span></div>
          <p className="mt-6 flex items-start gap-2 text-xs leading-5 text-muted-foreground"><Check className="mt-0.5 size-3.5 shrink-0 text-accent" />By continuing, you agree to our <Link to="/terms" className="underline underline-offset-4">terms</Link> and <Link to="/privacy" className="underline underline-offset-4">privacy policy</Link>.</p>
        </section>
      </div>
    </main>
  );
}

function AuthField({ id, label, type = "text", autoComplete, value, onChange, placeholder, required, minLength }: { id: string; label: string; type?: string; autoComplete?: string; value: string; onChange: (value: string) => void; placeholder: string; required?: boolean; minLength?: number }) {
  return <div className="grid gap-2"><Label htmlFor={id}>{label}</Label><Input id={id} type={type} required={required} minLength={minLength} autoComplete={autoComplete} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></div>;
}
