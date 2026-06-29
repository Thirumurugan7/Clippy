import { useState } from "react";
import { useRecorder } from "../hooks/useRecorder.js";

function clock(s) {
  const m = Math.floor(s / 60);
  const ss = s % 60;
  return `${m}:${String(ss).padStart(2, "0")}`;
}

// Capture a webcam or screen recording, then hand the webm to the normal upload
// flow (onUse) so it becomes a source video to edit.
export function RecorderModal({ onClose, onUse }) {
  const { state, error, elapsed, blob, previewRef, startPreview, start, stop, reset } = useRecorder();
  const [source, setSource] = useState("camera");
  const [busy, setBusy] = useState(false);

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
            <button className="btn-amber full" onClick={() => startPreview(source)}>
              {source === "screen" ? "Choose a screen to share" : "Turn on camera"}
            </button>
          </>
        )}

        {(state === "preview" || state === "recording") && (
          <>
            <div className="rec-stage">
              <video ref={previewRef} className="rec-video" playsInline />
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
