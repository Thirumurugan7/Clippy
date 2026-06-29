// Overlay elements baked into the export. For now: a progress bar that fills as
// the clip plays (shown live in the preview too). Room to grow (text, stickers).
export function OverlaysPanel({ settings, setSettings }) {
  const pb = settings.progress_bar || { enabled: false, color: "#8b6cf6", position: "bottom" };
  const set = (patch) => setSettings({ progress_bar: { ...pb, ...patch } });

  const tr = settings.transition || { fade: false };
  const setTr = (patch) => setSettings({ transition: { ...tr, ...patch } });

  const overlays = settings.text_overlays || [];
  const setOverlays = (next) => setSettings({ text_overlays: next });
  const addOverlay = () =>
    setOverlays([...overlays, { id: Date.now().toString(36), text: "Your text", position: "top", size: 0.06, color: "#ffffff" }]);
  const updateOverlay = (i, patch) => setOverlays(overlays.map((o, j) => (j === i ? { ...o, ...patch } : o)));
  const removeOverlay = (i) => setOverlays(overlays.filter((_, j) => j !== i));

  return (
    <div className="panel">
      <h3>Overlays</h3>
      <p className="panel-sub">Extras drawn on top of the video.</p>

      <button
        className={"toggle-row" + (pb.enabled ? " on" : "")}
        onClick={() => set({ enabled: !pb.enabled })}
        aria-pressed={pb.enabled}
      >
        <span className="toggle-text">
          <span className="toggle-title">Progress bar</span>
          <span className="toggle-desc">A bar that fills as the clip plays</span>
        </span>
        <span className={"switch" + (pb.enabled ? " on" : "")} aria-hidden><span className="switch-knob" /></span>
      </button>

      {pb.enabled && (
        <>
          <div className="panel-row">
            <label>Colour</label>
            <input type="color" value={pb.color || "#8b6cf6"} onChange={(e) => set({ color: e.target.value })} />
          </div>
          <div className="panel-row">
            <label>Position</label>
            <select value={pb.position || "bottom"} onChange={(e) => set({ position: e.target.value })}>
              <option value="bottom">Bottom</option>
              <option value="top">Top</option>
            </select>
          </div>
        </>
      )}

      <button
        className={"toggle-row" + (tr.fade ? " on" : "")}
        onClick={() => setTr({ fade: !tr.fade })}
        aria-pressed={tr.fade}
        style={{ marginTop: 10 }}
      >
        <span className="toggle-text">
          <span className="toggle-title">Fade in / out</span>
          <span className="toggle-desc">Ease from and to black at the ends</span>
        </span>
        <span className={"switch" + (tr.fade ? " on" : "")} aria-hidden><span className="switch-knob" /></span>
      </button>

      <div className="ov-text-head">
        <span className="cap-dl-label">Text overlays</span>
        <button className="btn-use ov-add" onClick={addOverlay}>+ Add text</button>
      </div>
      {overlays.length === 0 && <p className="panel-foot mono">Add a title, hook, or emoji on top of the video.</p>}
      {overlays.map((o, i) => (
        <div className="ov-item" key={o.id || i}>
          <div className="ov-item-row">
            <input
              className="sub-input"
              value={o.text}
              placeholder="Text…"
              onChange={(e) => updateOverlay(i, { text: e.target.value })}
            />
            <button className="ov-rm" onClick={() => removeOverlay(i)} aria-label="Remove">✕</button>
          </div>
          <div className="ov-item-ctrls">
            <select value={o.position} onChange={(e) => updateOverlay(i, { position: e.target.value })}>
              <option value="top">Top</option>
              <option value="center">Center</option>
              <option value="bottom">Bottom</option>
            </select>
            <input
              type="range" min="0.03" max="0.13" step="0.005"
              value={o.size}
              onChange={(e) => updateOverlay(i, { size: Number(e.target.value) })}
            />
            <input type="color" value={o.color} onChange={(e) => updateOverlay(i, { color: e.target.value })} />
          </div>
        </div>
      ))}

      <p className="panel-foot mono">Shown live in the preview and baked into the 9:16 export.</p>
    </div>
  );
}
