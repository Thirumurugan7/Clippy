import { useState } from "react";

// "Make it post-ready" hub: one-click Auto-Edit (chains the whole pipeline) plus
// AI-written title / hook / hashtags from the transcript — local gemma4.
export function PublishPanel({ videoId, onAutoEdit }) {
  const [busy, setBusy] = useState(false);
  const [copy, setCopy] = useState(null);
  const [gen, setGen] = useState(false);
  const [copied, setCopied] = useState("");

  async function runAuto() {
    setBusy(true);
    try {
      await onAutoEdit();
    } finally {
      setBusy(false);
    }
  }

  async function getCopy() {
    setGen(true);
    try {
      const r = await fetch(`/api/videos/${videoId}/social`, { method: "POST" });
      if (r.ok) setCopy(await r.json());
    } finally {
      setGen(false);
    }
  }

  function copyText(label, text) {
    navigator.clipboard?.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 1200);
  }

  return (
    <div className="panel">
      <h3>Publish</h3>
      <p className="panel-sub">Turn the source into a finished, post-ready short.</p>

      <button className="btn-amber full" onClick={runAuto} disabled={busy}>
        {busy ? "Auto-editing…" : "✨ Auto-Edit this video"}
      </button>
      <p className="cap-dl-hint mono">
        Picks the strongest moment, reframes to 9:16, adds captions, cleans audio,
        and trims silences & filler — all in one pass.
      </p>

      <div className="pub-copy">
        <div className="ov-text-head">
          <span className="cap-dl-label">Title, hook &amp; hashtags</span>
          <button className="btn-use" onClick={getCopy} disabled={gen}>
            {gen ? "Writing…" : copy ? "Regenerate" : "Generate"}
          </button>
        </div>
        {copy && (
          <div className="pub-fields">
            {[
              ["Title", copy.title],
              ["Hook", copy.hook],
              ["Description", copy.description],
            ].map(([label, val]) => val && (
              <button key={label} className="pub-field" onClick={() => copyText(label, val)} title="Click to copy">
                <span className="pub-field-label mono">{copied === label ? "copied" : label}</span>
                <span className="pub-field-val">{val}</span>
              </button>
            ))}
            {copy.hashtags?.length > 0 && (
              <button className="pub-field" onClick={() => copyText("Hashtags", copy.hashtags.join(" "))} title="Click to copy">
                <span className="pub-field-label mono">{copied === "Hashtags" ? "copied" : "Hashtags"}</span>
                <span className="pub-field-val pub-tags">{copy.hashtags.join(" ")}</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
