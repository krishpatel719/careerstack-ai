import {
  lazy,
  Suspense,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { ArrowRight, Check, LockKeyhole, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SiteHeader } from "@/components/SiteChrome";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { analyzeResume, type User } from "@/lib/api";
import { cn } from "@/lib/utils";

const PdfPreview = lazy(() =>
  import("@/components/PdfPreview").then((module) => ({
    default: module.PdfPreview,
  })),
);

export function UploadPage({
  user,
  onSignOut,
}: {
  user: User;
  onSignOut: () => void;
}) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState(
    () => localStorage.getItem("careerstack_last_role") || "",
  );
  const [location, setLocation] = useState(
    () => localStorage.getItem("careerstack_last_location") || "",
  );
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const valid = Boolean(file && role.trim() && location.trim());

  function chooseFile(candidate?: File) {
    if (!candidate) return;
    if (!/\.(pdf|docx)$/i.test(candidate.name)) {
      setError("Choose a PDF or DOCX file.");
      return;
    }
    if (candidate.size > 5 * 1024 * 1024) {
      setError("That file is over 5 MB. Please upload a smaller file.");
      return;
    }
    setError("");
    setFile(candidate);
  }

  function drop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const nextRole = role.trim();
      const nextLocation = location.trim();
      localStorage.setItem("careerstack_last_role", nextRole);
      localStorage.setItem("careerstack_last_location", nextLocation);
      const analysis = await analyzeResume(file, nextRole, nextLocation);
      sessionStorage.setItem("careerstack_analysis", JSON.stringify(analysis));
      navigate("/app");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "We couldn't analyse that file.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <SiteHeader user={user} onSignOut={onSignOut} />
      <main id="main-content" className="site-container upload-page">
        <div className="upload-intro">
          <p className="section-kicker">
            <span className="kicker-line" />
            New analysis
          </p>
          <h1 className="page-title mt-4">Give your resume a fair read.</h1>
          <p className="page-copy mt-5">
            Upload once. We will compare the document against the language of
            live postings for the role you have in mind.
          </p>
        </div>
        <div className="upload-layout mt-12">
          <section
            className="upload-form-panel"
            aria-labelledby="resume-details-title"
          >
            <div className="panel-heading">
              <span className="step-number">01</span>
              <div>
                <p className="section-kicker">Resume details</p>
                <h2
                  id="resume-details-title"
                  className="mt-2 font-display text-3xl tracking-[-.04em]"
                >
                  Start with the document.
                </h2>
              </div>
            </div>
            <form
              onSubmit={submit}
              className="grid gap-6 p-6 sm:p-8"
              aria-busy={busy}
            >
              <label
                htmlFor="resume-file"
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setDragging(false)}
                onDrop={drop}
                className={cn(
                  "drop-zone",
                  dragging && "drop-zone-active",
                  error && !file && "drop-zone-error",
                )}
              >
                <input
                  id="resume-file"
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="sr-only"
                  onChange={(event) => chooseFile(event.target.files?.[0])}
                />
                <span className="drop-icon">
                  <UploadCloud className="size-5" />
                </span>
                <span className="mt-4 text-sm font-semibold">
                  Drop your resume here
                </span>
                <span className="mt-1 text-xs text-muted-foreground">
                  or click to browse · PDF or DOCX · 5 MB max
                </span>
              </label>
              {file && (
                <Suspense
                  fallback={
                    <div className="h-16 animate-pulse rounded-xl bg-muted" />
                  }
                >
                  <PdfPreview file={file} />
                </Suspense>
              )}
              {error && (
                <p role="alert" className="form-error">
                  {error}
                </p>
              )}
              <div className="grid gap-5 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="role">Target role</Label>
                  <Input
                    id="role"
                    required
                    placeholder="e.g. Backend Developer"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    required
                    placeholder="e.g. Bengaluru, India"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                  />
                </div>
              </div>
              <Button size="lg" type="submit" disabled={!valid || busy}>
                {busy ? "Analysing your resume…" : "Analyse my resume"}
                <ArrowRight data-icon="inline-end" />
              </Button>
            </form>
          </section>
          <aside className="upload-aside">
            <div className="process-panel">
              <p className="section-kicker text-accent-soft">
                <span className="kicker-line bg-accent" />
                What happens next
              </p>
              <h2 className="mt-4 font-display text-3xl tracking-[-.04em] text-white">
                A clear path from file to fit.
              </h2>
              <div className="mt-8 grid gap-6">
                {[
                  [
                    "01",
                    "Read",
                    "We inspect structure, sections, dates, and parser friction.",
                  ],
                  [
                    "02",
                    "Compare",
                    "Live postings shape the requirements used for your score.",
                  ],
                  [
                    "03",
                    "Act",
                    "A short list tells you where to focus before applying.",
                  ],
                ].map(([number, title, body]) => (
                  <div key={number} className="process-step">
                    <span>{number}</span>
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {title}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-white/55">
                        {body}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <p className="mt-4 flex items-center gap-2 px-1 text-xs text-muted-foreground">
              <LockKeyhole className="size-4 text-accent" />
              Your file is not used to train a model.
            </p>
            <div className="upload-checklist">
              <p className="text-sm font-semibold">Before you upload</p>
              <ul>
                <li>
                  <Check className="size-3.5" />
                  Use a recent version of your resume
                </li>
                <li>
                  <Check className="size-3.5" />
                  Name the role you are actually targeting
                </li>
                <li>
                  <Check className="size-3.5" />
                  Keep the original PDF if you have one
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
