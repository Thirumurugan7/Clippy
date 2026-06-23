import { useHighlights } from "../hooks/useHighlights.js";

function fmt(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Circular "heat" gauge — the signature element. Fill ∝ score; hotter = stronger.
function HeatRing({ score }) {
  const pct = score == null ? 0 : Math.max(0, Math.min(1, score));
  const r = 18;
  const c = 2 * Math.PI * r;
  return (
    <svg className="heat-ring" width="46" height="46" viewBox="0 0 46 46" aria-hidden>
      <circle cx="23" cy="23" r={r} className="heat-track" />
      <circle
        cx="23"
        cy="23"
        r={r}
        className="heat-fill"
        style={{ strokeDasharray: c, strokeDashoffset: c * (1 - pct) }}
      />
      <text x="23" y="24" className="heat-num">
        {score == null ? "–" : Math.round(pct * 100)}
      </text>
    </svg>
  );
}

export function HighlightsRail({ videoId, onUseClip, onPreviewClip, activeClip }) {
  const { status, clips, model, error, raw, generate } = useHighlights(videoId);

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
