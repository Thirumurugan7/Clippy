import { useEffect, useRef, useState } from "react";
import { useEdl } from "./hooks/useEdl.js";
import { newId, sourceToVirtual } from "./edl.js";
import { PreviewPlayer } from "./components/PreviewPlayer.jsx";
import { TranscriptPane } from "./components/TranscriptPane.jsx";
import { Timeline } from "./components/Timeline.jsx";
import { Toolbar } from "./components/Toolbar.jsx";
import { HighlightsRail } from "./components/HighlightsRail.jsx";

// Gate the editor until probe has set the real duration — otherwise the default
// EDL would be a degenerate [0,0] segment that projects zero words.
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
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  if (!duration) return <div className="loading-shell mono">Analyzing video…</div>;
  return <EditorInner videoId={videoId} duration={duration} />;
}

function EditorInner({ videoId, duration }) {
  const { edl, ops, undo, redo, canUndo, canRedo, saving, saveError } = useEdl(videoId);
  const [transcript, setTranscript] = useState(null);
  const [peaks, setPeaks] = useState(null);
  const [activeVirtual, setActiveVirtual] = useState(0);
  const [exportState, setExportState] = useState(null);
  const [activeClip, setActiveClip] = useState(null);
  const playerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setTranscript(null);
    (function poll() {
      fetch(`/api/videos/${videoId}/transcript`)
        .then((r) => (r.ok ? r.json() : { ready: false }))
        .then((d) => {
          if (cancelled) return;
          if (d.ready) setTranscript(d);
          else setTimeout(poll, 2000);
        })
        .catch(() => !cancelled && setTimeout(poll, 2000));
    })();
    return () => { cancelled = true; };
  }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    setPeaks(null);
    (function poll() {
      fetch(`/api/videos/${videoId}/waveform`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (cancelled) return;
          if (d && d.peaks) setPeaks(d.peaks);
          else setTimeout(poll, 2000);
        })
        .catch(() => !cancelled && setTimeout(poll, 2000));
    })();
    return () => { cancelled = true; };
  }, [videoId]);

  const seek = (vt) => playerRef.current?.seekVirtual(vt);

  function splitAtPlayhead() {
    ops.split(activeVirtual);
  }

  async function detectFillers() {
    const res = await fetch(`/api/videos/${videoId}/fillers`);
    if (!res.ok || !transcript) return;
    const { indices } = await res.json();
    for (const i of indices) {
      const w = transcript.words[i];
      if (w) ops.deleteSourceRange(w.start, w.end);
    }
  }

  // Highlights: previewing seeks within the current edit; "Use clip" replaces the
  // working edit with just that range so the creator can trim and export a short.
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

  async function doExport() {
    setExportState({ status: "saving", jobId: null, result: null });
    await fetch(`/api/videos/${videoId}/edit`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments: edl }),
    });
    const res = await fetch(`/api/videos/${videoId}/export`, { method: "POST" });
    const { job_id } = await res.json();
    (function pollJob() {
      fetch(`/api/jobs/${job_id}`)
        .then((r) => r.json())
        .then((job) => {
          if (job.status === "done") {
            setExportState({ status: "done", jobId: job_id, result: JSON.parse(job.result_json) });
          } else if (job.status === "failed") {
            setExportState({ status: "failed", jobId: job_id, error: job.error });
          } else {
            setExportState({ status: job.status, jobId: job_id, result: null });
            setTimeout(pollJob, 1500);
          }
        });
    })();
  }

  if (!edl) return <div className="loading-shell mono">Loading editor…</div>;
  const exporting = exportState && !["done", "failed"].includes(exportState.status);

  return (
    <div className="editor">
      <div className="workspace">
        <section className="stage">
          <div className="preview-pane">
            <PreviewPlayer
              ref={playerRef}
              videoId={videoId}
              edl={edl}
              onVirtualTime={setActiveVirtual}
            />
          </div>

          <Toolbar
            onSplit={splitAtPlayhead}
            onDetectFillers={detectFillers}
            onExport={doExport}
            undo={undo}
            redo={redo}
            canUndo={canUndo}
            canRedo={canRedo}
            saving={saving}
            saveError={saveError}
            exporting={exporting}
          />

          <TranscriptPane
            transcript={transcript}
            edl={edl}
            activeVirtual={activeVirtual}
            onSeek={seek}
            onDeleteSourceRange={(a, b) => ops.deleteSourceRange(a, b)}
          />

          {exportState && (
            <div className="export-panel">
              {exportState.status === "failed" ? (
                <span className="error">Export failed: {exportState.error}</span>
              ) : exportState.status !== "done" ? (
                <p className="mono">Rendering your clip… ({exportState.status})</p>
              ) : (
                <>
                  <p className="mono">
                    Exported {exportState.result.original_duration}s →{" "}
                    <b>{exportState.result.output_duration}s</b> ·{" "}
                    {exportState.result.num_segments} segment(s)
                  </p>
                  <video
                    src={`/api/exports/${exportState.jobId}/file`}
                    controls
                    className="preview-video"
                  />
                </>
              )}
            </div>
          )}
        </section>

        <HighlightsRail
          videoId={videoId}
          onUseClip={onUseClip}
          onPreviewClip={onPreviewClip}
          activeClip={activeClip}
        />
      </div>

      <Timeline
        edl={edl}
        peaks={peaks}
        originalDuration={duration}
        activeVirtual={activeVirtual}
        ops={ops}
        onSeek={seek}
      />
    </div>
  );
}
