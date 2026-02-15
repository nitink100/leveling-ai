"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { createGuide, getGuideResults, getGuideStatus } from "@/lib/api";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { clearToken } from "@/lib/auth";

type Phase = "IDLE" | "UPLOADING" | "POLLING" | "DONE" | "FAILED";

type Example = { title: string; example: string };
type Cell = { level_id: string; definition_text?: string; examples?: Example[] };
type Competency = { id: string; name: string; cells?: Cell[] };
type Level = { id: string; label: string; position: number };

type Job = {
  localId: string;
  guideId: string | null;
  createdAt: number;

  websiteUrl: string;
  roleTitle: string;
  companyName?: string;
  companyContext?: string;
  fileName?: string;

  phase: Phase;
  status: string; // backend status (can be any string)
  err: string | null;

  results: any | null;
  resultsFetched: boolean;

  // for polling control
  startedPollingAt: number | null;
  lastPolledAt: number | null;
};

function StatusPill({ status }: { status: string }) {
  const s = (status || "UNKNOWN").toUpperCase();
  return <span className="pill">{s}</span>;
}

function CellBlock({
  title,
  definition,
  examples,
}: {
  title: string;
  definition: string;
  examples: Array<Example>;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="cellBlock">
      <div className="cellTop">
        <div className="cellTitle">{title}</div>
        <button className="btn" onClick={() => setOpen((v) => !v)} type="button">
          {open ? "Collapse" : "Expand"}
        </button>
      </div>

      <div className="cellText">
        {open ? definition : `${definition}`.slice(0, 160) + (definition.length > 160 ? "…" : "")}
      </div>

      {open && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 10 }}>
          {(examples || []).map((ex, idx) => (
            <div key={idx} className="cellExample">
              <div className="cellExampleTitle">{ex.title}</div>
              <div className="cellExampleText">{ex.example}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

function newLocalId() {
  return `job_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

function isTerminalStatus(status: string) {
  const s = (status || "").toUpperCase();
  return s === "DONE" || s === "FAILED";
}

/**
 * Polling schedule:
 * - For first 10s: every 1500ms (quick feedback)
 * - 10s–60s: every 6000ms (less aggressive, still responsive)
 * - After 60s: every 10000ms (slow fallback if backend is slow)
 */
function getPollIntervalMs(elapsedMs: number) {
  if (elapsedMs < 10_000) return 1500;
  if (elapsedMs < 60_000) return 6000;
  return 10_000;
}

export default function HomePage() {
  
  const router = useRouter();
  useEffect(() => {
    const t = getToken();
    if (!t) router.replace("/login");
  }, [router]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyContext, setCompanyContext] = useState("");

  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJobLocalId, setActiveJobLocalId] = useState<string | null>(null);

  const isUploading = useMemo(() => jobs.some((j) => j.phase === "UPLOADING"), [jobs]);

  const canSubmit = useMemo(() => {
    return (
      websiteUrl.trim().length > 0 &&
      roleTitle.trim().length > 0 &&
      !!selectedFile &&
      !isUploading
    );
  }, [websiteUrl, roleTitle, selectedFile, isUploading]);

  async function onSubmit() {
    if (!canSubmit) return;
    const pdfFile = selectedFile;
    if (!pdfFile) return;

    const localId = newLocalId();
    const now = Date.now();

    const job: Job = {
      localId,
      guideId: null,
      createdAt: now,
      websiteUrl: websiteUrl.trim(),
      roleTitle: roleTitle.trim(),
      companyName: companyName.trim() || undefined,
      companyContext: companyContext.trim() || undefined,
      fileName: pdfFile.name,

      phase: "UPLOADING",
      status: "UPLOADING",
      err: null,

      results: null,
      resultsFetched: false,

      startedPollingAt: null,
      lastPolledAt: null,
    };

    setJobs((prev) => [job, ...prev]);
    setActiveJobLocalId(localId);

    try {
      const created = await createGuide({
        websiteUrl: job.websiteUrl,
        roleTitle: job.roleTitle,
        pdfFile,
        companyName: job.companyName,
        companyContext: job.companyContext,
      });

      const createdStatus = created.status || "QUEUED";

      setJobs((prev) =>
        prev.map((j) =>
          j.localId === localId
            ? {
                ...j,
                guideId: created.guide_id,
                status: createdStatus,
                phase: isTerminalStatus(createdStatus) ? (createdStatus === "DONE" ? "DONE" : "FAILED") : "POLLING",
                startedPollingAt: now,
                lastPolledAt: now,
              }
            : j
        )
      );

      // reset file so you can upload another immediately
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e: any) {
      setJobs((prev) =>
        prev.map((j) =>
          j.localId === localId
            ? { ...j, phase: "FAILED", status: "FAILED", err: e?.message || "Failed to create guide." }
            : j
        )
      );
    }
  }

  // Manual refresh for a single job (status + results if DONE)
  async function refreshJob(localId: string) {
    const job = jobs.find((j) => j.localId === localId);
    if (!job?.guideId) return;

    try {
      const st = await getGuideStatus(job.guideId);
      const nextStatus = st.status || job.status;

      setJobs((prev) =>
        prev.map((j) => {
          if (j.localId !== localId) return j;

          let nextPhase: Phase = j.phase;
          if (nextStatus.toUpperCase() === "FAILED") nextPhase = "FAILED";
          else if (nextStatus.toUpperCase() === "DONE") nextPhase = "DONE";
          else nextPhase = "POLLING";

          return { ...j, status: nextStatus, phase: nextPhase, err: null, lastPolledAt: Date.now() };
        })
      );

      if (nextStatus.toUpperCase() === "DONE") {
        const res = await getGuideResults(job.guideId);
        setJobs((prev) =>
          prev.map((j) =>
            j.localId === localId ? { ...j, results: res, resultsFetched: true, phase: "DONE", err: null } : j
          )
        );
      }
    } catch (e: any) {
      setJobs((prev) =>
        prev.map((j) => (j.localId === localId ? { ...j, err: e?.message || "Refresh failed." } : j))
      );
    }
  }

  /**
   * Background polling loop:
   * - Poll ANY job that is not DONE/FAILED and has a guideId.
   * - Dynamic interval per job based on its elapsed time.
   * - Keep polling until terminal or long timeout (soft).
   *
   * NOTE: This avoids the “polling stopped after extraction” bug because we no longer depend
   * on the status being exactly QUEUED/PROCESSING.
   */
  useEffect(() => {
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        const now = Date.now();

        const targets = jobs.filter((j) => {
          if (!j.guideId) return false;
          if (isTerminalStatus(j.status)) return false;

          // if never started pollingAt, start it
          const startedAt = j.startedPollingAt ?? j.createdAt;
          const elapsed = now - startedAt;
          const interval = getPollIntervalMs(elapsed);
          const last = j.lastPolledAt ?? 0;

          return now - last >= interval;
        });

        // Poll sequentially to avoid spiking backend; still handles multiple jobs well
        for (const t of targets) {
          if (cancelled) break;
          try {
            const st = await getGuideStatus(t.guideId!);
            if (cancelled) break;

            const nextStatus = st.status || t.status;
            const upper = nextStatus.toUpperCase();

            setJobs((prev) =>
              prev.map((j) => {
                if (j.localId !== t.localId) return j;

                let nextPhase: Phase = j.phase;
                if (upper === "FAILED") nextPhase = "FAILED";
                else if (upper === "DONE") nextPhase = "DONE";
                else nextPhase = "POLLING";

                return {
                  ...j,
                  status: nextStatus,
                  phase: nextPhase,
                  err: null,
                  startedPollingAt: j.startedPollingAt ?? j.createdAt,
                  lastPolledAt: Date.now(),
                };
              })
            );

            // Auto-fetch results right away when DONE
            if (upper === "DONE") {
              const res = await getGuideResults(t.guideId!);
              if (cancelled) break;

              setJobs((prev) =>
                prev.map((j) =>
                  j.localId === t.localId ? { ...j, results: res, resultsFetched: true, phase: "DONE", err: null } : j
                )
              );
            }
          } catch (e: any) {
            const msg = e?.message || "Polling error";
            setJobs((prev) =>
              prev.map((j) =>
                j.localId === t.localId ? { ...j, err: msg, lastPolledAt: Date.now() } : j
              )
            );
          }
        }

        // Sleep a bit before next scan; small to keep loop responsive
        await new Promise((r) => setTimeout(r, 750));
      }
    };

    // Only run if there is at least one non-terminal job
    const hasLive = jobs.some((j) => j.guideId && !isTerminalStatus(j.status));
    if (hasLive) loop();

    return () => {
      cancelled = true;
    };
  }, [jobs]);

  const inProgress = jobs.filter((j) => j.guideId && !isTerminalStatus(j.status));
  const completed = jobs.filter((j) => j.guideId && j.status.toUpperCase() === "DONE");
  const failed = jobs.filter((j) => j.guideId && j.status.toUpperCase() === "FAILED");

  const activeJob = useMemo(() => {
    if (!activeJobLocalId) return null;
    return jobs.find((j) => j.localId === activeJobLocalId) || null;
  }, [jobs, activeJobLocalId]);

  const results = activeJob?.results || null;
  const levels: Level[] = results?.levels || [];
  const competencies: Competency[] = results?.competencies || [];

  return (
    <main className="container">
      <div>
        <div className="title">Leveling Guide → Evidence Examples</div>
        <div className="subtitle">
          Upload a leveling guide PDF and generate examples per matrix cell. Multiple jobs can run in parallel.
        </div>
      </div>
      <br></br>
      <button
        className="btn"
        type="button"
        onClick={() => {
          clearToken();
          router.push("/login");
        }}
      >
        Logout
      </button>

      {/* Form */}
      <div className="grid">
        <div className="field">
          <label className="label">Company website URL(mandatory)</label>
          <input
            className="input"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            placeholder="https://example.com"
          />
        </div>

        <div className="field">
          <label className="label">Role title(mandatory)</label>
          <input
            className="input"
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            placeholder="e.g., Backend Engineer, Data Scientist, Product Manager"
          />
        </div>

        <div className="field">
          <label className="label">Leveling guide PDF(mandatory)</label>

          <div className="uploadBox">
            <div className="uploadLeft">
              <div className="fileName">{selectedFile ? selectedFile.name : "No file selected"}</div>
              <div className="small">PDF only</div>
            </div>

            <div className="row" style={{ justifyContent: "flex-end" }}>
              <input
                ref={fileInputRef}
                className="hiddenFile"
                type="file"
                accept="application/pdf"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />

              <button className="btn" onClick={() => fileInputRef.current?.click()} type="button">
                Choose PDF
              </button>

              {selectedFile && (
                <button
                  className="btn"
                  onClick={() => {
                    setSelectedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  type="button"
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="field">
          <label className="label">Company name (optional)</label>
          <input
            className="input"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="field">
          <label className="label">Company context (optional)</label>
          <textarea
            className="textarea"
            value={companyContext}
            onChange={(e) => setCompanyContext(e.target.value)}
            placeholder="Optional: short description of the product/domain to ground examples."
            rows={4}
          />
        </div>

        <div className="row">
          <button
            className={`btn ${canSubmit ? "btnPrimary" : ""}`}
            disabled={!canSubmit}
            onClick={onSubmit}
            type="button"
          >
            {isUploading ? "Uploading…" : "Generate Examples"}
          </button>

          <div className="muted" style={{ fontSize: 13 }}>
            Polling is adaptive (fast first, then 5–10s).
          </div>
        </div>
      </div>

      {/* Jobs */}
      <div style={{ marginTop: 22 }} className="card">
        <div className="cardHeader">
          <div>Guides</div>
          <div className="muted" style={{ fontSize: 13 }}>
            Click “View” to open Guide + “Refresh” to force status/results now
          </div>
        </div>

        <div className="cardBody">
          {jobs.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>No jobs yet.</div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              <div>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>In progress</div>
                {inProgress.length === 0 ? (
                  <div className="muted" style={{ fontSize: 13 }}>None</div>
                ) : (
                  <div className="jobsGrid">
                    {inProgress.map((j) => (
                      <div key={j.localId} className="jobItem">
                        <div className="jobMeta">
                          <div>
                            <div style={{ fontWeight: 700 }}>{j.roleTitle}</div>
                            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                              {j.fileName || "PDF"} • {formatTime(j.createdAt)}
                            </div>
                            {j.guideId && <div className="code" style={{ marginTop: 6 }}>{j.guideId}</div>}
                            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                              Last polled: {j.lastPolledAt ? formatTime(j.lastPolledAt) : "—"}
                            </div>
                          </div>

                          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
                            <StatusPill status={j.status} />
                            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                              <button className="btn" type="button" onClick={() => setActiveJobLocalId(j.localId)}>
                                View
                              </button>
                              <button className="btn" type="button" onClick={() => refreshJob(j.localId)}>
                                Refresh
                              </button>
                            </div>
                          </div>
                        </div>

                        {j.err && (
                          <div style={{ marginTop: 10 }} className="errorBox">
                            <div style={{ fontWeight: 700 }}>Warning</div>
                            <div style={{ opacity: 0.9, marginTop: 6 }}>{j.err}</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Completed</div>
                {completed.length === 0 ? (
                  <div className="muted" style={{ fontSize: 13 }}>None</div>
                ) : (
                  <div className="jobsGrid">
                    {completed.map((j) => (
                      <div key={j.localId} className="jobItem">
                        <div className="jobMeta">
                          <div>
                            <div style={{ fontWeight: 700 }}>{j.roleTitle}</div>
                            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                              {j.fileName || "PDF"} • {formatTime(j.createdAt)}
                            </div>
                            {j.guideId && <div className="code" style={{ marginTop: 6 }}>{j.guideId}</div>}
                          </div>

                          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
                            <StatusPill status={j.status} />
                            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                              <button
                                className={`btn ${activeJobLocalId === j.localId ? "btnPrimary" : ""}`}
                                type="button"
                                onClick={() => setActiveJobLocalId(j.localId)}
                              >
                                {activeJobLocalId === j.localId ? "Showing" : "Show Results"}
                              </button>
                              <button className="btn" type="button" onClick={() => refreshJob(j.localId)}>
                                Refresh
                              </button>
                            </div>
                          </div>
                        </div>

                        {j.err && (
                          <div style={{ marginTop: 10 }} className="errorBox">
                            <div style={{ fontWeight: 700 }}>Note</div>
                            <div style={{ opacity: 0.9, marginTop: 6 }}>{j.err}</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Failed</div>
                {failed.length === 0 ? (
                  <div className="muted" style={{ fontSize: 13 }}>None</div>
                ) : (
                  <div className="jobsGrid">
                    {failed.map((j) => (
                      <div key={j.localId} className="jobItem">
                        <div className="jobMeta">
                          <div>
                            <div style={{ fontWeight: 700 }}>{j.roleTitle}</div>
                            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                              {j.fileName || "PDF"} • {formatTime(j.createdAt)}
                            </div>
                            {j.guideId && <div className="code" style={{ marginTop: 6 }}>{j.guideId}</div>}
                          </div>

                          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
                            <StatusPill status={j.status} />
                            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                              <button className="btn" type="button" onClick={() => setActiveJobLocalId(j.localId)}>
                                View
                              </button>
                              <button className="btn" type="button" onClick={() => refreshJob(j.localId)}>
                                Refresh
                              </button>
                            </div>
                          </div>
                        </div>

                        {j.err && (
                          <div style={{ marginTop: 10 }} className="errorBox">
                            <div style={{ fontWeight: 700 }}>Error</div>
                            <div style={{ opacity: 0.9, marginTop: 6 }}>{j.err}</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div style={{ marginTop: 22 }} className="card">
        <div className="cardHeader">
          <div>Results</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {activeJob ? `Active: ${activeJob.roleTitle} • ${activeJob.status}` : "Select a Guide"}
          </div>
        </div>

        <div className="cardBody">
          {!activeJob ? (
            <div className="muted" style={{ fontSize: 13 }}>Pick a job above.</div>
          ) : activeJob.status.toUpperCase() !== "DONE" ? (
            <div className="muted" style={{ fontSize: 13 }}>
              Not DONE yet. Status: <b>{activeJob.status}</b> •{" "}
              <button className="btn" type="button" onClick={() => refreshJob(activeJob.localId)}>
                Refresh now
              </button>
            </div>
          ) : !results ? (
            <div className="muted" style={{ fontSize: 13 }}>
              DONE but results not loaded yet. Click{" "}
              <button className="btn" type="button" onClick={() => refreshJob(activeJob.localId)}>
                Refresh
              </button>
            </div>
          ) : (
            <div>
              <div className="muted" style={{ fontSize: 13 }}>
                Prompt version: <span className="code">{results.prompt_version}</span> • Completed:{" "}
                <span className="code">
                  {results.progress?.completed}/{results.progress?.expected}
                </span>
              </div>

              <div className="matrixWrap">
                <div className="matrixMinWidth">
                  <div
                    className="matrixHeaderRow"
                    style={{
                      gridTemplateColumns: `260px repeat(${levels.length}, minmax(240px, 1fr))`,
                    }}
                  >
                    <div style={{ fontWeight: 700 }}>Competency</div>
                    {levels.map((lv) => (
                      <div key={lv.id} style={{ fontWeight: 700 }}>
                        {lv.label}
                      </div>
                    ))}
                  </div>

                  <div style={{ display: "grid", gap: 0 }}>
                    {competencies.map((comp) => (
                      <div
                        key={comp.id}
                        className="matrixRow"
                        style={{
                          gridTemplateColumns: `260px repeat(${levels.length}, minmax(240px, 1fr))`,
                        }}
                      >
                        <div style={{ fontWeight: 700, opacity: 0.95 }}>{comp.name}</div>

                        {levels.map((lv) => {
                          const cell = (comp.cells || []).find((c) => c.level_id === lv.id);
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

              {results?.notes && <div style={{ marginTop: 12 }} className="muted">Notes: {results.notes}</div>}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
