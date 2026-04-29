import { DocsResponse, Persona, ReviewResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function reviewFromRepo(repoUrl: string, persona: Persona): Promise<ReviewResponse> {
  const res = await fetch(`${API_BASE}/api/review/repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl, persona }),
  });
  return handleResponse<ReviewResponse>(res);
}

export async function reviewFromZip(file: File, persona: Persona): Promise<ReviewResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("persona", persona);

  const res = await fetch(`${API_BASE}/api/review/upload`, {
    method: "POST",
    body: fd,
  });
  return handleResponse<ReviewResponse>(res);
}

export async function docsFromRepo(repoUrl: string, persona: Persona): Promise<DocsResponse> {
  const res = await fetch(`${API_BASE}/api/docs/repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl, persona }),
  });
  return handleResponse<DocsResponse>(res);
}

export async function docsFromZip(file: File, persona: Persona): Promise<DocsResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("persona", persona);

  const res = await fetch(`${API_BASE}/api/docs/upload`, {
    method: "POST",
    body: fd,
  });
  return handleResponse<DocsResponse>(res);
}
