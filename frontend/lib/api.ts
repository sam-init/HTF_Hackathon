import { DocsResponse, Persona, ReviewResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/* ─── Response handler ─────────────────────────────────── */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status})`;
    try {
      const ct = res.headers.get("content-type") ?? "";
      if (ct.includes("application/json")) {
        const json = await res.json();
        message = json?.detail ?? json?.message ?? JSON.stringify(json);
      } else {
        const text = await res.text();
        if (text) message = text;
      }
    } catch {
      /* ignore parse errors, keep status message */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

/* ─── Timeout wrapper ──────────────────────────────────── */
function withTimeout(promise: Promise<Response>, ms = 120_000): Promise<Response> {
  return Promise.race([
    promise,
    new Promise<Response>((_, reject) =>
      setTimeout(() => reject(new Error(`Request timed out after ${ms / 1000}s`)), ms)
    ),
  ]);
}

/* ─── Review endpoints ─────────────────────────────────── */
export async function reviewFromRepo(
  repoUrl: string,
  persona: Persona
): Promise<ReviewResponse> {
  const res = await withTimeout(
    fetch(`${API_BASE}/api/review/repo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, persona }),
    })
  );
  return handleResponse<ReviewResponse>(res);
}

export async function reviewFromZip(
  file: File,
  persona: Persona
): Promise<ReviewResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("persona", persona);

  const res = await withTimeout(
    fetch(`${API_BASE}/api/review/upload`, { method: "POST", body: fd })
  );
  return handleResponse<ReviewResponse>(res);
}

/* ─── Docs endpoints ───────────────────────────────────── */
export async function docsFromRepo(
  repoUrl: string,
  persona: Persona
): Promise<DocsResponse> {
  const res = await withTimeout(
    fetch(`${API_BASE}/api/docs/repo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, persona }),
    })
  );
  return handleResponse<DocsResponse>(res);
}

export async function docsFromZip(
  file: File,
  persona: Persona
): Promise<DocsResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("persona", persona);

  const res = await withTimeout(
    fetch(`${API_BASE}/api/docs/upload`, { method: "POST", body: fd })
  );
  return handleResponse<DocsResponse>(res);
}
