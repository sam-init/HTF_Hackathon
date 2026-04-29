"use client";

import { useState } from "react";

import { DocsResults } from "@/components/DocsResults";
import { ReviewResults } from "@/components/ReviewResults";
import { docsFromRepo, docsFromZip, reviewFromRepo, reviewFromZip } from "@/lib/api";
import { DocsResponse, Persona, ReviewResponse } from "@/lib/types";

const personas: Persona[] = ["Intern", "Student", "Frontend Developer", "Backend Developer"];

type Tab = "review" | "docs";

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("review");
  const [persona, setPersona] = useState<Persona>("Student");
  const [repoUrl, setRepoUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [reviewData, setReviewData] = useState<ReviewResponse | null>(null);
  const [docsData, setDocsData] = useState<DocsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runWithRepo() {
    if (!repoUrl) {
      setError("Please enter a repository URL.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (tab === "review") {
        setReviewData(await reviewFromRepo(repoUrl, persona));
      } else {
        setDocsData(await docsFromRepo(repoUrl, persona));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runWithZip() {
    if (!file) {
      setError("Please select a ZIP file.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (tab === "review") {
        setReviewData(await reviewFromZip(file, persona));
      } else {
        setDocsData(await docsFromZip(file, persona));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <header className="card" style={{ marginBottom: 14 }}>
        <h1 style={{ marginTop: 0, marginBottom: 10 }}>DevPilot AI Dashboard</h1>
        <p style={{ margin: 0, color: "var(--muted)" }}>
          Production-style AI tooling for repository review and documentation workflows.
        </p>
      </header>

      <section className="dashboard-grid">
        <aside className="card">
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button className={`btn ${tab === "review" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("review")}>
              Code Reviewer
            </button>
            <button className={`btn ${tab === "docs" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("docs")}>
              Docs Generator
            </button>
          </div>

          <label>
            Persona
            <select className="select" value={persona} onChange={(e) => setPersona(e.target.value as Persona)}>
              {personas.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>

          <label style={{ display: "block", marginTop: 10 }}>
            GitHub Repo URL
            <input
              className="input"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
            />
          </label>

          <button className="btn btn-primary" onClick={runWithRepo} disabled={loading} style={{ marginTop: 10, width: "100%" }}>
            {loading ? "Processing..." : "Run With Repo URL"}
          </button>

          <hr style={{ margin: "14px 0", borderColor: "var(--border)" }} />

          <label>
            ZIP Upload
            <input
              className="input"
              type="file"
              accept=".zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <button className="btn btn-secondary" onClick={runWithZip} disabled={loading} style={{ marginTop: 10, width: "100%" }}>
            {loading ? "Processing..." : "Run With ZIP"}
          </button>

          {error && <p style={{ color: "var(--danger)", marginTop: 10 }}>{error}</p>}
        </aside>

        <section>
          {tab === "review" && reviewData && <ReviewResults data={reviewData} />}
          {tab === "docs" && docsData && <DocsResults data={docsData} />}
          {!reviewData && tab === "review" && (
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Code Reviewer Ready</h3>
              <p style={{ marginBottom: 0 }}>
                Connect a repository or upload ZIP to generate evidence-based inline findings and chat-style summary.
              </p>
            </div>
          )}
          {!docsData && tab === "docs" && (
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Documentation Generator Ready</h3>
              <p style={{ marginBottom: 0 }}>
                Generate README, docstrings, modular docs, onboarding guide, and repository graphs.
              </p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
