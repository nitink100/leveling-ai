const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function assertOk(res: Response, fallbackMsg: string): Promise<void> {
  if (res.ok) return Promise.resolve();
  return res
    .text()
    .then((t) => {
      const msg = t?.trim() || fallbackMsg;
      throw new Error(msg);
    })
    .catch(() => {
      throw new Error(fallbackMsg);
    });
}

export type CreateGuideInput = {
  websiteUrl: string;
  roleTitle: string;
  pdfFile: File;
  companyName?: string;
  companyContext?: string;
};

export type CreateGuideResponse = {
  ok?: boolean;
  guide_id: string;
  status?: string;
  prompt_version?: string;
};

export async function createGuide(input: CreateGuideInput): Promise<CreateGuideResponse> {
  const fd = new FormData();
  fd.append("website_url", input.websiteUrl);
  fd.append("role_title", input.roleTitle);
  fd.append("pdf", input.pdfFile);

  if (input.companyName) fd.append("company_name", input.companyName);
  if (input.companyContext) fd.append("company_context", input.companyContext);

  const res = await fetch(`${API_BASE}/api/guides`, {
    method: "POST",
    body: fd,
  });

  await assertOk(res, "Failed to create guide.");
  return res.json();
}

export type GuideStatusResponse = {
  ok?: boolean;
  guide_id?: string;
  status: string;
};

export async function getGuideStatus(guideId: string): Promise<GuideStatusResponse> {
  const res = await fetch(`${API_BASE}/api/guides/${guideId}`, { method: "GET" });
  await assertOk(res, "Failed to fetch guide status.");
  return res.json();
}

export async function getGuideResults(guideId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/guides/${guideId}/results`, { method: "GET" });
  await assertOk(res, "Failed to fetch guide results.");
  return res.json();
}
