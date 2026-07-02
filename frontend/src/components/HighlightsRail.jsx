import { useState, useCallback } from "react";
import { useHighlights } from "../hooks/useHighlights.js";

// Enqueue ONE batch job that renders every highlight as its own vertical short,
// then expose per-clip download links. The "one long video -> many clips" flow.
function useBatchExport(videoId) {
  const [status, setStatus] = useState("idle"); // idle|running|done|failed
  const [result, setResult] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    setStatus("running");
    setError(null);
    setResult(null);
    const res = await fetch(`/api/videos/${videoId}/export_batch`, { method: "POST" });
    if (!res.ok) {
      setStatus("failed");
      setError((await res.json().catch(() => ({}))).detail || "could not start");
      return;
    }
    const { job_id } = await res.json();
    setJobId(job_id);
    function poll() {
      fetch(`/api/jobs/${job_id}`)
        .then((r) => r.json())
        .then((job) => {
          if (job.status === "done") {
            setResult(JSON.parse(job.result_json || "{}"));
            setStatus("done");
          } else if (job.status === "failed") {
            setError(job.error);
            setStatus("failed");
          } else {
            setTimeout(poll, 1500);
          }
        });
    }
    poll();
  }, [videoId]);

  return { status, result, jobId, error, run };
}

function fmt(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// The heat scale: a cool score is blue, a hot one climbs violet → magenta → amber.
// Colour encodes hook strength, not just the fill amount — the page's signature.
const HEAT_STOPS = [
  [0.0, [0x6d, 0x7c, 0xf6]],
  [0.5, [0x8b, 0x6c, 0xf6]],
  [0.8, [0xe0, 0x56, 0x9f]],
  [1.0, [0xf5, 0xa3, 0x4d]],
];

function heatColor(pct) {
  for (let i = 1; i < HEAT_STOPS.length; i++) {
    const [p1, c1] = HEAT_STOPS[i];
    if (pct <= p1) {
      const [p0, c0] = HEAT_STOPS[i - 1];
      const t = p1 === p0 ? 0 : (pct - p0) / (p1 - p0);
      const [r, g, b] = c0.map((v, k) => Math.round(v + (c1[k] - v) * t));
      return `rgb(${r}, ${g}, ${b})`;
    }
  }
  return "rgb(245, 163, 77)";
}

// Circular "heat" gauge — the signature element. Fill ∝ score; hue = hook strength.
function HeatRing({ score }) {
  const pct = score == null ? 0 : Math.max(0, Math.min(1, score));
  const r = 18;
  const c = 2 * Math.PI * r;
  const col = heatColor(pct);
  return (
    <svg className="heat-ring" width="46" height="46" viewBox="0 0 46 46" aria-hidden>
      <circle cx="23" cy="23" r={r} className="heat-track" />
      <circle
        cx="23"
        cy="23"
        r={r}
        className="heat-fill"
        style={{
          stroke: score == null ? "var(--line-2)" : col,
          strokeDasharray: c,
          strokeDashoffset: c * (1 - pct),
          filter: score == null ? "none" : `drop-shadow(0 0 5px ${col})`,
        }}
      />
      <text x="23" y="24" className="heat-num">
        {score == null ? "–" : Math.round(pct * 100)}
      </text>
    </svg>
  );
}

export function HighlightsRail({ videoId, onUseClip, onPreviewClip, activeClip }) {
  const { status, clips, model, error, raw, generate } = useHighlights(videoId);
  const batch = useBatchExport(videoId);

  return (
    <aside className="rail">
      <div className="rail-head">
        <div>
          <h2>Highlights</h2>
          <p className="rail-sub">AI picks the strongest moments — you choose and trim.</p>
        </div>
        <button
          className="btn-amber"
          onClick={generate}
          disabled={status === "running"}
        >
          {status === "running"
            ? "Analyzing…"
            : clips
            ? "Regenerate"
            : "Find highlights"}
        </button>
      </div>

      {clips && clips.length > 0 && (
        <div className="batch-bar">
          <button
            className="btn-amber btn-batch"
            onClick={batch.run}
            disabled={batch.status === "running"}
          >
            {batch.status === "running"
              ? `Rendering ${clips.length} shorts…`
              : `Export all ${clips.length} as 9:16 shorts`}
          </button>
          {batch.status === "failed" && (
            <p className="mono error">{batch.error || "batch export failed"}</p>
          )}
          {batch.status === "done" && batch.result && (
            <div className="batch-results">
              <p className="rail-foot mono">
                {batch.result.ok}/{batch.result.count} rendered
              </p>
              {batch.result.clips.map((c) => (
                <div key={c.index} className="batch-row">
                  <span className="mono">#{c.index + 1} · {fmt(c.start)}–{fmt(c.end)}</span>
                  {c.error ? (
                    <span className="error mono">failed</span>
                  ) : (
                    <a
                      className="btn-use"
                      href={`/api/exports/${batch.jobId}/clip/${c.index}/file`}
                      download={`clip-${c.index + 1}.mp4`}
                    >
                      Download
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {status === "running" && (
        <div className="rail-state mono">gemma4 is reading the transcript…</div>
      )}

      {status === "idle" && (
        <div className="rail-empty">
          <p>No highlights yet.</p>
          <p className="muted">Generate AI picks from your transcript, then turn any one into a short.</p>
        </div>
      )}

      {status === "failed" && (
        <div className="rail-state">
          <p className="error">Couldn't read clips from the model.</p>
          {error && <p className="mono error">{error}</p>}
          {raw && <details><summary className="mono">raw output</summary><pre className="raw">{raw}</pre></details>}
        </div>
      )}

      {clips && (
        <div className="clip-list">
          {clips.map((c, i) => {
            const dur = c.end - c.start;
            const on = activeClip && activeClip.start === c.start && activeClip.end === c.end;
            return (
              <div
                key={i}
                className={"hl-card" + (on ? " hl-card-on" : "")}
                onClick={() => onPreviewClip(c)}
              >
                <HeatRing score={c.score} />
                <div className="hl-body">
                  <div className="hl-meta">
                    <span className="hl-range mono">{fmt(c.start)}–{fmt(c.end)}</span>
                    <span className="hl-dur">{Math.round(dur)}s</span>
                  </div>
                  <p className="hl-reason">{c.reason}</p>
                  <button
                    className="btn-use"
                    onClick={(e) => {
                      e.stopPropagation();
                      onUseClip(c);
                    }}
                  >
                    {on ? "Editing this clip" : "Use clip"}
                  </button>
                </div>
              </div>
            );
          })}
          {model && <p className="rail-foot mono">{clips.length} candidates · {model}</p>}
        </div>
      )}
    </aside>
  );
}
