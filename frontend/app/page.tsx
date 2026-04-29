import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container hero">
      <div className="card" style={{ padding: 30 }}>
        <h1>Ship Better Pull Requests With Multi-Agent AI Reviews</h1>
        <p>
          DevPilot AI combines evidence-based code review agents and automated documentation generation
          to accelerate onboarding, keep docs fresh, and improve engineering quality.
        </p>
        <div style={{ display: "flex", gap: 12, marginTop: 18, flexWrap: "wrap" }}>
          <Link href="/dashboard" className="btn btn-primary">
            Open Dashboard
          </Link>
          <a href="#features" className="btn btn-secondary">
            Explore Features
          </a>
        </div>
      </div>

      <section id="features" className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", marginTop: 20 }}>
        <article className="card">
          <h3>Code Reviewer</h3>
          <p>Six specialized agents inspect PR-ready code for bugs, security, performance, readability, architecture, and accessibility.</p>
        </article>
        <article className="card">
          <h3>Documentation Generator</h3>
          <p>Generate README files, docstrings, modular docs, onboarding guides, and graph visuals from repository source.</p>
        </article>
        <article className="card">
          <h3>Persona-Aware Output</h3>
          <p>Adapt review tone and explanation depth for interns, students, frontend engineers, and backend engineers.</p>
        </article>
      </section>
    </main>
  );
}
