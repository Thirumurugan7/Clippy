import { useEffect, useState } from "react";
import { CAPTION_PRESETS, PRESET_NAMES, FONTS } from "../presets.js";

// Reveal types (how words appear over time) — the Descript/Veed "caption type"
// axis, independent of the colour preset below.
const REVEAL_TYPES = [
  { id: "highlight", label: "Highlight", desc: "Line shows; the spoken word lights up (karaoke)." },
  { id: "build", label: "Word build", desc: "Words appear one by one as they're spoken." },
  { id: "word", label: "One word", desc: "A single big word at a time (TikTok-style)." },
  { id: "line", label: "Clean line", desc: "The whole line, steady — no per-word emphasis." },
];

// Per-word motion (mirrors Veed's named animations). Composes with any type + style.
const MOTIONS = [
  { id: "none", label: "None" },
  { id: "pop", label: "Pop" },
  { id: "bounce", label: "Bounce" },
  { id: "scale_in", label: "Scale in" },
  { id: "float_in", label: "Float up" },
  { id: "drop_in", label: "Drop in" },
  { id: "slide_in", label: "Slide in" },
  { id: "stomp", label: "Stomp" },
  { id: "pulse", label: "Pulse" },
];

const LABELS = {
  hormozi: "Hormozi", beast: "Beast", karaoke: "Karaoke", boxed: "Boxed",
  tiktok: "TikTok", neon: "Neon", bold_pop: "Bold Pop", clean: "Clean",
  minimal: "Minimal", uppercase: "Uppercase", gradient: "Gradient", subtitle: "Subtitle",
};

// Live sample of a preset using its real colours/box so cards are distinguishable.
function Sample({ name }) {
  const s = CAPTION_PRESETS[name];
  const word = s.uppercase ? "WORD" : "word";
  const box = s.active_box || s.word_box;
  return (
    <div className="cap-sample" style={{ background: s.line_band || "transparent" }}>
      <span className="cap-up" style={{ background: s.word_box || "transparent", color: s.upcoming, WebkitTextStroke: s.outline_width ? `1px ${s.outline_color}` : "none" }}>
        {s.uppercase ? "THE" : "the"}
      </span>{" "}
      <span style={{ background: box || "transparent", color: s.gradient ? s.gradient[1] : s.primary, padding: box ? "0 4px" : 0, borderRadius: 4, textShadow: s.glow ? `0 0 6px ${s.glow}` : "none", WebkitTextStroke: s.outline_width ? `1px ${s.outline_color}` : "none" }}>
        {word}
      </span>
    </div>
  );
}

