import { useRef, useState } from "react";

// Background removal controls. Selfie segmentation separates the speaker, then
// the background is kept, blurred, replaced with a flat colour, or replaced with
// a custom photo (green-screen). Applied in the 9:16 export.
const MODES = [
  { id: "none", label: "Keep", desc: "Original background" },
  { id: "blur", label: "Blur", desc: "Defocus behind the speaker" },
  { id: "color", label: "Color", desc: "Replace with a solid colour" },
  { id: "image", label: "Image", desc: "Replace with a photo" },
];

export function BackgroundPanel({ settings, setSettings, videoId }) {
  const bg = settings.background || { mode: "none", color: "#10121a" };
  const set = (patch) => setSettings({ background: { ...bg, ...patch } });
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  async function uploadImage(f) {
    if (!f) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch(`/api/videos/${videoId}/background_image`, { method: "POST", body: form });
      const data = await res.json();
      if (res.ok) set({ mode: "image", image: data.image });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="panel">
      <h3>Background</h3>
      <p className="panel-sub">Blur or replace what’s behind the speaker, on 9:16 export.</p>

      <div className="bg-modes">
        {MODES.map((m) => (
          <button
            key={m.id}
            className={"bg-card" + (bg.mode === m.id ? " on" : "")}
            onClick={() => (m.id === "image" ? fileRef.current?.click() : set({ mode: m.id }))}
          >
            <span className="bg-card-title">{m.label}</span>
            <span className="bg-card-desc">{m.desc}</span>
          </button>
        ))}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hidden
        onChange={(e) => uploadImage(e.target.files?.[0] || null)}
      />

      {bg.mode === "color" && (
        <div className="panel-row">
          <label>Background colour</label>
          <input type="color" value={bg.color || "#10121a"} onChange={(e) => set({ color: e.target.value })} />
        </div>
      )}

      {bg.mode === "image" && (
        <div className="bg-image-row">
          {bg.image && (
            <img className="bg-thumb" src={`/api/videos/${videoId}/background_image/file?t=${encodeURIComponent(bg.image)}`} alt="background" />
          )}
          <button className="btn-use" onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? "Uploading…" : bg.image ? "Change image" : "Choose image"}
          </button>
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
