const ASPECT_OPTS = [
  { id: "9:16", label: "9:16", hint: "Reels / TikTok / Shorts" },
  { id: "1:1", label: "1:1", hint: "Square post" },
  { id: "4:5", label: "4:5", hint: "Portrait post" },
  { id: "16:9", label: "16:9", hint: "Landscape" },
];

export function CropPanel({ settings, setSettings }) {
  return (
    <div className="panel">
      <h3>Crop & aspect</h3>
      <p className="panel-sub">Choose the output shape and how it frames.</p>
      <div className="aspect-grid">
        {ASPECT_OPTS.map((a) => (
          <button
            key={a.id}
            className={"aspect-card" + (settings.aspect === a.id ? " on" : "")}
            onClick={() => setSettings({ aspect: a.id })}
          >
            <span className={`aspect-icon ar-${a.id.replace(":", "-")}`} />
            <span className="aspect-label">{a.label}</span>
            <span className="aspect-hint">{a.hint}</span>
          </button>
        ))}
      </div>

      <div className="seg-toggle wide">
        <button className={settings.framing === "auto" ? "on" : ""} onClick={() => setSettings({ framing: "auto" })}>
          Auto (face-track)
        </button>
        <button className={settings.framing === "manual" ? "on" : ""} onClick={() => setSettings({ framing: "manual" })}>
          Manual
        </button>
      </div>
      <p className="panel-sub">
        {settings.framing === "manual"
          ? "Drag left/right on the preview to reposition the crop."
          : "The crop follows the main face automatically."}
      </p>
    </div>
  );
}
