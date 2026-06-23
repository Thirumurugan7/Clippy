import { useEffect, useState, useCallback, useRef } from "react";
import { EditorPage } from "./EditorPage.jsx";
import { useAuth } from "./hooks/useAuth.js";
import { AuthScreen } from "./components/AuthScreen.jsx";

function StatusDot({ status }) {
  return <span className={`dot dot-${status}`} title={status} />;
}

export default function App() {
  const { user, login, register, logout } = useAuth();
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [videos, setVideos] = useState({});
  const [showJobs, setShowJobs] = useState(false);
  const fileInputRef = useRef(null);

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

  async function uploadFile(f) {
    if (!f) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (res.ok) {
        setCurrentVideoId(data.video_id);
        refreshJobs();
      }
    } finally {
      setUploading(false);
      setFile(null);
    }
  }

  const activeCount = jobs.filter((j) => j.status === "running" || j.status === "queued").length;

  if (user === undefined) return <div className="loading-shell mono">Loading…</div>;
  if (user === null) return <AuthScreen onLogin={login} onRegister={register} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/clippy-logo.png" alt="Clippy" className="brand-logo" />
          <span className="brand-tag">long video → shorts</span>
        </div>
        <div className="topbar-actions">
          <span className="user-email mono">{user.email}</span>
          <button
            className="btn-amber"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading…" : "Upload video"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            hidden
            onChange={(e) => uploadFile(e.target.files?.[0] || null)}
          />
          <div className="jobs-wrap">
            <button className="btn-ghost" onClick={() => setShowJobs((s) => !s)}>
              Activity{activeCount > 0 ? ` · ${activeCount}` : ""}
            </button>
            {showJobs && (
              <div className="jobs-pop">
                {jobs.length === 0 ? (
                  <p className="muted mono">No jobs yet.</p>
                ) : (
                  jobs.slice(0, 12).map((j) => {
                    const v = videos[j.video_id];
                    return (
                      <button
                        key={j.id}
                        className="job-row"
                        onClick={() => {
                          setCurrentVideoId(j.video_id);
                          setShowJobs(false);
                        }}
                      >
                        <StatusDot status={j.status} />
                        <span className="job-type">{j.type}</span>
                        <span className="job-name mono">
                          {v ? v.original_filename : j.video_id.slice(0, 8)}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>
          <button className="btn-ghost" onClick={() => { setCurrentVideoId(null); logout(); }}>
            Sign out
          </button>
        </div>
      </header>

      <main className="main">
        {currentVideoId ? (
          <EditorPage key={currentVideoId} videoId={currentVideoId} />
        ) : (
          <div className="welcome">
            <img src="/clippy-logo.png" alt="Clippy" className="welcome-logo" />
            <h1>Forge shorts from any long video</h1>
            <p>Upload a video. Clippy transcribes it, finds the strongest moments, and lets you edit by editing the transcript — all on your machine.</p>
            <button
              className="btn-amber lg"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? "Uploading…" : "Upload a video"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
