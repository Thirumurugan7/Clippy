import { useState, useRef, useEffect } from "react";

// Editor action bar: editing actions on the left, a single Export menu on the
// right that gathers every output in one place so users aren't hunting for it.
export function Toolbar({
  onSplit,
  onDetectFillers,
  onRemoveSilences,
  onExport,
  onExportVertical,
  undo,
  redo,
  canUndo,
  canRedo,
  saving,
  saveError,
  exporting,
}) {
  const [menu, setMenu] = useState(false);
  const wrapRef = useRef(null);
  useEffect(() => {
    function onDoc(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setMenu(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(fn) {
    setMenu(false);
    fn();
  }

  return (
    <div className="toolbar">
      <button onClick={onSplit}>Split at playhead</button>
      <button onClick={onDetectFillers}>Remove filler words</button>
      <button onClick={onRemoveSilences}>Remove silences</button>
      <span className="toolbar-spacer" />
      <button onClick={undo} disabled={!canUndo} title="Undo">↶</button>
      <button onClick={redo} disabled={!canRedo} title="Redo">↷</button>
      <span className={"save-state mono" + (saveError ? " error" : "")}>
        {saveError ? "save failed" : saving ? "saving…" : "saved"}
      </span>
      <div className="export-menu-wrap" ref={wrapRef}>
        <button className="btn-primary export-btn" onClick={() => setMenu((s) => !s)} disabled={exporting}>
          {exporting ? "Exporting…" : "Export ▾"}
        </button>
        {menu && !exporting && (
          <div className="export-menu">
            <button className="export-item" onClick={() => pick(onExportVertical)}>
              <span className="ei-title">9:16 vertical short</span>
              <span className="ei-desc">Face-tracked crop + captions</span>
            </button>
            <button className="export-item" onClick={() => pick(onExport)}>
              <span className="ei-title">Edited video</span>
              <span className="ei-desc">Your cuts, original aspect</span>
            </button>
            <div className="export-hint mono">
              Multiple clips at once? Use <b>Export all</b> in Highlights.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
