import {
  ArrowRight,
  Check,
  ChevronRight,
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
  const scrollTo = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="reference-landing">
      <SiteHeader user={user} onSignOut={onSignOut} />
      <main id="main-content">
        <section className="reference-hero">
          <div className="reference-container reference-hero-grid">
            <div className="reference-hero-copy">
              <span className="reference-badge">Scored against live postings</span>
              <h1 className="reference-display">
                Know your resume's score <span>before you apply</span>
              </h1>
              <p className="reference-hero-subhead">
                We mine live job postings for your target role and score your
                resume across four measured components, not a guess. You get a
                calculation you can inspect.
              </p>
              <div className="reference-feature-list">
                <span><Check />40 live postings sampled</span>
                <span><Check />Four weighted components</span>
                <span><Check />Results in seconds</span>
              </div>
              <div className="reference-hero-actions">
                <button className="reference-button reference-button-primary" onClick={start}>
                  Analyse my resume <span className="reference-button-icon"><ArrowRight /></span>
                </button>
                <button className="reference-button reference-button-ghost" onClick={() => scrollTo("methodologySection")}>
                  How scoring works
                </button>
              </div>
              <p className="reference-fineprint">PDF or DOCX · up to 5MB</p>
            </div>
            <PreviewPanel />
          </div>
        </section>

        <section className="reference-section" id="methodologySection">
          <div className="reference-container">
            <header className="reference-section-heading">
              <p className="reference-kicker">The method</p>
              <h2 className="reference-display reference-section-title">How the score is calculated</h2>
              <p>Four components, each measured independently and combined by a fixed formula, never a model guessing a number.</p>
            </header>
            <div className="reference-method-intro">
              <p><strong>Two different questions.</strong> The ATS Parse Score asks whether a parser can read your document at all. The Role Fit Score asks how well your experience matches a specific role in today's market. Parse score is one input to fit score, 20% of its weight, not a separate total added on top.</p>
              <p>Real applicant tracking systems are proprietary and vary by vendor and by how each employer configures them. We don't claim to reproduce any specific one. These checks reflect common, well-documented parsing behaviour.</p>
            </div>
            <div className="reference-method-grid">
              {componentMeta.map((item) => <MethodCard key={item.key} item={item} />)}
            </div>
            <div className="reference-formula-wrap">
              <div className="reference-formula">
                <span>score</span> = {componentMeta.map((item, index) => (
                  <span key={item.key}>{(item.weight / 100).toFixed(2)} · {item.label.toLowerCase()}{index < componentMeta.length - 1 ? " + " : ""}</span>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="reference-section reference-section-wash" id="workflow">
          <div className="reference-container">
            <header className="reference-section-heading">
              <p className="reference-kicker">The inputs</p>
              <h2 className="reference-display reference-section-title">Where the requirements come from</h2>
              <p>Every score is built on postings sampled at the moment you ask for it.</p>
            </header>
            <div className="reference-data-steps">
              <DataStep number="1" text="Search live postings for your role" />
              <ChevronRight className="reference-data-arrow" aria-hidden="true" />
              <DataStep number="2" text="Extract skills from each" />
              <ChevronRight className="reference-data-arrow" aria-hidden="true" />
              <DataStep number="3" text="Weight by frequency" />
            </div>
            <p className="reference-data-closing">Every requirement is measured from real postings, not a fixed rubric.</p>
          </div>
        </section>
      </main>
      <footer className="reference-footer">
        <div className="reference-container reference-footer-inner">
          <Brand />
          <div><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link><span>© 2026 CareerStack AI</span></div>
        </div>
      </footer>
    </div>
  );
}

function PreviewPanel() {
  return (
    <div className="reference-preview-wrap">
      <div className="reference-browser-frame">
        <div className="reference-browser-titlebar">
          <div className="reference-browser-dots"><i /><i /><i /></div>
          <div className="reference-browser-url">careerstack.ai/dashboard</div>
        </div>
        <div className="reference-browser-body">
          <aside className="reference-preview-sidebar"><b /><b /><b /><b /></aside>
          <div className="reference-preview-main">
            <div className="reference-ring">
              <svg viewBox="0 0 96 96" aria-hidden="true"><circle className="reference-ring-track" cx="48" cy="48" r="41" /><circle className="reference-ring-fill" cx="48" cy="48" r="41" /></svg>
              <strong>72</strong>
            </div>
            <span className="reference-band">Competitive</span>
            <div className="reference-mini-bars"><i /><i /><i /></div>
            <div className="reference-mini-labels"><span>Role fit</span><span>Market language</span><span>Evidence quality</span></div>
          </div>
        </div>
      </div>
      <span className="reference-preview-caption">A useful score comes with the evidence behind it.</span>
    </div>
  );
}

function MethodCard({ item }: { item: (typeof componentMeta)[number] }) {
  return (
    <article className="reference-method-card">
      <strong>{Math.round(item.weight)}%</strong>
      <h3>{item.label}</h3>
      <p>{item.note}</p>
      <p>{item.key === "format" ? "Nine deterministic checks for tables, columns, contact details, dates, bullets, and more." : item.key === "keyword" ? "How often the skills asked for across sampled postings actually appear in your resume." : item.key === "semantic" ? "Whether your wording supports the requirements in the role, sentence by sentence." : "How your experience and seniority compare with the market sample for this role."}</p>
    </article>
  );
}

function DataStep({ number, text }: { number: string; text: string }) {
  return <div className="reference-data-step"><span>{number}</span><strong>{text}</strong></div>;
}
