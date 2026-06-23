import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from "react";
import { virtualToSource, sourceToVirtual, segmentDuration } from "../edl.js";
import { drawCaptions, cxAt } from "../captionLayout.js";

const CANVAS_W = 540;
const CANVAS_H = 960; // 9:16 at half of 1080x1920
const SCALE = CANVAS_W / 1080; // caption metrics scale vs the exported short

// Plays the original <video> but only the kept segments, in EDL order. In
// `vertical` mode it composites a live 9:16 preview onto a canvas — the same
// face-track crop + karaoke captions the export will bake — so what you see
// before exporting is what you get.
export const PreviewPlayer = forwardRef(function PreviewPlayer(
  { videoId, edl, onVirtualTime, vertical, reframe, captionLines },
  ref
) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const edlRef = useRef(edl);
  edlRef.current = edl;
  const idxRef = useRef(0);
  const [paused, setPaused] = useState(true);

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

  // Canvas compositor loop for vertical mode.
  useEffect(() => {
    if (!vertical) return;
    let raf;
    const ctx = canvasRef.current?.getContext("2d");
    function frame() {
      const v = videoRef.current;
      const canvas = canvasRef.current;
      if (v && canvas && ctx && v.videoWidth) {
        const vw = v.videoWidth;
        const vh = v.videoHeight;
        const cropW = Math.round((vh * 9) / 16);
        const useW = Math.min(cropW, vw);
        const cx = (reframe?.centers ? cxAt(reframe.centers, v.currentTime) : 0.5) * vw;
        const sx = Math.min(Math.max(cx - useW / 2, 0), vw - useW);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        ctx.drawImage(v, sx, 0, useW, vh, 0, 0, CANVAS_W, CANVAS_H);
        if (captionLines && captionLines.length) {
          const vt = sourceToVirtual(edlRef.current, v.currentTime);
          if (vt != null) {
            drawCaptions(ctx, captionLines, vt, CANVAS_W, CANVAS_H, {
              fontsize: 58 * SCALE, marginV: 300 * SCALE,
            });
          }
        }
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [vertical, reframe, captionLines]);

  function toggle() {
    const v = videoRef.current;
    if (!v) return;
    v.paused ? v.play() : v.pause();
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
        <div className="vert-stage" onClick={toggle}>
          <canvas ref={canvasRef} width={CANVAS_W} height={CANVAS_H} className="vert-canvas" />
          {paused && <div className="play-overlay">▶</div>}
        </div>
      )}
    </div>
  );
});
