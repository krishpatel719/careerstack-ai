import type { ReactNode } from "react";
import {
  ArrowRight,
  Check,
  FileSearch,
  LockKeyhole,
  ScanLine,
  Target,
  Upload,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Brand, SiteHeader } from "@/components/SiteChrome";
import { componentMeta } from "@/lib/score";
import type { User } from "@/lib/api";

export function LandingPage({
  user,
  onSignOut,
}: {
  user?: User | null;
  onSignOut?: () => void;
}) {
  const navigate = useNavigate();
  const start = () => navigate(user ? "/upload" : "/auth");

  return (
    <div className="min-h-screen overflow-hidden">
      <SiteHeader user={user} onSignOut={onSignOut} />
      <main id="main-content">
        <section className="hero-section hero-editorial">
          <div className="hero-grid site-container">
            <div className="hero-copy-block">
              <h1 className="hero-title">
                Make the evidence impossible to miss.
              </h1>
              <p className="hero-copy">
                CareerStack reads your resume against the role you are targeting,
                then gives you the few changes worth making.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <button className="button button-primary h-12 px-6" onClick={start}>
                  Analyse your resume
                  <ArrowRight className="size-4" aria-hidden="true" />
                </button>
                <button
                  className="button button-secondary h-12 px-5"
                  onClick={() =>
                    document
                      .getElementById("method")
                      ?.scrollIntoView({ behavior: "smooth" })
                  }
                >
                  See how it works
                </button>
              </div>
            </div>
            <HeroDocument />
          </div>
        </section>

        <section className="problem-section">
          <div className="site-container problem-layout">
            <div>
              <p className="section-kicker">The problem</p>
              <h2 className="section-title mt-5 max-w-xl">
                Most resume advice is written for the average candidate.
              </h2>
              <p className="section-copy mt-5 max-w-xl">
                It tells you to add more keywords, keep everything, and trust a
                number that never explains what changed. That is not useful
                when you are applying to a specific role in a specific market.
              </p>
            </div>
            <div className="problem-list">
              <PainPoint
                number="01"
                title="The score is disconnected"
                body="A number tells you what is wrong, not why it matters to this employer or this role."
              />
              <PainPoint
                number="02"
                title="The market keeps moving"
                body="A generic checklist cannot tell you what this job is asking for now."
              />
              <PainPoint
                number="03"
                title="The rewrite can become fiction"
                body="Adding words you have never used can make a resume cleaner and the story less true."
              />
            </div>
          </div>
        </section>

        <section className="story-section">
          <div className="site-container story-layout">
            <div className="story-copy">
              <p className="section-kicker">Why CareerStack</p>
              <h2 className="section-title mt-5 max-w-2xl">
                We built for the moment after the upload.
              </h2>
              <p className="story-lede mt-6">
                Most tools stop at a score. The hard part is deciding what to
                do next without pretending to be a recruiter, a parser, or a
                career coach.
              </p>
              <p className="story-body mt-5">
                CareerStack keeps the scoring deterministic and the
                recommendations grounded in your own experience. The goal is not
                to make you look like everyone else. It is to make the signal
                you already have easier to understand.
              </p>
              <div className="story-principles mt-9">
                <StoryPrinciple
                  title="Evidence before keywords"
                  body="We map gaps to the work you can actually defend."
                />
                <StoryPrinciple
                  title="One useful next move"
                  body="We rank the few changes most likely to improve the application."
                />
              </div>
            </div>
            <figure className="story-figure">
              <img
                src="/career-workspace.jpg"
                alt="A job seeker reviewing work on a laptop"
                width="1400"
                height="933"
                loading="eager"
              />
              <figcaption>
                <span>The principle we started with</span>
                <strong>A score without evidence is just a feeling with a number attached.</strong>
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="why-section">
          <div className="site-container">
            <div className="why-heading">
              <p className="section-kicker">The difference</p>
              <h2 className="section-title mt-5 max-w-2xl">
                Built to help you decide, not just score.
              </h2>
            </div>
            <div className="comparison-grid mt-12">
              <div className="comparison-column comparison-column-muted">
                <p className="comparison-label">Most resume tools</p>
                <ComparisonRow text="Give you a score" />
                <ComparisonRow text="Suggest more keywords" />
                <ComparisonRow text="Treat every role the same" />
                <ComparisonRow text="Hide uncertainty" />
              </div>
              <div className="comparison-column comparison-column-accent">
                <p className="comparison-label">CareerStack</p>
                <ComparisonRow text="Show the evidence behind the score" strong />
                <ComparisonRow text="Map gaps to real experience" strong />
                <ComparisonRow text="Use the live market as context" strong />
                <ComparisonRow text="Make limitations visible" strong />
              </div>
            </div>
          </div>
        </section>

        <section id="method" className="method-section">
          <div className="site-container">
            <div className="method-heading">
              <p className="section-kicker">Transparent by design</p>
              <h2 className="section-title mt-5 max-w-2xl">
                The score is useful because you can open it up.
              </h2>
              <p className="section-copy mt-5 max-w-2xl">
                Four measured signals shape the result. A language model only
                helps read your document and explain the evidence.
              </p>
            </div>
            <div className="method-layout mt-12">
              <div className="formula-panel">
                <p>Role fit formula</p>
                <div className="formula" aria-label="Role fit formula">
                  <span>0.40 language</span>
                  <span>0.25 evidence</span>
                  <span>0.20 format</span>
                  <span>0.15 experience</span>
                </div>
                <p className="formula-note">
                  Scores reflect our published model. They do not reproduce a
                  proprietary employer ATS.
                </p>
              </div>
              <div className="method-list">
                {componentMeta.map((item, index) => (
                  <MethodRow key={item.key} item={item} index={index} />
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="workflow-section">
          <div className="site-container">
            <h2 className="section-title max-w-2xl">
              One focused path from upload to application.
            </h2>
            <p className="section-copy mt-5 max-w-2xl">
              Choose a role, understand the evidence, and make the next useful
              edit without turning your search into a project management system.
            </p>
            <ol className="workflow-grid mt-12">
              <WorkflowStep
                number="01"
                icon={<Upload />}
                title="Add the document"
                body="Upload a PDF or DOCX. We check that the file is readable before scoring it."
              />
              <WorkflowStep
                number="02"
                icon={<Target />}
                title="Name the target"
                body="Choose the role and location. The market profile is built around that search."
              />
              <WorkflowStep
                number="03"
                icon={<ScanLine />}
                title="Read the evidence"
                body="See where your experience already matches and where the document stays unclear."
              />
              <WorkflowStep
                number="04"
                icon={<FileSearch />}
                title="Make the next edit"
                body="Work the ranked actions, then compare your resume with relevant live roles."
              />
            </ol>
          </div>
        </section>

        <section className="integrity-section">
          <div className="site-container integrity-layout">
            <div className="integrity-copy">
              <p className="section-kicker">A better kind of honest</p>
              <h2 className="section-title max-w-xl">
                Your resume stays your working document.
              </h2>
              <p className="section-copy mt-5 max-w-xl">
                We use the file to produce your analysis and matching role view.
                It is not used to train a model. The product also tells you when
                a market sample is sparse or a provider description is partial.
              </p>
              <ul className="trust-list mt-7">
                <li>
                  <Check className="size-4" />
                  Evidence recommendations stay grounded in your document
                </li>
                <li>
                  <Check className="size-4" />
                  Missing context is never treated as proof you did not provide
                </li>
                <li>
                  <Check className="size-4" />
                  Score limitations stay visible in the report
                </li>
              </ul>
            </div>
            <div className="integrity-note">
              <LockKeyhole className="size-5" />
              <p>Private by default</p>
              <span>Your document is used to help you make the next decision.</span>
            </div>
          </div>
        </section>

        <section className="final-cta">
          <div className="site-container final-cta-inner">
            <h2 className="max-w-3xl font-display text-4xl leading-[1] tracking-[-0.05em] sm:text-6xl">
              Know what the role needs. Prove what you have done.
            </h2>
            <button className="button button-accent h-12 px-6" onClick={start}>
              Analyse your resume
              <ArrowRight className="size-4" aria-hidden="true" />
            </button>
          </div>
        </section>
      </main>
      <footer className="site-footer">
        <div className="site-container flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
          <Brand />
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <Link to="/privacy" className="transition-colors hover:text-foreground">
              Privacy
            </Link>
            <Link to="/terms" className="transition-colors hover:text-foreground">
              Terms
            </Link>
            <span className="inline-flex items-center gap-1.5">
              <LockKeyhole className="size-3.5" />
              © 2026 CareerStack AI
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function HeroDocument() {
  return (
    <div className="hero-document-stage">
      <div className="hero-document-stamp">CareerStack / Field note 01</div>
      <figure className="hero-document-card">
        <div className="hero-document-image-wrap">
          <img
            src="/resume-review.jpg"
            alt="A printed resume beside a laptop"
            width="1400"
            height="933"
          />
          <div className="hero-document-overlay">
            <span>Read this first</span>
            <strong>What is already true?</strong>
            <small>Evidence, not keywords.</small>
          </div>
        </div>
        <figcaption>
          <span>One document. One target role.</span>
          <span>Private by default.</span>
        </figcaption>
      </figure>
      <div className="hero-document-note">Read the document.<br />Then read the market.</div>
    </div>
  );
}

function PainPoint({ number, title, body }: { number: string; title: string; body: string }) {
  return (
    <article className="pain-point">
      <span>{number}</span>
      <div>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
    </article>
  );
}

function StoryPrinciple({ title, body }: { title: string; body: string }) {
  return (
    <div className="story-principle">
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function ComparisonRow({ text, strong = false }: { text: string; strong?: boolean }) {
  return (
    <div className={strong ? "comparison-row comparison-row-strong" : "comparison-row"}>
      {strong ? <Check className="size-4" /> : <span className="comparison-dash">/</span>}
      <span>{text}</span>
    </div>
  );
}

function MethodRow({ item, index }: { item: (typeof componentMeta)[number]; index: number }) {
  return (
    <article className="method-row">
      <span className="method-index">0{index + 1}</span>
      <div className="method-row-main">
        <div className="flex items-baseline justify-between gap-4">
          <h3>{item.label}</h3>
          <span className="method-weight">{item.weight}%</span>
        </div>
        <p>{item.note}</p>
        <div className="method-bar" aria-hidden="true">
          <span style={{ width: `${item.weight * 2.1}%` }} />
        </div>
      </div>
    </article>
  );
}

function WorkflowStep({ number, icon, title, body }: { number: string; icon: ReactNode; title: string; body: string }) {
  return (
    <li className="workflow-step">
      <div className="flex items-center justify-between">
        <span className="workflow-icon">{icon}</span>
        <span className="workflow-number">{number}</span>
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
    </li>
  );
}
