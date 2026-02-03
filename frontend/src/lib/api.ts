// src/lib/api.ts
// Minimal API client for the Leveling Guide backend.

export type GuideStatus = {
  guide_id: string;
  status: string; // QUEUED | PROCESSING | DONE | FAILED
};

// Allow easy switching between local/prod.
// In Next.js, define NEXT_PUBLIC_API_BASE_URL in .env.local
// Example: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function apiUrl(path: string) {
  if (!path.startsWith("/")) path = `/${path}`;
  return `${API_BASE_URL}${path}`;
}

async function readError(res: Response): Promise<string> {
  try {
    const j = await res.json();
    return j?.detail || j?.message || JSON.stringify(j);
  } catch {
    try {
      return await res.text();
    } catch {
      return `HTTP ${res.status}`;
    }
  }
}

export async function createGuide(input: {
  websiteUrl: string;
  roleTitle: string;
  pdfFile: File;
  companyName?: string;
  companyContext?: string;
}): Promise<GuideStatus> {
  const formData = new FormData();
  formData.append("website_url", input.websiteUrl);
  formData.append("role_title", input.roleTitle);
  formData.append("pdf", input.pdfFile);

  if (input.companyName) formData.append("company_name", input.companyName);
  if (input.companyContext) formData.append("company_context", input.companyContext);

  const res = await fetch(apiUrl("/api/guides"), {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function getGuideStatus(guideId: string): Promise<GuideStatus> {
  const res = await fetch(apiUrl(`/api/guides/${guideId}/status`), { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getGuideResults(guideId: string): Promise<any> {
  const res = await fetch(apiUrl(`/api/guides/${guideId}/results`), { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