export function CaptionsPanel({ settings, setSettings, videoId }) {
  const cap = settings.caption;
  const [langs, setLangs] = useState([]);
  const lang = cap.language || "";

  useEffect(() => {
    fetch("/api/subtitles/languages")
      .then((r) => r.json())
      .then((d) => setLangs(d.languages || []))
      .catch(() => {});
  }, []);

  const q = lang ? `?lang=${lang}` : "";
  const suffix = lang ? `.${lang}` : "";

  const reveal = cap.reveal || "highlight";
  const motion = cap.animation || (cap.animate ? "pop" : "none");

  return (
    <div className="panel">
      <h3>Captions</h3>
      <p className="panel-sub">Pick how words appear, then a style — both update the preview live.</p>

      <span className="cap-dl-label">Animation type</span>
      <div className="reveal-grid">
        {REVEAL_TYPES.map((r) => (
          <button
            key={r.id}
            className={"reveal-card" + (reveal === r.id ? " on" : "")}
            onClick={() => setSettings({ caption: { reveal: r.id } })}
            title={r.desc}
          >
            <span className="reveal-name">{r.label}</span>
            <span className="reveal-desc">{r.desc}</span>
          </button>
        ))}
      </div>

      <span className="cap-dl-label">Style</span>
      <div className="cap-grid">
        {PRESET_NAMES.map((name) => (
          <button
            key={name}
            className={"cap-card" + (cap.preset === name ? " on" : "")}
            onClick={() => setSettings({ caption: { preset: name } })}
          >
            <Sample name={name} />
            <span className="cap-name">{LABELS[name] || name}</span>
          </button>
        ))}
      </div>

      <div className="panel-row">
        <label>Font</label>
        <select value={cap.font || "default"}
          onChange={(e) => setSettings({ caption: { font: e.target.value } })}>
          {FONTS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
      </div>
      <div className="panel-row">
        <label>Size</label>
        <input type="range" min="36" max="92" value={cap.fontsize || 58}
          onChange={(e) => setSettings({ caption: { fontsize: Number(e.target.value) } })} />
      </div>
      <div className="panel-row">
        <label>Highlight</label>
        <input type="color" value={cap.color || "#ff8a3d"}
          onChange={(e) => setSettings({ caption: { color: e.target.value } })} />
      </div>
      <div className="panel-row">
        <label>Position</label>
        <select value={cap.position || "bottom"}
          onChange={(e) => setSettings({ caption: { position: e.target.value } })}>
          <option value="bottom">Bottom</option>
          <option value="center">Center</option>
          <option value="top">Top</option>
        </select>
      </div>

      <span className="cap-dl-label">Motion</span>
      <div className="motion-grid">
        {MOTIONS.map((m) => (
          <button
            key={m.id}
            className={"motion-chip" + (motion === m.id ? " on" : "")}
            onClick={() => setSettings({ caption: { animation: m.id } })}
            title={`${m.label} — animates the spoken word`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <button
        className={"toggle-row" + (cap.emphasis ? " on" : "")}
        onClick={() => setSettings({ caption: { emphasis: !cap.emphasis } })}
        aria-pressed={!!cap.emphasis}
      >
        <span className="toggle-text">
          <span className="toggle-title">Emphasize keywords</span>
          <span className="toggle-desc">Colour the punchy words so they pop</span>
        </span>
        <span className={"switch" + (cap.emphasis ? " on" : "")} aria-hidden><span className="switch-knob" /></span>
      </button>
      {cap.emphasis && (
        <div className="panel-row">
          <label>Keyword colour</label>
          <input type="color" value={cap.emphasis_color || "#ffd400"}
            onChange={(e) => setSettings({ caption: { emphasis_color: e.target.value } })} />
        </div>
      )}
      <button
        className={"toggle-row" + (cap.speaker_colors ? " on" : "")}
        onClick={() => setSettings({ caption: { speaker_colors: !cap.speaker_colors } })}
        aria-pressed={!!cap.speaker_colors}
      >
        <span className="toggle-text">
          <span className="toggle-title">Colour by speaker</span>
          <span className="toggle-desc">Each speaker gets their own caption colour (run Detect speakers first)</span>
        </span>
        <span className={"switch" + (cap.speaker_colors ? " on" : "")} aria-hidden><span className="switch-knob" /></span>
      </button>

      <div className="panel-row">
        <label>Language</label>
        <select value={lang} onChange={(e) => setSettings({ caption: { language: e.target.value } })}>
          <option value="">Original</option>
          {langs.map((l) => (
            <option key={l.code} value={l.code}>{l.name}</option>
          ))}
        </select>
      </div>
      <p className="cap-dl-hint mono">
        {lang
          ? "Captions are translated locally by gemma4 and burned into the exported video."
          : "Captions match the spoken language."}
      </p>

      {videoId && (
        <div className="cap-downloads">
          <span className="cap-dl-label">Download caption file</span>
          <div className="cap-dl-row">
            <a className="btn-use" href={`/api/videos/${videoId}/subtitles.srt${q}`} download={`captions${suffix}.srt`}>.srt</a>
            <a className="btn-use" href={`/api/videos/${videoId}/subtitles.vtt${q}`} download={`captions${suffix}.vtt`}>.vtt</a>
          </div>
          <p className="cap-dl-hint mono">
            {lang ? "Sidecar file in the selected language." : "Matches your current edit (YouTube, players, re-styling)."}
          </p>
        </div>
      )}
    </div>
  );
}
