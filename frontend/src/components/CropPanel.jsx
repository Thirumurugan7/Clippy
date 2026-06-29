const ASPECT_OPTS = [
  { id: "9:16", label: "9:16", hint: "Reels / TikTok / Shorts" },
  { id: "1:1", label: "1:1", hint: "Square post" },
  { id: "4:5", label: "4:5", hint: "Portrait post" },
  { id: "16:9", label: "16:9", hint: "Landscape" },
];

// One-click platform presets (Veed-style "Resize for X"). Each sets the aspect
// AND nudges caption position so text clears the platform's own on-screen UI
// (TikTok/Reels cover the lower third, so captions move to center there).
const PLATFORMS = [
  { id: "tiktok", label: "TikTok", icon: "🎵", aspect: "9:16", position: "center" },
  { id: "reels", label: "Reels", icon: "📸", aspect: "9:16", position: "center" },
  { id: "shorts", label: "Shorts", icon: "▶️", aspect: "9:16", position: "bottom" },
  { id: "ig_square", label: "Insta 1:1", icon: "⬛", aspect: "1:1", position: "bottom" },
  { id: "ig_portrait", label: "Insta 4:5", icon: "🖼", aspect: "4:5", position: "bottom" },
  { id: "youtube", label: "YouTube", icon: "📺", aspect: "16:9", position: "bottom" },
];

export function CropPanel({ settings, setSettings }) {
  const curPos = settings.caption?.position || "bottom";
  return (
    <div className="panel">
      <h3>Crop & aspect</h3>
      <p className="panel-sub">Choose the output shape and how it frames.</p>

      <span className="cap-dl-label">Resize for platform</span>
      <div className="plat-grid">
        {PLATFORMS.map((p) => (
          <button
            key={p.id}
            className={"plat-chip" + (settings.aspect === p.aspect && curPos === p.position ? " on" : "")}
            onClick={() => setSettings({ aspect: p.aspect, caption: { position: p.position } })}
            title={`${p.aspect} · captions ${p.position}`}
          >
            <span className="plat-icon">{p.icon}</span>
            {p.label}
          </button>
        ))}
      </div>

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
          ? "Drag the crop box on the preview to frame it exactly."
          : "The crop follows the main face automatically."}
      </p>
    </div>
  );
}
