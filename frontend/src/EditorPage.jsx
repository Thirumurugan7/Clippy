import { useEffect, useRef, useState, useMemo } from "react";
import { useEdl } from "./hooks/useEdl.js";
import { useSettings } from "./hooks/useSettings.js";
import { newId, sourceToVirtual, projectWords } from "./edl.js";
import { groupLines } from "./captionLayout.js";
import { PreviewPlayer } from "./components/PreviewPlayer.jsx";
import { TranscriptPane } from "./components/TranscriptPane.jsx";
import { Timeline } from "./components/Timeline.jsx";
import { Toolbar } from "./components/Toolbar.jsx";
import { Sidebar } from "./components/Sidebar.jsx";
import { HighlightsRail } from "./components/HighlightsRail.jsx";
import { CaptionsPanel } from "./components/CaptionsPanel.jsx";
import { CropPanel } from "./components/CropPanel.jsx";
import { AiEditPanel } from "./components/AiEditPanel.jsx";

export function EditorPage({ videoId }) {
  const [duration, setDuration] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setDuration(0);
    (function poll() {
      fetch(`/api/videos/${videoId}`)
        .then((r) => r.json())
        .then((v) => {
          if (cancelled) return;
          if (v.duration_seconds > 0) setDuration(v.duration_seconds);
          else setTimeout(poll, 1000);
        })
        .catch(() => !cancelled && setTimeout(poll, 1000));
    })();
    return () => { cancelled = true; };
  }, [videoId]);

  if (!duration) return <div className="loading-shell mono">Analyzing video…</div>;
  return <EditorInner videoId={videoId} duration={duration} />;
}

const TABS = [
  { id: "ai", label: "AI edit", icon: "🪄" },
  { id: "highlights", label: "Highlights", icon: "✨" },
  { id: "captions", label: "Captions", icon: "💬" },
  { id: "crop", label: "Crop", icon: "⬚" },
];

