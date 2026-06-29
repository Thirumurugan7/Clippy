import { useMemo, useState } from "react";

function clock(t) {
  const m = Math.floor(t / 60);
  const s = Math.round(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Group source-transcript words into editable caption lines.
function groupCues(words, maxWords = 7, maxGap = 0.7) {
  const cues = [];
  let cur = [];
  for (const w of words) {
    if (cur.length) {
      const gap = w.start - cur[cur.length - 1].end;
      if (cur.length >= maxWords || gap > maxGap) {
        cues.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) cues.push(cur);
  return cues.map((ws) => ({
    start: ws[0].start,
    end: ws[ws.length - 1].end,
    text: ws.map((w) => w.word.trim()).join(" "),
  }));
}

// Edit caption text per line. Saving retimes the line's words evenly and the
// fix flows to burned-in captions AND the SRT/VTT downloads (all read the words).
export function SubtitleEditor({ transcript, videoId, onReload }) {
  const [saving, setSaving] = useState(null);
  const cues = useMemo(() => (transcript ? groupCues(transcript.words) : []), [transcript]);

  if (!transcript) {
    return (
      <div className="panel">
        <h3>Subtitles</h3>
        <p className="panel-sub">Transcript still loading…</p>
      </div>
    );
  }

  async function saveCue(cue, value, idx) {
    const text = value.trim();
    if (text === cue.text.trim() || !text) return;
    setSaving(idx);
    try {
      await fetch(`/api/videos/${videoId}/transcript/cue`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start: cue.start, end: cue.end, text }),
      });
      if (onReload) await onReload();
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="panel">
      <h3>Subtitles</h3>
      <p className="panel-sub">Fix any line — changes flow to captions and the .srt/.vtt downloads.</p>
      <div className="sub-list">
        {cues.map((c, i) => (
          <div className="sub-row" key={`${c.start.toFixed(2)}-${i}`}>
            <span className="sub-time mono">{clock(c.start)}</span>
            <input
              className="sub-input"
              defaultValue={c.text}
              onBlur={(e) => saveCue(c, e.target.value, i)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  e.target.blur();
                }
              }}
            />
            {saving === i && <span className="sub-saving mono">saving…</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
