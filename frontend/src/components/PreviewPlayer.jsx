import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { virtualToSource, sourceToVirtual, segmentDuration } from "../edl.js";

// Plays the original <video> but only the kept segments, in EDL order. The
// timeline/transcript drive it via seekVirtual(virtualTime); during playback it
// jumps across segment boundaries (handles reorder: source time is non-monotonic
// but each kept source time maps to exactly one segment).
export const PreviewPlayer = forwardRef(function PreviewPlayer(
  { videoId, edl, onVirtualTime },
  ref
) {
  const videoRef = useRef(null);
  const edlRef = useRef(edl);
  edlRef.current = edl;
  const idxRef = useRef(0); // current segment index in EDL order

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

    // If we've drifted outside the tracked segment (e.g. native scrub), re-derive.
    if (!seg || src < seg.sourceStart - 0.1 || src > seg.sourceEnd + 0.1) {
      const found = findSegBySource(e, src);
      if (found >= 0) {
        idx = found;
        idxRef.current = idx;
        seg = e[idx];
      }
    }

    // Advance across the join when the current segment ends during playback.
    if (seg && !v.paused && src >= seg.sourceEnd - 0.03) {
      const next = e[idx + 1];
      if (next) {
        idxRef.current = idx + 1;
        v.currentTime = next.sourceStart;
      } else {
        v.pause();
      }
      return;
    }

    const vt = sourceToVirtual(e, src);
    if (vt != null) onVirtualTime?.(vt);
  }

  useImperativeHandle(ref, () => ({
    seekVirtual(vt) {
      const v = videoRef.current;
      const map = virtualToSource(edlRef.current, vt);
      if (map && v) {
        idxRef.current = map.segIndex;
        v.currentTime = map.source;
        onVirtualTime?.(vt);
      }
    },
    play() {
      videoRef.current?.play();
    },
    pause() {
      videoRef.current?.pause();
    },
  }));

  // If an edit removes the segment we're parked on, snap to the start of the edit.
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

  return (
    <video
      ref={videoRef}
      src={`/api/videos/${videoId}/file`}
      controls
      onTimeUpdate={onTimeUpdate}
      className="preview-video"
    />
  );
});
