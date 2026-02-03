"use client";

import React, { useMemo, useRef, useState } from "react";
import { createGuide, getGuideResults, getGuideStatus } from "@/lib/api";

type Phase = "IDLE" | "UPLOADING" | "POLLING" | "DONE" | "FAILED";

function StatusPill({ status }: { status: string }) {
  const s = status?.toUpperCase?.() || "UNKNOWN";
  const tone =
    s === "DONE"
      ? "rgba(80, 200, 120, 0.25)"
      : s === "FAILED"
        ? "rgba(255, 80, 80, 0.25)"
        : "rgba(255, 255, 255, 0.10)";

  return (
    <span
      style={{
        display: "inline-block",
        padding: "5px 10px",
        borderRadius: 999,
        fontSize: 12,
        border: "1px solid rgba(255,255,255,0.18)",
        background: tone,
      }}
    >
      {s}
    </span>
  );
}

function CellBlock({
  title,
  definition,
  examples,
}: {
  title: string;
  definition: string;
  examples: Array<{ title: string; example: string }>;
}) {
  const [open, setOpen] = useState(false);

  const preview = useMemo(() => {
    const txt = definition || "";
    if (!txt) return "";
    return txt.length > 180 ? txt.slice(0, 180) + "…" : txt;
  }, [definition]);

  return (
    <div className="cell">
      <div className="cellTop">
        <div className="cellTitle">{title}</div>
        <button className="cellBtn" onClick={() => setOpen((v) => !v)}>
          {open ? "Collapse" : "Expand"}
        </button>
      </div>

      <div className="cellText">{open ? definition : preview}</div>

      {open && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          {(examples || []).map((ex, idx) => (
            <div key={idx} className="exampleBlock">
              <div className="exampleTitle">{ex.title}</div>
              <div className="exampleText">{ex.example}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [phase, setPhase] = useState<Phase>("IDLE");
  const [err, setErr] = useState<string | null>(null);

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyContext, setCompanyContext] = useState("");

  // ✅ IMPORTANT: keep selected file in state so React re-renders on file change
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  const [guideId, setGuideId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");

  const [results, setResults] = useState<any>(null);

  const canSubmit = useMemo(() => {
    return (
      websiteUrl.trim().length > 0 &&
      roleTitle.trim().length > 0 &&
      !!pdfFile &&
      phase !== "UPLOADING" &&
      phase !== "POLLING"
    );
  }, [websiteUrl, roleTitle, pdfFile, phase]);

  function pickFile() {
    fileInputRef.current?.click();
  }

  function onFilePicked(f: File | null) {
    if (!f) {
      setPdfFile(null);
      return;
    }
    if (f.type !== "application/pdf") {
      setPdfFile(null);
      setErr("Please select a PDF file.");
      return;
    }
    setErr(null);
    setPdfFile(f);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    const f = e.dataTransfer.files?.[0];
    onFilePicked(f || null);
  }

  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
  }

  async function onSubmit() {
    setErr(null);
    setResults(null);

    if (!pdfFile) {
      setErr("Please select a PDF.");
      return;
    }

    try {
      setPhase("UPLOADING");

      const created = await createGuide({
        websiteUrl: websiteUrl.trim(),
        roleTitle: roleTitle.trim(),
        pdfFile,
        companyName: companyName.trim() || undefined,
        companyContext: companyContext.trim() || undefined,
      });

      setGuideId(created.guide_id);
      setStatus(created.status || "QUEUED");
      setPhase("POLLING");

      // Poll status until DONE/FAILED, then fetch results
      const maxMs = 60_000; // 1 minute product expectation
      const started = Date.now();

      while (true) {
        const st = await getGuideStatus(created.guide_id);
        setStatus(st.status);

        if (st.status === "DONE") break;

        if (st.status === "FAILED") {
          setPhase("FAILED");
          setErr("Processing failed. Check backend logs for the failure reason.");
          return;
        }

        if (Date.now() - started > maxMs) {
          setPhase("FAILED");
          setErr("Timed out waiting for results (> 60s).");
          return;
        }

        await new Promise((r) => setTimeout(r, 1000));
      }

      const res = await getGuideResults(created.guide_id);
      setResults(res);
      setPhase("DONE");
    } catch (e: any) {
      setPhase("FAILED");
      setErr(e?.message || "Something went wrong.");
    }
  }

  const levels = results?.levels || [];
  const competencies = results?.competencies || [];

  const gridTemplateColumns = useMemo(() => {
    return `260px repeat(${levels.length}, minmax(240px, 1fr))`;
  }, [levels.length]);

  return (
    <main className="container">
      <h1 className="title">Leveling Guide → Evidence Examples</h1>
      <p className="subtitle">
        Upload a leveling guide PDF and get 3 concrete examples per cell. Results should appear within ~1 minute.
      </p>

      <div className="formGrid">
        <div className="card">
          <div className="field">
            <label className="label">Company website URL</label>
            <input
              className="input"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://example.com"
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="label">Role title</label>
            <input
              className="input"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              placeholder="e.g., Backend Engineer, Data Scientist, PM"
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="label">Leveling guide PDF</label>

            {/* Hidden input, pretty box UI */}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              style={{ display: "none" }}
              onChange={(e) => onFilePicked(e.target.files?.[0] || null)}
            />

            <div className="uploadBox" onClick={pickFile} onDrop={onDrop} onDragOver={onDragOver}>
              <div className="uploadLeft">
                <div className="uploadTitle">Choose a PDF</div>
                <div className="uploadHint">Click to browse or drag & drop here</div>
              </div>

              <div className="filePill">{pdfFile ? pdfFile.name : "No file selected"}</div>
            </div>
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="label">Company name (optional)</label>
            <input
              className="input"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <label className="label">Company context (optional)</label>
            <textarea
              className="textarea"
              value={companyContext}
              onChange={(e) => setCompanyContext(e.target.value)}
              placeholder="Optional: short company/product/domain context to ground examples."
              rows={4}
            />
          </div>

          <div className="actionsRow" style={{ marginTop: 14 }}>
            <button className="button" disabled={!canSubmit} onClick={onSubmit}>
              {phase === "UPLOADING" ? "Uploading…" : phase === "POLLING" ? "Processing…" : "Generate Examples"}
            </button>

            {guideId && (
              <div className="metaRow">
                <div style={{ fontSize: 13, opacity: 0.85 }}>Guide:</div>
                <code style={{ fontSize: 12 }}>{guideId}</code>
                <StatusPill status={status} />
              </div>
            )}
          </div>

          {err && (
            <div className="errorBox" style={{ marginTop: 14 }}>
              <div className="errorTitle">Error</div>
              <div className="errorText">{err}</div>
            </div>
          )}

          {phase === "POLLING" && (
            <div style={{ marginTop: 12, opacity: 0.85 }}>
              Processing… polling status every 1s (expected &lt; 60s).
            </div>
          )}
        </div>
      </div>

      {phase === "DONE" && results && (
        <section className="resultsHeader">
          <h2 style={{ fontSize: 18, fontWeight: 800 }}>Results</h2>
          <div className="resultsMeta">
            Prompt version: <code>{results.prompt_version}</code> • Completed:{" "}
            <code>
              {results.progress?.completed}/{results.progress?.expected}
            </code>
          </div>

          <div className="tableWrap">
            <div className="tableInner">
              {/* Header row */}
              <div className="tableHeaderRow" style={{ gridTemplateColumns }}>
                <div style={{ fontWeight: 800 }}>Competency</div>
                {levels.map((lv: any) => (
                  <div key={lv.id} style={{ fontWeight: 800 }}>
                    {lv.label}
                  </div>
                ))}
              </div>

              {/* Body rows */}
              <div style={{ display: "grid" }}>
                {competencies.map((comp: any) => (
                  <div key={comp.id} className="tableBodyRow" style={{ gridTemplateColumns }}>
                    <div style={{ fontWeight: 800, opacity: 0.95 }}>{comp.name}</div>

                    {levels.map((lv: any) => {
                      const cell = (comp.cells || []).find((c: any) => c.level_id === lv.id);

                      if (!cell) {
                        return (
                          <div key={lv.id} style={{ opacity: 0.6, fontSize: 13 }}>
                            No cell found
                          </div>
                        );
                      }

                      return (
                        <CellBlock
                          key={lv.id}
                          title="Definition + Examples"
                          definition={cell.definition_text || ""}
                          examples={cell.examples || []}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
