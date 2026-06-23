import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react";
import { virtualToSource, sourceToVirtual, segmentDuration } from "../edl.js";
import { drawCaptions, cxAt } from "../captionLayout.js";
import { resolveCaptionStyle } from "../presets.js";
import { computeCrop, targetDims } from "../crop.js";

// Plays the original <video> but only the kept segments, in EDL order. In
// `vertical` mode it composites a live preview onto a canvas — the same
// aspect crop (face-track or manual) + caption preset the export will bake.
export const PreviewPlayer = forwardRef(function PreviewPlayer(
  { videoId, edl, onVirtualTime, vertical, reframe, captionLines, settings, onCropDrag },
  ref
) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const edlRef = useRef(edl);
  edlRef.current = edl;
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const idxRef = useRef(0);
  const [paused, setPaused] = useState(true);

  const aspect = settings?.aspect || "9:16";
  const [tw, th] = targetDims(aspect);
  const scale = 540 / Math.max(tw, th);
  const cw = Math.round(tw * scale);
  const ch = Math.round(th * scale);

  function findSegBySource(e, src) {
    for (let i = 0; i < e.length; i++) {
      if (src >= e[i].sourceStart - 0.05 && src <= e[i].sourceEnd + 0.05) return i;
    }
    return -1;
  }

  function onTimeUpdate() {
    const v = videoRef.current;
    const e = edlRef.current;
    if (!v || !e || !e.length) return;
    const src = v.currentTime;
    let idx = idxRef.current;
    if (idx >= e.length) idx = e.length - 1;
    let seg = e[idx];
    if (!seg || src < seg.sourceStart - 0.1 || src > seg.sourceEnd + 0.1) {
      const found = findSegBySource(e, src);
      if (found >= 0) { idx = found; idxRef.current = idx; seg = e[idx]; }
    }
    if (seg && !v.paused && src >= seg.sourceEnd - 0.03) {
      const next = e[idx + 1];
      if (next) { idxRef.current = idx + 1; v.currentTime = next.sourceStart; }
      else v.pause();
      return;
    }
    const vt = sourceToVirtual(e, src);
    if (vt != null) onVirtualTime?.(vt);
  }

  useImperativeHandle(ref, () => ({
    seekVirtual(vt) {
      const v = videoRef.current;
      const map = virtualToSource(edlRef.current, vt);
      if (map && v) { idxRef.current = map.segIndex; v.currentTime = map.source; onVirtualTime?.(vt); }
    },
    play() { videoRef.current?.play(); },
    pause() { videoRef.current?.pause(); },
  }));

  useEffect(() => {
    const v = videoRef.current;
    if (!v || !edl?.length) return;
    if (sourceToVirtual(edl, v.currentTime) == null) {
      idxRef.current = 0;
      v.currentTime = edl[0].sourceStart;
      onVirtualTime?.(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edl]);

  // Canvas compositor loop.
  useEffect(() => {
    if (!vertical) return;
    let raf;
    const ctx = canvasRef.current?.getContext("2d");
    function frame() {
      const v = videoRef.current;
      const canvas = canvasRef.current;
      const st = settingsRef.current;
      if (v && canvas && ctx && v.videoWidth && st) {
        const vw = v.videoWidth, vh = v.videoHeight;
        const asp = st.aspect;
        const cxNorm = st.framing === "manual"
          ? st.crop_cx
          : (reframe?.centers ? cxAt(reframe.centers, v.currentTime) : 0.5);
        const [sx, sy, scw, sch] = computeCrop(vw, vh, asp, cxNorm);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(v, sx, sy, scw, sch, 0, 0, canvas.width, canvas.height);
        if (captionLines && captionLines.length) {
          const vt = sourceToVirtual(edlRef.current, v.currentTime);
          if (vt != null) {
            const base = resolveCaptionStyle(st.caption);
            const s = { ...base, fontsize: base.fontsize * (canvas.width / tw), outline_width: base.outline_width * (canvas.width / tw) };
            drawCaptions(ctx, captionLines, vt, canvas.width, canvas.height, s);
          }
        }
        if (st.framing === "manual") {
          ctx.strokeStyle = "rgba(255,138,61,0.9)";
          ctx.lineWidth = 2;
          ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
        }
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [vertical, reframe, captionLines, tw]);

  // pointer: drag to pan (manual framing); click to play/pause.
  const drag = useRef(null);
  function onPointerDown(e) {
    drag.current = { x: e.clientX, cx: settings?.crop_cx ?? 0.5, moved: false };
  }
  function onPointerMove(e) {
    if (!drag.current || settings?.framing !== "manual") return;
    const dx = e.clientX - drag.current.x;
    if (Math.abs(dx) > 2) drag.current.moved = true;
    const next = Math.max(0, Math.min(1, drag.current.cx - dx / cw));
    onCropDrag?.(next);
  }
  function onPointerUp() {
    const v = videoRef.current;
    if (drag.current && !drag.current.moved && v) v.paused ? v.play() : v.pause();
    drag.current = null;
  }

  return (
    <div className={"player-wrap" + (vertical ? " vert" : "")}>
      <video
        ref={videoRef}
        src={`/api/videos/${videoId}/file`}
        controls={!vertical}
        onTimeUpdate={onTimeUpdate}
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        className={vertical ? "src-hidden" : "preview-video"}
        playsInline
      />
      {vertical && (
        <div
          className="vert-stage"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <canvas ref={canvasRef} width={cw} height={ch} className="vert-canvas" />
          {paused && <div className="play-overlay">▶</div>}
        </div>
      )}
    </div>
  );
});
