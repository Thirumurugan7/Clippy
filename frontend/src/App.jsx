import { useEffect, useState, useCallback } from "react";
import { EditorPage } from "./EditorPage.jsx";

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

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [videos, setVideos] = useState({});
  const [message, setMessage] = useState(null);
  // Keep the open video in the URL (?v=...) so a reload stays in the editor.
  const [currentVideoId, setCurrentVideoIdState] = useState(
    () => new URLSearchParams(window.location.search).get("v")
  );
  const setCurrentVideoId = useCallback((id) => {
    setCurrentVideoIdState(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("v", id);
    else url.searchParams.delete("v");
    window.history.replaceState({}, "", url);
  }, []);

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
    const t = setInterval(refreshJobs, 2000);
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
          text: `Stored ${data.video_id} (${formatBytes(data.size_bytes)})`,
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
    <div className="app">
      <header className="topbar">
        <h1>ClipForge</h1>
        <div className="uploader">
          <input
            type="file"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? "Uploading…" : "Upload"}
          </button>
          {message && (
            <span className={message.kind === "error" ? "error" : "mono"}>
              {message.text}
            </span>
          )}
        </div>
      </header>

      {currentVideoId ? (
        <EditorPage key={currentVideoId} videoId={currentVideoId} />
      ) : (
        <div className="card mono">Upload a video to start editing.</div>
      )}

      <details className="jobs-drawer">
        <summary>Jobs ({jobs.length})</summary>
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Type</th>
              <th>Video</th>
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
                  <td className="mono">{v ? v.original_filename : j.video_id.slice(0, 8)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </div>
  );
}
