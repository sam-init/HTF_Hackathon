import { Finding, ReviewResponse } from "@/lib/types";

function severityClass(severity: Finding["severity"]) {
  return `badge badge-${severity}`;
}

export function ReviewResults({ data }: { data: ReviewResponse }) {
  return (
    <section className="grid" style={{ gap: 12 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Chat-Style Review Summary</h3>
        <p style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{data.summary}</p>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Inline Feedback ({data.findings.length})</h3>
        <div style={{ display: "grid", gap: 10 }}>
          {data.findings.map((finding, idx) => (
            <article key={`${finding.file}-${finding.line}-${idx}`} className="card" style={{ boxShadow: "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <strong>{finding.issue_title}</strong>
                <span className={severityClass(finding.severity)}>{finding.severity.toUpperCase()}</span>
              </div>
              <p style={{ marginBottom: 8 }}>
                <code>{finding.file}:{finding.line}</code> • {finding.agent} • confidence {(finding.confidence * 100).toFixed(0)}%
              </p>
              <p style={{ margin: "6px 0" }}>{finding.explanation}</p>
              <p style={{ margin: "6px 0", color: "var(--muted)" }}>
                <strong>Suggested fix:</strong> {finding.fix_suggestion}
              </p>
            </article>
          ))}
          {data.findings.length === 0 && <p>No high-confidence findings were produced.</p>}
        </div>
      </div>
    </section>
  );
}
