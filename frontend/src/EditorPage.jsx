import { useEffect, useRef, useState } from "react";
import { useEdl } from "./hooks/useEdl.js";
import { PreviewPlayer } from "./components/PreviewPlayer.jsx";
import { TranscriptPane } from "./components/TranscriptPane.jsx";
import { Timeline } from "./components/Timeline.jsx";
import { Toolbar } from "./components/Toolbar.jsx";

// The editor: preview (top), transcript (middle), timeline (bottom) — all driven
// by one EDL via useEdl. Loads transcript + waveform + duration for the video.
export function EditorPage({ videoId }) {
  const { edl, ops, undo, redo, canUndo, canRedo, saving } = useEdl(videoId);
  const [transcript, setTranscript] = useState(null);
  const [peaks, setPeaks] = useState(null);
  const [duration, setDuration] = useState(0);
  const [activeVirtual, setActiveVirtual] = useState(0);
  const [exportState, setExportState] = useState(null);
  const playerRef = useRef(null);

  // video metadata (original duration)
  useEffect(() => {
    fetch(`/api/videos/${videoId}`)
      .then((r) => r.json())
      .then((v) => setDuration(v.duration_seconds || 0));
  }, [videoId]);

  // poll transcript until ready
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
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  // poll waveform until ready
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
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  function seek(vt) {
    playerRef.current?.seekVirtual(vt);
  }

  function splitAtPlayhead() {
    ops.split(activeVirtual);
  }

  async function detectFillers() {
    const res = await fetch(`/api/videos/${videoId}/fillers`);
    if (!res.ok || !transcript) return;
    const { indices } = await res.json();
    // Delete each filler word's source span (composes via functional updates).
    for (const i of indices) {
      const w = transcript.words[i];
      if (w) ops.deleteSourceRange(w.start, w.end);
    }
  }

  async function doExport() {
    setExportState({ status: "saving", jobId: null, result: null });
    // Flush the current EDL before exporting so the worker renders the latest.
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

  if (!edl) return <div className="card mono">Loading editor…</div>;
  const exporting = exportState && !["done", "failed"].includes(exportState.status);

  return (
    <div className="editor">
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
        exporting={exporting}
      />

      <TranscriptPane
        transcript={transcript}
        edl={edl}
        activeVirtual={activeVirtual}
        onSeek={seek}
        onDeleteSourceRange={(a, b) => ops.deleteSourceRange(a, b)}
      />

      <Timeline
        edl={edl}
        peaks={peaks}
        originalDuration={duration}
        activeVirtual={activeVirtual}
        ops={ops}
        onSeek={seek}
      />

      {exportState && (
        <div className="export-panel">
          {exportState.status === "failed" ? (
            <span className="error">Export failed: {exportState.error}</span>
          ) : exportState.status !== "done" ? (
            <p className="mono">Exporting… ({exportState.status})</p>
          ) : (
            <>
              <p className="mono">
                Exported: {exportState.result.original_duration}s →{" "}
                <b>{exportState.result.output_duration}s</b> (
                {exportState.result.num_segments} segments)
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
    </div>
  );
}
