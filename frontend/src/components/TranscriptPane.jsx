import { useMemo, useState } from "react";
import { projectWords } from "../edl.js";

// Renders the transcript as a pure projection of the EDL (so it always matches
// the timeline order). Click a word = seek the preview. Drag across words then
// press Delete/Backspace = cut that source range from the EDL.
export function TranscriptPane({ transcript, edl, activeVirtual, onSeek, onDeleteSourceRange }) {
  const words = useMemo(
    () => (transcript && edl ? projectWords(edl, transcript.words) : []),
    [transcript, edl]
  );
  const [sel, setSel] = useState(null); // {a,b} indices into `words`
  const [dragging, setDragging] = useState(false);

  function isActive(w) {
    return activeVirtual >= w.virtualStart && activeVirtual <= w.virtualEnd;
  }
  function inSel(idx) {
    if (!sel) return false;
    const lo = Math.min(sel.a, sel.b);
    const hi = Math.max(sel.a, sel.b);
    return idx >= lo && idx <= hi;
  }
  function onKeyDown(e) {
    if ((e.key === "Delete" || e.key === "Backspace") && sel) {
      const lo = Math.min(sel.a, sel.b);
      const hi = Math.max(sel.a, sel.b);
      onDeleteSourceRange(words[lo].start, words[hi].end);
      setSel(null);
      e.preventDefault();
    }
  }

  if (!transcript) {
    return <div className="transcript-empty mono">Transcribing…</div>;
  }

  return (
    <div className="transcript" tabIndex={0} onKeyDown={onKeyDown}>
      {words.map((w, idx) => (
        <span
          key={`${w.segId}_${w.i}`}
          className={
            "word" +
            (isActive(w) ? " word-active" : "") +
            (inSel(idx) ? " word-sel" : "")
          }
          title={`${w.start.toFixed(2)}s`}
          onMouseDown={() => {
            setSel({ a: idx, b: idx });
            setDragging(true);
          }}
          onMouseEnter={() => {
            if (dragging) setSel((s) => (s ? { ...s, b: idx } : s));
          }}
          onMouseUp={() => {
            setDragging(false);
            if (sel && sel.a === idx && sel.b === idx) onSeek(w.virtualStart);
          }}
        >
          {w.word}
        </span>
      ))}
    </div>
  );
}
