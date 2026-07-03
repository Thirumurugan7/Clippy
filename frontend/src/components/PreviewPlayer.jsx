import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react";
import { virtualToSource, sourceToVirtual } from "../edl.js";
import { drawCaptions, drawTextOverlays, cxAt } from "../captionLayout.js";
import { resolveCaptionStyle } from "../presets.js";
import { computeCrop, targetDims } from "../crop.js";

// Plays the original <video> but only the kept EDL segments. Two preview modes:
//   - Auto  : WYSIWYG composited result (aspect crop following the face + captions)
//   - Manual: the FULL source frame with a draggable crop box (image-style crop)
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
  const [src, setSrc] = useState(null); // {w,h} of the source video

  const aspect = settings?.aspect || "9:16";
  const manual = settings?.framing === "manual";
  const [tw, th] = targetDims(aspect);
  // Canvas pixel dims: source-shaped in manual (show whole frame), target-shaped otherwise.
  let baseW = tw, baseH = th;
  if (manual && src) { baseW = src.w; baseH = src.h; }
  const scale = 540 / Math.max(baseW, baseH);
  const cw = Math.round(baseW * scale);
  const ch = Math.round(baseH * scale);

  function findSegBySource(e, s) {
    for (let i = 0; i < e.length; i++) if (s >= e[i].sourceStart - 0.05 && s <= e[i].sourceEnd + 0.05) return i;
    return -1;
  }
  function onTimeUpdate() {
    const v = videoRef.current, e = edlRef.current;
    if (!v || !e || !e.length) return;
    const s = v.currentTime;
    let idx = idxRef.current;
    if (idx >= e.length) idx = e.length - 1;
    let seg = e[idx];
    if (!seg || s < seg.sourceStart - 0.1 || s > seg.sourceEnd + 0.1) {
      const f = findSegBySource(e, s);
      if (f >= 0) { idx = f; idxRef.current = idx; seg = e[idx]; }
    }
    if (seg && !v.paused && s >= seg.sourceEnd - 0.03) {
      const next = e[idx + 1];
      if (next) { idxRef.current = idx + 1; v.currentTime = next.sourceStart; } else v.pause();
      return;
    }
    const vt = sourceToVirtual(e, s);
    if (vt != null) onVirtualTime?.(vt);
  }

  useImperativeHandle(ref, () => ({
    seekVirtual(vt) {
      const v = videoRef.current, map = virtualToSource(edlRef.current, vt);
      if (map && v) { idxRef.current = map.segIndex; v.currentTime = map.source; onVirtualTime?.(vt); }
    },
    play() { videoRef.current?.play(); },
    pause() { videoRef.current?.pause(); },
    toggle() { const v = videoRef.current; if (v) v.paused ? v.play() : v.pause(); },
  }));

  useEffect(() => {
    const v = videoRef.current;
    if (!v || !edl?.length) return;
    if (sourceToVirtual(edl, v.currentTime) == null) {
      idxRef.current = 0; v.currentTime = edl[0].sourceStart; onVirtualTime?.(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edl]);

  // Canvas compositor.
  useEffect(() => {
    if (!vertical) return;
    let raf;
    const ctx = canvasRef.current?.getContext("2d");
    function frame() {
      const v = videoRef.current, canvas = canvasRef.current, st = settingsRef.current;
      if (v && canvas && ctx && v.videoWidth && st) {
        const vw = v.videoWidth, vh = v.videoHeight;
        const W = canvas.width, H = canvas.height;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, W, H);
        if (st.framing === "manual") {
          // full frame + crop-box overlay
          ctx.drawImage(v, 0, 0, vw, vh, 0, 0, W, H);
          const [sx, sy, scw, sch] = computeCrop(vw, vh, st.aspect, st.crop_cx, st.crop_cy ?? 0.5);
          const k = W / vw;
          const bx = sx * k, by = sy * k, bw = scw * k, bh = sch * k;
          ctx.fillStyle = "rgba(0,0,0,0.55)";
          ctx.fillRect(0, 0, W, by);
          ctx.fillRect(0, by + bh, W, H - by - bh);
          ctx.fillRect(0, by, bx, bh);
          ctx.fillRect(bx + bw, by, W - bx - bw, bh);
          ctx.strokeStyle = "#8b6cf6";
          ctx.lineWidth = 2;
          ctx.strokeRect(bx + 1, by + 1, bw - 2, bh - 2);
        } else {
          const cxn = reframe?.centers ? cxAt(reframe.centers, v.currentTime) : 0.5;
          const [sx, sy, scw, sch] = computeCrop(vw, vh, st.aspect, cxn, 0.5);
          ctx.drawImage(v, sx, sy, scw, sch, 0, 0, W, H);
          if (captionLines && captionLines.length) {
            const vt = sourceToVirtual(edlRef.current, v.currentTime);
            if (vt != null) {
              const base = resolveCaptionStyle(st.caption);
              const f = W / tw;
              drawCaptions(ctx, captionLines, vt, W, H, { ...base, fontsize: base.fontsize * f, outline_width: base.outline_width * f });
            }
          }
          // static text overlays (matches the export)
          drawTextOverlays(ctx, st.text_overlays, W, H);
          // progress bar overlay (matches the export)
          const pb = st.progress_bar;
          if (pb && pb.enabled) {
            const vt = sourceToVirtual(edlRef.current, v.currentTime);
            const dur = edlRef.current.reduce((a, s) => a + (s.sourceEnd - s.sourceStart), 0);
            if (vt != null && dur > 0) {
              const frac = Math.min(1, Math.max(0, vt / dur));
              const bh = Math.max(3, Math.round(H * 0.011));
              const by = pb.position === "top" ? 0 : H - bh;
              ctx.fillStyle = pb.color || "#8b6cf6";
              ctx.fillRect(0, by, W * frac, bh);
            }
          }
          // fade in/out transition (matches the export)
          if (st.transition && st.transition.fade) {
            const vt = sourceToVirtual(edlRef.current, v.currentTime);
            const dur = edlRef.current.reduce((a, s) => a + (s.sourceEnd - s.sourceStart), 0);
            if (vt != null && dur > 0.9) {
              const fd = 0.4;
              let a = 0;
              if (vt < fd) a = 1 - vt / fd;
              else if (vt > dur - fd) a = 1 - (dur - vt) / fd;
              a = Math.max(0, Math.min(1, a));
              if (a > 0.001) {
                ctx.fillStyle = `rgba(0,0,0,${a})`;
                ctx.fillRect(0, 0, W, H);
              }
            }
          }
        }
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [vertical, reframe, captionLines, tw, manual]);

  // Drag: in manual, 2D reposition of the crop box; otherwise click = play/pause.
  const drag = useRef(null);
  function onPointerDown(e) {
    drag.current = { x: e.clientX, y: e.clientY, cx: settings?.crop_cx ?? 0.5, cy: settings?.crop_cy ?? 0.5, moved: false };
  }
  function onPointerMove(e) {
    if (!drag.current || settings?.framing !== "manual") return;
    const rect = e.currentTarget.getBoundingClientRect();
    const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) drag.current.moved = true;
    const nx = Math.max(0, Math.min(1, drag.current.cx + dx / rect.width));
    const ny = Math.max(0, Math.min(1, drag.current.cy + dy / rect.height));
    onCropDrag?.(nx, ny);
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
        onLoadedMetadata={(e) => setSrc({ w: e.target.videoWidth, h: e.target.videoHeight })}
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        className={vertical ? "src-hidden" : "preview-video"}
        playsInline
      />
      {vertical && (
        <div className="vert-stage" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
          <canvas ref={canvasRef} width={cw} height={ch} className="vert-canvas" />
          {paused && !manual && <div className="play-overlay">▶</div>}
          {manual && <div className="crop-hint mono">drag to position the crop</div>}
        </div>
      )}
    </div>
  );
});
