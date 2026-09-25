import {
  ArrowRight,
  Check,
  ChevronRight,
  ShieldCheck,
  Sparkles,
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
                We compare your document with current postings for one role.
                Four measured signals show what is already there and what is
                worth changing before you apply.
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
              <h2 className="reference-display reference-section-title">Four checks. One readable report.</h2>
              <p>Each signal is measured separately, then combined with a fixed formula. The model helps read your document. It does not invent the score.</p>
            </header>
            <div className="reference-method-intro">
              <p><strong>Two different questions.</strong> The ATS Parse Score asks whether a parser can read your document at all. The Role Fit Score asks how well your experience matches this role in today's market. Parse score is one input to fit score, not a second total added on top.</p>
              <p>Real applicant tracking systems are proprietary and configured differently by each employer. We do not claim to reproduce one. These checks reflect the parsing behaviour employers document most often.</p>
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

        <section className="reference-story">
          <div className="reference-container reference-story-grid">
            <div className="reference-story-copy">
              <p className="reference-kicker">Why it exists</p>
              <h2 className="reference-display reference-section-title">A polished resume can still miss the role.</h2>
              <p>Most advice adds more words. It does not help you decide which experience belongs in the first three lines, which skill needs proof, or which gap is worth closing before you apply.</p>
              <p>CareerStack starts with the document and the market, then shows the difference in plain language. No invented experience. No black box. Just a better next edit.</p>
              <div className="reference-story-notes">
                <div><span>01</span><strong>Evidence before keywords</strong><p>Recommendations have to point back to something you can defend.</p></div>
                <div><span>02</span><strong>One useful next move</strong><p>The report ranks changes instead of handing you a wall of advice.</p></div>
              </div>
            </div>
            <aside className="reference-story-card">
              <span className="reference-story-card-label">The question behind the score</span>
              <strong>What should I change before this application goes out?</strong>
              <div className="reference-story-card-footer"><span>CareerStack / 2026</span><span>Read the document. Then read the market.</span></div>
            </aside>
          </div>
        </section>

        <section className="reference-section reference-section-wash" id="workflow">
          <div className="reference-container">
            <header className="reference-section-heading">
              <p className="reference-kicker">The inputs</p>
              <h2 className="reference-display reference-section-title">The score follows the market.</h2>
              <p>Postings are sampled at the moment you ask, so the comparison reflects the role as it is being advertised now.</p>
            </header>
            <div className="reference-data-steps">
              <DataStep number="1" text="Search live postings for your role" />
              <ChevronRight className="reference-data-arrow" aria-hidden="true" />
              <DataStep number="2" text="Extract skills from each" />
              <ChevronRight className="reference-data-arrow" aria-hidden="true" />
              <DataStep number="3" text="Weight by frequency" />
            </div>
            <p className="reference-data-closing">Every requirement comes from a sampled posting. Nothing is pulled from a generic checklist.</p>
          </div>
        </section>

        <section className="reference-trust-strip">
          <div className="reference-container reference-trust-grid">
            <div><ShieldCheck /><strong>Evidence first</strong><span>Recommendations stay grounded in your document.</span></div>
            <div><Sparkles /><strong>Clear next move</strong><span>See what to change before you send the application.</span></div>
            <div><Check /><strong>Private by default</strong><span>Your file is not used to train a model.</span></div>
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
      <figure className="reference-document-card">
        <div className="reference-document-media">
          <img src="/resume-review.jpg" alt="A printed resume beside a laptop" width="1400" height="933" />
          <div className="reference-document-overlay">
            <span>Read this first</span>
            <strong>What is already true?</strong>
            <small>Evidence, not keywords.</small>
          </div>
        </div>
        <figcaption><span>One document. One target role.</span><span>Private by default.</span></figcaption>
      </figure>
      <div className="reference-report-card">
        <div className="reference-report-top"><span>Role fit</span><strong>72</strong><em>Competitive</em></div>
        <div className="reference-report-bars"><i /><i /><i /></div>
        <p>One clear edit stands out. Start there.</p>
      </div>
      <span className="reference-preview-caption">A score is only useful when you can see the evidence behind it.</span>
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
