// Background removal controls. Selfie segmentation separates the speaker, then
// the background is kept, blurred, or replaced with a flat colour. Applied in
// the 9:16 export (the live preview shows the original frame).
const MODES = [
  { id: "none", label: "Keep", desc: "Original background" },
  { id: "blur", label: "Blur", desc: "Defocus behind the speaker" },
  { id: "color", label: "Color", desc: "Replace with a solid colour" },
];

export function BackgroundPanel({ settings, setSettings }) {
  const bg = settings.background || { mode: "none", color: "#10121a" };
  const set = (patch) => setSettings({ background: { ...bg, ...patch } });

  return (
    <div className="panel">
      <h3>Background</h3>
      <p className="panel-sub">Blur or replace what’s behind the speaker, on 9:16 export.</p>

      <div className="bg-modes">
        {MODES.map((m) => (
          <button
            key={m.id}
            className={"bg-card" + (bg.mode === m.id ? " on" : "")}
            onClick={() => set({ mode: m.id })}
          >
            <span className="bg-card-title">{m.label}</span>
            <span className="bg-card-desc">{m.desc}</span>
          </button>
        ))}
      </div>

      {bg.mode === "color" && (
        <div className="panel-row">
          <label>Background colour</label>
          <input
            type="color"
            value={bg.color || "#10121a"}
            onChange={(e) => set({ color: e.target.value })}
          />
        </div>
      )}

      <p className="panel-foot mono">
        {bg.mode === "none"
          ? "Off — the original background is kept."
          : "Runs selfie segmentation per frame during export (adds render time)."}
      </p>
    </div>
  );
}
