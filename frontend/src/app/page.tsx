"use client";

import { useState } from "react";
import { createGuide } from "@/lib/api";

export default function Home() {
  const [companyUrl, setCompanyUrl] = useState("");
  const [pdf, setPdf] = useState<File | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guideId, setGuideId] = useState<string | null>(null);

  async function onGenerate() {
    setError(null);
    setGuideId(null);

    if (!companyUrl.trim()) {
      setError("Please enter a company website URL.");
      return;
    }
    if (!pdf) {
      setError("Please upload a PDF.");
      return;
    }

    try {
      setLoading(true);
      const res = await createGuide(companyUrl.trim(), pdf);
      setGuideId(res.guide_id);
    } catch (e: any) {
      setError(e?.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700 }}>
        Leveling Guide → Concrete Examples
      </h1>

      <p style={{ marginTop: 8, opacity: 0.8 }}>
        Upload a leveling guide PDF and provide a company website. We’ll generate
        3 concrete examples per competency × level.
      </p>

      <section
        style={{
          marginTop: 24,
          padding: 16,
          border: "1px solid #e5e7eb",
          borderRadius: 12,
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>Input</h2>

        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              Company website
            </span>
            <input
              type="url"
              placeholder="https://example.com"
              value={companyUrl}
              onChange={(e) => setCompanyUrl(e.target.value)}
              style={{
                padding: 10,
                border: "1px solid #e5e7eb",
                borderRadius: 8,
              }}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              Leveling guide PDF
            </span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setPdf(e.target.files?.[0] || null)}
            />
          </label>

          <button
            type="button"
            onClick={onGenerate}
            disabled={loading}
            style={{
              padding: 12,
              borderRadius: 10,
              border: "1px solid #111827",
              background: loading ? "#6b7280" : "#111827",
              color: "white",
              fontWeight: 600,
              width: 180,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Generating..." : "Generate"}
          </button>

          {error ? <p style={{ color: "crimson" }}>{error}</p> : null}

          {guideId ? (
            <p style={{ marginTop: 8 }}>
              Created guide: <code>{guideId}</code>
            </p>
          ) : null}
        </div>
      </section>

      <section
        style={{
          marginTop: 24,
          padding: 16,
          border: "1px solid #e5e7eb",
          borderRadius: 12,
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>Results</h2>
        <p style={{ marginTop: 8, opacity: 0.7 }}>
          Next: we’ll poll the backend and render the generated grid here.
        </p>
      </section>
    </main>
  );
}
