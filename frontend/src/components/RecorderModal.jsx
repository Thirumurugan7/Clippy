import { useState, useRef, useEffect } from "react";
import { useRecorder } from "../hooks/useRecorder.js";

function clock(s) {
  const m = Math.floor(s / 60);
  const ss = s % 60;
  return `${m}:${String(ss).padStart(2, "0")}`;
}

// Auto-scrolling teleprompter. A state-driven translateY (advanced on an
// interval) scrolls the script upward while `running`, looping at the end.
// State-driven (not scrollTop+rAF) so it survives StrictMode cleanly. Works
// with or without a camera.
function Teleprompter({ script, speed, running, className }) {
  const [offset, setOffset] = useState(0);
  const outerRef = useRef(null);
  const innerRef = useRef(null);

  useEffect(() => {
    if (running) setOffset(0);
  }, [running]);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      setOffset((o) => {
        const inner = innerRef.current;
        const outer = outerRef.current;
        const max = inner && outer ? inner.scrollHeight - outer.clientHeight + 40 : Infinity;
        const next = o + speed * 0.05; // 50ms tick
        return next >= max ? 0 : next;
      });
    }, 50);
    return () => clearInterval(id);
  }, [running, speed]);

  return (
    <div ref={outerRef} className={"tp-view " + (className || "")}>
      <div ref={innerRef} className="tp-text" style={{ transform: `translateY(${-offset}px)` }}>
        {script}
      </div>
    </div>
  );
}

// Capture a webcam or screen recording, then hand the webm to the normal upload
// flow (onUse) so it becomes a source video to edit. Optional teleprompter
// scrolls a script you read while looking at the camera.
export function RecorderModal({ onClose, onUse }) {
  const { state, error, elapsed, blob, previewRef, startPreview, start, stop, reset } = useRecorder();
  const [source, setSource] = useState("camera");
  const [busy, setBusy] = useState(false);
  const [script, setScript] = useState("");
  const [speed, setSpeed] = useState(80);
  const [rehearse, setRehearse] = useState(false);
  const hasScript = script.trim().length > 0;

  async function use() {
    if (!blob) return;
    setBusy(true);
    const file = new File([blob], `recording-${Date.now()}.webm`, { type: "video/webm" });
    await onUse(file);
    setBusy(false);
    onClose();
  }

  return (
    <div className="modal-scrim" onMouseDown={onClose}>
      <div className="modal recorder" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Record</h3>
          <button className="modal-x" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {state === "idle" && (
          <>
            <p className="panel-sub">Capture a clip without leaving Clippy. It uploads and opens for editing.</p>
            <div className="seg-toggle wide">
              <button className={source === "camera" ? "on" : ""} onClick={() => setSource("camera")}>📷 Webcam</button>
              <button className={source === "screen" ? "on" : ""} onClick={() => setSource("screen")}>🖥 Screen</button>
            </div>

            <textarea
              className="ai-input tp-script"
              rows={3}
              placeholder="Teleprompter script (optional) — it scrolls while you record"
              value={script}
              onChange={(e) => setScript(e.target.value)}
            />
            {hasScript && (
              <>
                <div className="panel-row">
                  <label>Scroll speed</label>
                  <input type="range" min="30" max="220" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
                </div>
                <button className="btn-ghost full" onClick={() => setRehearse((r) => !r)}>
                  {rehearse ? "■ Pause rehearsal" : "▶ Rehearse teleprompter"}
                </button>
                {rehearse && <Teleprompter script={script} speed={speed} running={rehearse} className="tp-rehearse" />}
              </>
            )}

            <button className="btn-amber full" onClick={() => startPreview(source)}>
              {source === "screen" ? "Choose a screen to share" : "Turn on camera"}
            </button>
          </>
        )}

        {(state === "preview" || state === "recording") && (
          <>
            <div className="rec-stage">
              <video ref={previewRef} className="rec-video" playsInline />
              {hasScript && <Teleprompter script={script} speed={speed} running={state === "recording"} className="tp-overlay" />}
              {state === "recording" && <span className="rec-dot" />}
              {state === "recording" && <span className="rec-time mono">{clock(elapsed)}</span>}
            </div>
            {state === "preview" ? (
              <button className="btn-amber full" onClick={start}>● Start recording</button>
            ) : (
              <button className="btn-danger full" onClick={stop}>■ Stop</button>
            )}
          </>
        )}

        {state === "recorded" && blob && (
          <>
            <div className="rec-stage">
              <video className="rec-video" src={URL.createObjectURL(blob)} controls playsInline />
            </div>
            <div className="rec-actions">
              <button className="btn-ghost" onClick={reset} disabled={busy}>Re-record</button>
              <button className="btn-amber" onClick={use} disabled={busy}>
                {busy ? "Uploading…" : "Use this recording"}
              </button>
            </div>
          </>
        )}

        {state === "error" && (
          <>
            <p className="error">{error}</p>
            <button className="btn-amber full" onClick={reset}>Try again</button>
          </>
        )}
      </div>
    </div>
  );
}
