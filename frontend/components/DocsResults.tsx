import { DocsResponse } from "@/lib/types";
import { GraphPanel } from "./GraphPanel";

export function DocsResults({ data }: { data: DocsResponse }) {
  return (
    <section className="grid" style={{ gap: 12 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>What Happened</h3>
        <p style={{ margin: "6px 0" }}>
          We analyzed your repository structure, generated module-specific documentation, and created graph views.
          Temporary workspace snapshots are internal processing artifacts and are not required for users to inspect.
        </p>
        <p style={{ margin: "6px 0", color: "var(--muted)" }}>
          Doc rot detected: <strong>{data.doc_rot_detected ? "Yes (README regenerated)" : "No"}</strong>
        </p>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>README Output</h3>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{data.readme}</pre>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Module-by-Module Documentation</h3>
        <div style={{ display: "grid", gap: 8 }}>
          {Object.entries(data.modular_docs).map(([path, content]) => (
            <details key={path}>
              <summary><strong>{path}</strong></summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>{content}</pre>
            </details>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Generated Docstrings</h3>
        <div style={{ display: "grid", gap: 8 }}>
          {Object.entries(data.docstrings).map(([path, content]) => (
            <details key={path}>
              <summary><strong>{path}</strong></summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>{content}</pre>
            </details>
          ))}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Onboarding Guide</h3>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{data.onboarding_guide}</pre>
      </div>

      <GraphPanel title="Dependency Graph" graph={data.dependency_graph} />
      <GraphPanel title="Execution Flowchart" graph={data.execution_flowchart} />
      <GraphPanel title="Knowledge Graph" graph={data.knowledge_graph} />
    </section>
  );
}
