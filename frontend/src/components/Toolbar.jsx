// Editor action bar. All actions operate on the current playhead / EDL.
export function Toolbar({
  onSplit,
  onDetectFillers,
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
  return (
    <div className="toolbar">
      <button onClick={onSplit}>Split at playhead</button>
      <button onClick={onDetectFillers}>Detect filler words</button>
      <span className="toolbar-spacer" />
      <button onClick={undo} disabled={!canUndo}>
        Undo
      </button>
      <button onClick={redo} disabled={!canRedo}>
        Redo
      </button>
      <button onClick={onExport} disabled={exporting}>
        {exporting ? "Exporting…" : "Export video"}
      </button>
      <button className="btn-primary" onClick={onExportVertical} disabled={exporting}>
        {exporting ? "Exporting…" : "Make 9:16 short"}
      </button>
      <span className={"save-state mono" + (saveError ? " error" : "")}>
        {saveError ? "save failed" : saving ? "saving…" : "saved"}
      </span>
    </div>
  );
}
