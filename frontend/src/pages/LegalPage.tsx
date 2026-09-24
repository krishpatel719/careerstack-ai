import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "@/components/SiteChrome";

export function LegalPage({ kind }: { kind: "privacy" | "terms" }) {
  const privacy = kind === "privacy";
  return (
    <div className="min-h-screen">
      <header className="site-header">
        <div className="site-container flex h-18 items-center justify-between">
          <Brand />
          <Link to="/" className="nav-link inline-flex items-center gap-1.5">
            <ArrowLeft className="size-3.5" />
            Back home
          </Link>
        </div>
      </header>
      <main className="site-container legal-page">
        <p className="section-kicker">CareerStack AI</p>
        <h1 className="page-title mt-4">
          {privacy ? "Privacy, in plain language." : "Terms of use."}
        </h1>
        <p className="page-copy mt-5 max-w-2xl">
          This page is a concise product-level summary. It is not legal advice.
        </p>
        <div className="legal-copy mt-12">
          {privacy ? (
            <>
              <h2>What we handle</h2>
              <p>
                When you analyse a resume, CareerStack processes the file, the
                target role, and the location you provide to produce the
                analysis and matching-role view. When you create an account, we
                store the account details needed to keep your saved analyses
                available.
              </p>
              <h2>What we do not do</h2>
              <p>
                We do not use your resume to train a model. We do not sell
                personal information. We keep the interface explicit about when
                a score is based on sparse market data or a shortened provider
                description.
              </p>
              <h2>Your choices</h2>
              <p>
                You can sign out at any time. For access, correction, or
                deletion of account data, contact the project owner through the
                channel where you received this application.
              </p>
            </>
          ) : (
            <>
              <h2>Using the service</h2>
              <p>
                CareerStack provides resume analysis and job-search signals for
                informational purposes. Submit only a document you have
                permission to use, and do not use the service to make decisions
                about another person without their consent.
              </p>
              <h2>Scores and job results</h2>
              <p>
                Scores are deterministic estimates produced by the published
                model. They are not a guarantee of hiring, an ATS outcome, or
                the quality of a particular application. Job results depend on
                the providers and public sources available at the time of the
                search.
              </p>
              <h2>Availability</h2>
              <p>
                The service is provided as-is for an academic project. We may
                change or stop features as the project evolves. Please keep an
                independent copy of important documents.
              </p>
            </>
          )}
        </div>
        <Link to="/" className="button button-secondary mt-12 inline-flex">
          Back to CareerStack
        </Link>
      </main>
    </div>
  );
}
