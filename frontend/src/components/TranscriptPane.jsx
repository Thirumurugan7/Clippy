import { useMemo, useRef, useState } from "react";
import { projectWords } from "../edl.js";

// Renders the transcript as a pure projection of the EDL (so it always matches
// the timeline order). Interactions:
//   - single click a word  -> seek the preview there
//   - drag across words     -> select that range
//   - double-click a word   -> select just that word
//   - Delete/Backspace      -> cut the selected source range from the EDL
export function TranscriptPane({ transcript, edl, activeVirtual, txProgress, onSeek, onDeleteSourceRange }) {
  const words = useMemo(
    () => (transcript && edl ? projectWords(edl, transcript.words) : []),
    [transcript, edl]
  );
  const [sel, setSel] = useState(null); // persisted selection {a,b} (indices)
  const anchor = useRef(null); // drag anchor index
  const moved = useRef(false); // did the pointer move during this drag

  function isActive(w) {
    return activeVirtual >= w.virtualStart && activeVirtual <= w.virtualEnd;
  }
  function inSel(idx) {
    if (!sel) return false;
    return idx >= Math.min(sel.a, sel.b) && idx <= Math.max(sel.a, sel.b);
  }
  function deleteSelection() {
    if (!sel) return;
    const lo = Math.min(sel.a, sel.b);
    const hi = Math.max(sel.a, sel.b);
    onDeleteSourceRange(words[lo].start, words[hi].end);
    setSel(null);
  }
  function onKeyDown(e) {
    if ((e.key === "Delete" || e.key === "Backspace") && sel) {
      e.preventDefault();
      deleteSelection();
    }
  }

  if (!transcript) {
    const pct = Math.round((txProgress?.progress || 0) * 100);
    const running = txProgress?.status === "running" || pct > 0;
    return (
      <div className="transcript-empty">
        <div className="tx-row mono">
          <span>{running ? `Transcribing… ${pct}%` : "Transcription queued…"}</span>
        </div>
        <div className="tx-bar"><div className="tx-fill" style={{ width: `${Math.max(3, pct)}%` }} /></div>
        <p className="muted mono tx-note">Runs locally with faster-whisper — roughly real-time on this machine.</p>
      </div>
    );
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
            anchor.current = idx;
            moved.current = false;
            setSel(null);
          }}
          onMouseEnter={() => {
            if (anchor.current != null) {
              moved.current = true;
              setSel({ a: anchor.current, b: idx });
            }
          }}
          onMouseUp={() => {
            if (anchor.current != null && !moved.current) onSeek(w.virtualStart);
            anchor.current = null;
          }}
          onDoubleClick={() => setSel({ a: idx, b: idx })}
        >
          {w.word}
        </span>
      ))}
    </div>
  );
}
