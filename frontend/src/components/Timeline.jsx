import { useRef } from "react";
import { totalDuration, segmentDuration } from "../edl.js";

// Visual timeline: each EDL segment is a clip block (width ∝ duration) with a
// waveform slice, left/right trim handles, a delete button, and HTML5
// drag-to-reorder. A playhead line tracks the preview. Clicking a clip seeks.
function fmtClock(t) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Pick a "nice" tick spacing so the ruler shows roughly 5–8 labels.
function tickStep(total) {
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
  return steps.find((s) => total / s <= 7) || 900;
}

export function Timeline({ edl, peaks, originalDuration, activeVirtual, ops, onSeek }) {
  const dragFrom = useRef(null);
  const rulerRef = useRef(null);
  const total = totalDuration(edl) || 1;

  // virtual start time of each segment (prefix sum), for click-to-seek.
  const prefix = [];
  let acc = 0;
  for (const s of edl) {
    prefix.push(acc);
    acc += segmentDuration(s);
  }

  // Ruler ticks across the virtual timeline.
  const step = tickStep(total);
  const ticks = [];
  for (let t = 0; t <= total + 1e-6; t += step) ticks.push(t);

  function scrub(e) {
    const rect = rulerRef.current.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onSeek(frac * total);
  }
  function startScrub(e) {
    scrub(e);
    const move = (ev) => scrub(ev);
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function WaveformCanvas({ seg }) {
    function draw(c) {
      if (!c || !peaks || !peaks.length || !originalDuration) return;
      const ctx = c.getContext("2d");
      const w = c.width;
      const h = c.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "rgba(255,255,255,0.55)";
      const i0 = Math.floor((seg.sourceStart / originalDuration) * peaks.length);
      const i1 = Math.ceil((seg.sourceEnd / originalDuration) * peaks.length);
      const span = Math.max(1, i1 - i0);
      for (let x = 0; x < w; x++) {
        const p = peaks[i0 + Math.floor((x / w) * span)] || 0;
        const bar = Math.max(1, p * h);
        ctx.fillRect(x, (h - bar) / 2, 1, bar);
      }
    }
    return <canvas ref={draw} width={320} height={56} className="wave" />;
  }

  function startTrim(e, seg, edge) {
    e.preventDefault();
    e.stopPropagation();
    const clipEl = e.currentTarget.parentElement;
    const widthPx = clipEl.getBoundingClientRect().width;
    const secPerPx = segmentDuration(seg) / widthPx;
    const startX = e.clientX;
    const base = edge === "start" ? seg.sourceStart : seg.sourceEnd;
    function move(ev) {
      ops.trim(seg.id, edge, base + (ev.clientX - startX) * secPerPx);
    }
    function up() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function onClipClick(e, i, seg) {
    // seek to the virtual time under the cursor within this clip
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    onSeek(prefix[i] + frac * segmentDuration(seg));
  }

  return (
    <div className="timeline">
      <div className="timeline-ruler" ref={rulerRef} onPointerDown={startScrub}>
        {ticks.map((t, k) => (
          <span key={k} className="tl-tick" style={{ left: `${(t / total) * 100}%` }}>
            <span className="tl-tick-label mono">{fmtClock(t)}</span>
          </span>
        ))}
        <span className="tl-scrub-head" style={{ left: `${(activeVirtual / total) * 100}%` }} />
      </div>
      <div className="timeline-track">
        {edl.map((seg, i) => {
          const frac = segmentDuration(seg) / total;
          const isActive = activeVirtual >= prefix[i] && activeVirtual < prefix[i] + segmentDuration(seg);
          return (
            <div
              key={seg.id}
              className={"clip" + (isActive ? " clip-active" : "")}
              style={{ flex: `${frac} 1 0` }}
              draggable
              onDragStart={() => (dragFrom.current = i)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                if (dragFrom.current != null) ops.reorder(dragFrom.current, i);
                dragFrom.current = null;
              }}
              onClick={(e) => onClipClick(e, i, seg)}
            >
              <div
                className="handle l"
                onPointerDown={(e) => startTrim(e, seg, "start")}
              />
              <WaveformCanvas seg={seg} />
              <span className="clip-time mono">{segmentDuration(seg).toFixed(1)}s</span>
              <button
                className="clip-del"
                title="Delete segment"
                onClick={(e) => {
                  e.stopPropagation();
                  ops.del(seg.id);
                }}
              >
                ✕
              </button>
              <div
                className="handle r"
                onPointerDown={(e) => startTrim(e, seg, "end")}
              />
            </div>
          );
        })}
        <div
          className="playhead"
          style={{ left: `${(activeVirtual / total) * 100}%` }}
        />
      </div>
    </div>
  );
}
