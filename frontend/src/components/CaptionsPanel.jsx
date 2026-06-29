import { useEffect, useState } from "react";
import { CAPTION_PRESETS, PRESET_NAMES } from "../presets.js";

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
  const [lang, setLang] = useState("");

  useEffect(() => {
    fetch("/api/subtitles/languages")
      .then((r) => r.json())
      .then((d) => setLangs(d.languages || []))
      .catch(() => {});
  }, []);

  const q = lang ? `?lang=${lang}` : "";
  const suffix = lang ? `.${lang}` : "";

  return (
    <div className="panel">
      <h3>Captions</h3>
      <p className="panel-sub">Pick a style — it updates the preview live.</p>
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

      {videoId && (
        <div className="cap-downloads">
          <span className="cap-dl-label">Download caption file</span>
          <div className="panel-row">
            <label>Language</label>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="">Original</option>
              {langs.map((l) => (
                <option key={l.code} value={l.code}>{l.name}</option>
              ))}
            </select>
          </div>
          <div className="cap-dl-row">
            <a className="btn-use" href={`/api/videos/${videoId}/subtitles.srt${q}`} download={`captions${suffix}.srt`}>.srt</a>
            <a className="btn-use" href={`/api/videos/${videoId}/subtitles.vtt${q}`} download={`captions${suffix}.vtt`}>.vtt</a>
          </div>
          <p className="cap-dl-hint mono">
            {lang ? "Translated locally by gemma4 — may take a few seconds." : "Matches your current edit (YouTube, players, re-styling)."}
          </p>
        </div>
      )}
    </div>
  );
}
