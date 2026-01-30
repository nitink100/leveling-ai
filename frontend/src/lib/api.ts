const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function createGuide(companyUrl: string, pdfFile: File) {
  const formData = new FormData();
  formData.append("company_url", companyUrl);
  formData.append("pdf", pdfFile);

  const resp = await fetch(`${API_BASE_URL}/api/guides`, {
    method: "POST",
    body: formData,
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "Failed to create guide");
  }

  return resp.json() as Promise<{ guide_id: string; status: string }>;
}
