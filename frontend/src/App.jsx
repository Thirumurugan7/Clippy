import { useEffect, useState, useCallback, useRef } from "react";

// M1: transcription + transcript synced to player.
// M2: transcript editing (mark words to delete), one-click filler detection,
//     and exporting the edited video (real ffmpeg cuts on the real timeline).

function formatBytes(n) {
  if (n == null) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function StatusBadge({ status }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

function TranscriptView({ videoId }) {
  const videoRef = useRef(null);
  const [transcript, setTranscript] = useState(null);
  const [activeIdx, setActiveIdx] = useState(-1);
  const wordRefs = useRef({});

  const [editMode, setEditMode] = useState(false);
  const [deleted, setDeleted] = useState(() => new Set());
  const [exportState, setExportState] = useState(null); // {status, result, jobId}

  useEffect(() => {
    let cancelled = false;
    setTranscript(null);
    setDeleted(new Set());
    setExportState(null);
    async function poll() {
      try {
        const res = await fetch(`/api/videos/${videoId}/transcript`);
        if (res.ok) {
          const data = await res.json();
          if (data.ready) {
            if (!cancelled) setTranscript(data);
            return;
          }
        }
      } catch (e) {
        /* retry */
      }
      if (!cancelled) setTimeout(poll, 2000);
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  function onTimeUpdate() {
    const v = videoRef.current;
    if (!v || !transcript) return;
    const t = v.currentTime;
    const words = transcript.words;
    let idx = -1;
    for (let i = 0; i < words.length; i++) {
      if (t >= words[i].start && t <= words[i].end) {
        idx = i;
        break;
      }
      if (words[i].start > t) break;
    }
    if (idx !== activeIdx) {
      setActiveIdx(idx);
      const el = wordRefs.current[idx];
      if (el) el.scrollIntoView({ block: "nearest" });
    }
  }

  function onWordClick(w) {
    if (editMode) {
      setDeleted((prev) => {
        const next = new Set(prev);
        next.has(w.i) ? next.delete(w.i) : next.add(w.i);
        return next;
      });
    } else {
      const v = videoRef.current;
      if (v) {
        v.currentTime = w.start;
        v.play();
      }
    }
  }

  async function detectFillers() {
    const res = await fetch(`/api/videos/${videoId}/fillers`);
    if (!res.ok) return;
    const data = await res.json();
    setEditMode(true);
    setDeleted((prev) => new Set([...prev, ...data.indices]));
  }

  function clearDeleted() {
    setDeleted(new Set());
  }

  async function doExport() {
    setExportState({ status: "queued", jobId: null, result: null });
    const res = await fetch(`/api/videos/${videoId}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delete_word_indices: [...deleted] }),
    });
    const { job_id } = await res.json();
    // poll the job
    async function pollJob() {
      const r = await fetch(`/api/jobs/${job_id}`);
      const job = await r.json();
      if (job.status === "done") {
        setExportState({
          status: "done",
          jobId: job_id,
          result: JSON.parse(job.result_json),
        });
        return;
      }
      if (job.status === "failed") {
        setExportState({ status: "failed", jobId: job_id, error: job.error });
        return;
      }
      setExportState((s) => ({ ...s, status: job.status, jobId: job_id }));
      setTimeout(pollJob, 1500);
    }
    pollJob();
  }

  const removedSeconds = transcript
    ? [...deleted].reduce((acc, i) => {
        const w = transcript.words[i];
        return acc + (w ? w.end - w.start : 0);
      }, 0)
    : 0;

  return (
    <div className="card">
      <h3>Player + transcript editor</h3>
      <video
        ref={videoRef}
        src={`/api/videos/${videoId}/file`}
        controls
        onTimeUpdate={onTimeUpdate}
        style={{ width: "100%", borderRadius: 8, background: "#000" }}
      />
      {!transcript ? (
        <p className="mono" style={{ marginTop: 12 }}>
          Transcribing… (faster-whisper running in the worker)
        </p>
      ) : (
        <>
          <p className="mono" style={{ marginTop: 12 }}>
            language={transcript.language} (p=
            {transcript.language_probability?.toFixed(2)}), {transcript.words.length} words
          </p>

          <div className="toolbar">
            <button
              className={editMode ? "btn-on" : ""}
              onClick={() => setEditMode((e) => !e)}
            >
              {editMode ? "Edit mode: ON" : "Edit mode: OFF"}
            </button>
            <button onClick={detectFillers}>Detect filler words</button>
            <button onClick={clearDeleted} disabled={deleted.size === 0}>
              Clear ({deleted.size})
            </button>
            <button
              className="btn-primary"
              onClick={doExport}
              disabled={deleted.size === 0 || (exportState && exportState.status !== "done" && exportState.status !== "failed")}
            >
              Export edited video (−{deleted.size} words, ~{removedSeconds.toFixed(1)}s)
            </button>
          </div>
          <p className="mono" style={{ marginTop: 4 }}>
            {editMode
              ? "Edit mode ON — click a word to mark/unmark it for deletion (strikethrough)."
              : "Edit mode OFF — click a word to seek the player."}
          </p>

          <div className="transcript">
            {transcript.words.map((w) => (
              <span
                key={w.i}
                ref={(el) => (wordRefs.current[w.i] = el)}
                className={
                  "word" +
                  (w.i === activeIdx ? " word-active" : "") +
                  (deleted.has(w.i) ? " word-deleted" : "")
                }
                title={`${w.start.toFixed(2)}s – ${w.end.toFixed(2)}s`}
                onClick={() => onWordClick(w)}
              >
                {w.word}
              </span>
            ))}
          </div>

          {exportState && (
            <div className="export-panel">
              {exportState.status === "failed" ? (
                <span className="error">Export failed: {exportState.error}</span>
              ) : exportState.status !== "done" ? (
                <p className="mono">Exporting… (status: {exportState.status})</p>
              ) : (
                <>
                  <p className="mono">
                    Exported: {exportState.result.original_duration}s →{" "}
                    <b>{exportState.result.output_duration}s</b> (
                    {exportState.result.num_words_deleted} words cut,{" "}
                    {exportState.result.num_kept_segments} segments joined)
                  </p>
                  <video
                    src={`/api/exports/${exportState.jobId}/file`}
                    controls
                    style={{ width: "100%", borderRadius: 8, background: "#000" }}
                  />
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [videos, setVideos] = useState({});
  const [message, setMessage] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState(null);

  const refreshJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs");
      const data = await res.json();
      setJobs(data.jobs || []);
      const ids = [...new Set((data.jobs || []).map((j) => j.video_id))];
      const entries = await Promise.all(
        ids.map(async (id) => {
          const r = await fetch(`/api/videos/${id}`);
          return [id, r.ok ? await r.json() : null];
        })
      );
      setVideos(Object.fromEntries(entries));
    } catch (e) {
      /* retry next tick */
    }
  }, []);

  useEffect(() => {
    refreshJobs();
    const t = setInterval(refreshJobs, 1500);
    return () => clearInterval(t);
  }, [refreshJobs]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setMessage(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) {
        setMessage({ kind: "error", text: data.detail || "upload failed" });
      } else {
        setMessage({
          kind: "ok",
          text: `Stored. video_id=${data.video_id} (${formatBytes(data.size_bytes)})`,
        });
        setCurrentVideoId(data.video_id);
        refreshJobs();
      }
    } catch (e) {
      setMessage({ kind: "error", text: String(e) });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <h1>ClipForge</h1>
      <p className="mono">M2 — transcript editing + filler removal + export</p>

      <div className="card">
        <h3>Upload a long video</h3>
        <input
          type="file"
          accept="video/*"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <div style={{ marginTop: 12 }}>
          <button onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </div>
        {message && (
          <p className={message.kind === "error" ? "error" : "mono"} style={{ marginTop: 12 }}>
            {message.text}
          </p>
        )}
      </div>

      {currentVideoId && <TranscriptView videoId={currentVideoId} />}

      <div className="card">
        <h3>Jobs</h3>
        {jobs.length === 0 ? (
          <p className="mono">No jobs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Type</th>
                <th>Video</th>
                <th>Result / Error</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const v = videos[j.video_id];
                return (
                  <tr
                    key={j.id}
                    onClick={() => setCurrentVideoId(j.video_id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.type}</td>
                    <td className="mono">
                      {v ? v.original_filename : j.video_id.slice(0, 8)}
                    </td>
                    <td>
                      {j.status === "failed" ? (
                        <span className="error">{j.error}</span>
                      ) : j.result_json ? (
                        <span className="mono">{j.result_json}</span>
                      ) : (
                        <span className="mono">…</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