function EditorInner({ videoId, duration }) {
  const { edl, ops, undo, redo, canUndo, canRedo, saving, saveError } = useEdl(videoId);
  const { settings, setSettings } = useSettings(videoId);
  const [transcript, setTranscript] = useState(null);
  const [txProgress, setTxProgress] = useState({ progress: 0, status: "queued" });
  const [peaks, setPeaks] = useState(null);
  const [activeVirtual, setActiveVirtual] = useState(0);
  const [exportState, setExportState] = useState(null);
  const [activeClip, setActiveClip] = useState(null);
  const [vmode, setVmode] = useState(true);
  const [reframe, setReframe] = useState(null);
  const [tab, setTab] = useState("ai");
  const [collapsed, setCollapsed] = useState(false);
  const playerRef = useRef(null);

  const captionLines = useMemo(() => {
    if (!transcript || !edl) return [];
    return groupLines(projectWords(edl, transcript.words));
  }, [transcript, edl]);

  useEffect(() => {
    let c = false;
    fetch(`/api/videos/${videoId}/reframe`, { method: "POST" });
    (function poll() {
      fetch(`/api/videos/${videoId}/reframe`).then((r) => r.json()).then((d) => {
        if (c) return;
        d.ready ? setReframe(d) : setTimeout(poll, 2500);
      }).catch(() => !c && setTimeout(poll, 2500));
    })();
    return () => { c = true; };
  }, [videoId]);

  useEffect(() => {
    let c = false;
    setTranscript(null);
    (function poll() {
      fetch(`/api/videos/${videoId}/transcript`).then((r) => (r.ok ? r.json() : { ready: false })).then((d) => {
        if (c) return;
        if (d.ready) setTranscript(d);
        else { setTxProgress({ progress: d.progress || 0, status: d.status || "queued" }); setTimeout(poll, 1500); }
      }).catch(() => !c && setTimeout(poll, 2000));
    })();
    return () => { c = true; };
  }, [videoId]);

  useEffect(() => {
    let c = false;
    (function poll() {
      fetch(`/api/videos/${videoId}/waveform`).then((r) => (r.ok ? r.json() : null)).then((d) => {
        if (c) return;
        d && d.peaks ? setPeaks(d.peaks) : setTimeout(poll, 2000);
      }).catch(() => !c && setTimeout(poll, 2000));
    })();
    return () => { c = true; };
  }, [videoId]);

  const seek = (vt) => playerRef.current?.seekVirtual(vt);
  const splitAtPlayhead = () => ops.split(activeVirtual);

  async function detectFillers() {
    const res = await fetch(`/api/videos/${videoId}/fillers`);
    if (!res.ok || !transcript) return;
    const { indices } = await res.json();
    for (const i of indices) {
      const w = transcript.words[i];
      if (w) ops.deleteSourceRange(w.start, w.end);
    }
  }

  function onPreviewClip(c) {
    const vt = sourceToVirtual(edl, c.start);
    if (vt != null) seek(vt);
    else onUseClip(c);
  }
  function onUseClip(c) {
    ops.setAll([{ id: newId(), sourceStart: c.start, sourceEnd: c.end }]);
    setActiveClip({ start: c.start, end: c.end });
    setTimeout(() => seek(0), 0);
  }
  function onApplyAiEdit(p) {
    ops.setAll([{ id: newId(), sourceStart: p.clip.start, sourceEnd: p.clip.end }]);
    setActiveClip({ start: p.clip.start, end: p.clip.end });
    setSettings({ aspect: p.aspect, caption: { preset: p.caption_preset } });
    setTimeout(() => seek(0), 0);
  }

  async function runExport(kind) {
    setExportState({ status: "saving", kind, jobId: null, result: null });
    await fetch(`/api/videos/${videoId}/edit`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments: edl }),
    });
    const path = kind === "v" ? "export_vertical" : "export";
    const res = await fetch(`/api/videos/${videoId}/${path}`, { method: "POST" });
    const { job_id } = await res.json();
    (function pollJob() {
      fetch(`/api/jobs/${job_id}`).then((r) => r.json()).then((job) => {
        if (job.status === "done") setExportState({ status: "done", kind, jobId: job_id, result: JSON.parse(job.result_json) });
        else if (job.status === "failed") setExportState({ status: "failed", kind, jobId: job_id, error: job.error });
        else { setExportState({ status: job.status, kind, jobId: job_id, result: null }); setTimeout(pollJob, 1500); }
      });
    })();
  }
  const doExport = () => runExport("h");
  const doExportVertical = () => runExport("v");

  if (!edl || !settings) return <div className="loading-shell mono">Loading editor…</div>;
  const exporting = exportState && !["done", "failed"].includes(exportState.status);

  return (
    <div className="editor">
      <div className="workspace">
        <section className="stage">
          <div className="preview-head">
            <div className="seg-toggle">
              <button className={vmode ? "on" : ""} onClick={() => setVmode(true)}>Edited</button>
              <button className={!vmode ? "on" : ""} onClick={() => setVmode(false)}>Source</button>
            </div>
            {vmode && (
              <span className="preview-note mono">
                {settings.aspect} · {settings.framing === "manual" ? "manual crop" : reframe ? (reframe.tracked ? "face-tracked" : "center crop") : "analyzing…"} · {settings.caption.preset}
              </span>
            )}
          </div>
          <div className={"preview-pane" + (vmode ? " is-vertical" : "")}>
            <PreviewPlayer
              ref={playerRef}
              videoId={videoId}
              edl={edl}
              onVirtualTime={setActiveVirtual}
              vertical={vmode}
              reframe={reframe}
              captionLines={captionLines}
              settings={settings}
              onCropDrag={(cx, cy) => setSettings({ crop_cx: cx, crop_cy: cy, framing: "manual" })}
            />
          </div>

          <Toolbar
            onSplit={splitAtPlayhead} onDetectFillers={detectFillers}
            onExport={doExport} onExportVertical={doExportVertical}
            undo={undo} redo={redo} canUndo={canUndo} canRedo={canRedo}
            saving={saving} saveError={saveError} exporting={exporting}
          />

          <TranscriptPane
            transcript={transcript} edl={edl} activeVirtual={activeVirtual}
            txProgress={txProgress}
            onSeek={seek} onDeleteSourceRange={(a, b) => ops.deleteSourceRange(a, b)}
          />

          {exportState && (
            <div className="export-panel">
              {exportState.status === "failed" ? (
                <span className="error">Export failed: {exportState.error}</span>
              ) : exportState.status !== "done" ? (
                <p className="mono">{exportState.kind === "v" ? "Rendering vertical short — face track + captions…" : "Rendering your clip…"} ({exportState.status})</p>
              ) : exportState.kind === "v" ? (
                <>
                  <p className="mono">
                    {exportState.result.aspect || "9:16"} · {exportState.result.width}×{exportState.result.height} · {exportState.result.duration}s · {exportState.result.face_tracked ? "face-tracked" : "center crop"}
                  </p>
                  <video src={`/api/exports/${exportState.jobId}/file`} controls className="vertical-result" />
                </>
              ) : (
                <>
                  <p className="mono">Exported {exportState.result.original_duration}s → <b>{exportState.result.output_duration}s</b> · {exportState.result.num_segments} segment(s)</p>
                  <video src={`/api/exports/${exportState.jobId}/file`} controls className="preview-video" />
                </>
              )}
            </div>
          )}
        </section>

        <Sidebar tabs={TABS} active={tab} onSelect={setTab} collapsed={collapsed} onToggle={() => setCollapsed((s) => !s)}>
          {tab === "ai" && <AiEditPanel videoId={videoId} onApply={onApplyAiEdit} />}
          {tab === "highlights" && <HighlightsRail videoId={videoId} onUseClip={onUseClip} onPreviewClip={onPreviewClip} activeClip={activeClip} />}
          {tab === "captions" && <CaptionsPanel settings={settings} setSettings={setSettings} />}
          {tab === "crop" && <CropPanel settings={settings} setSettings={setSettings} />}
        </Sidebar>
      </div>

      <Timeline edl={edl} peaks={peaks} originalDuration={duration} activeVirtual={activeVirtual} ops={ops} onSeek={seek} />
    </div>
  );
}
