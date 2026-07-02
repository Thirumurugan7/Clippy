import { useEffect, useState, useCallback, useRef } from "react";
import { EditorPage } from "./EditorPage.jsx";
import { useAuth } from "./hooks/useAuth.js";
import { AuthScreen } from "./components/AuthScreen.jsx";
import { RecorderModal } from "./components/RecorderModal.jsx";
import { Icon } from "./components/Icon.jsx";
import { TEMPLATES } from "./templates.js";

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
  const [showRecorder, setShowRecorder] = useState(false);
  const [template, setTemplate] = useState(null); // use-case template selected on home
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

  // Apply a use-case template to a freshly uploaded video: merge its settings
  // over the defaults and stash a starter AI prompt the editor will pre-fill.
  async function applyTemplate(videoId, tpl) {
    if (!tpl) return;
    try {
      const cur = await (await fetch(`/api/videos/${videoId}/settings`)).json();
      const merged = {
        ...cur,
        ...tpl.settings,
        caption: { ...cur.caption, ...(tpl.settings.caption || {}) },
      };
      await fetch(`/api/videos/${videoId}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(merged),
      });
      if (tpl.prompt) sessionStorage.setItem(`clippy_prompt_${videoId}`, tpl.prompt);
    } catch {
      /* non-fatal — editor still opens with defaults */
    }
  }

  async function uploadFile(f) {
    if (!f) return;
    setUploading(true);
    const tpl = template;
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (res.ok) {
        await applyTemplate(data.video_id, tpl);
        setTemplate(null);
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
          <span className="brand-name">Clippy</span>
          <span className="brand-tag">long video → shorts</span>
        </div>
        <div className="topbar-actions">
          <span className="user-email mono">{user.email}</span>
          <button className="btn-ghost btn-icon" onClick={() => setShowRecorder(true)}>
            <Icon name="record" size={13} className="ico-rec" /> Record
          </button>
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
            <h1>Turn one long video into a week of shorts</h1>
            <p>Upload a video. Clippy transcribes it, finds the strongest moments, and lets you edit by editing the transcript — all on your machine.</p>
            <div className="welcome-actions">
              <button
                className="btn-amber lg"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? "Uploading…" : template ? `Upload for ${template.title}` : "Upload a video"}
              </button>
              <button className="btn-ghost lg btn-icon" onClick={() => setShowRecorder(true)}>
                <Icon name="record" size={14} className="ico-rec" /> Record instead
              </button>
            </div>

            <div className="tpl-block">
              <p className="tpl-eyebrow">…or start with an outcome</p>
              <div className="tpl-grid">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    className={"tpl-card" + (template?.id === t.id ? " on" : "")}
                    onClick={() => setTemplate((cur) => (cur?.id === t.id ? null : t))}
                    disabled={uploading}
                  >
                    <span className="tpl-icon"><Icon name={t.icon} size={22} /></span>
                    <span className="tpl-title">{t.title}</span>
                    <span className="tpl-desc">{t.desc}</span>
                  </button>
                ))}
              </div>
              <p className="tpl-foot mono">
                {template
                  ? `Selected — sets ${template.settings.aspect}, ${template.settings.caption.preset} captions + a starter prompt. Now upload or record.`
                  : "Picks aspect, captions, audio + a starter AI prompt — then you upload."}
              </p>
            </div>
          </div>
        )}
      </main>

      {showRecorder && (
        <RecorderModal onClose={() => setShowRecorder(false)} onUse={uploadFile} />
      )}
    </div>
  );
}
