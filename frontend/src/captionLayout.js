// Caption layout + canvas drawing for the live vertical preview. Mirrors the
// backend Pillow renderer (backend/captions.py) + presets so the preview matches
// the exported short. `style` is a resolved caption style (see presets.js).

export function groupLines(words, maxWords = 4, maxGap = 0.7) {
  const lines = [];
  let cur = [];
  for (const w of words) {
    if (cur.length) {
      const gap = w.virtualStart - cur[cur.length - 1].virtualEnd;
      if (cur.length >= maxWords || gap > maxGap) {
        lines.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) lines.push(cur);
  return lines.map((ws) => ({
    start: ws[0].virtualStart,
    end: ws[ws.length - 1].virtualEnd,
    words: ws,
  }));
}

// Per-word motion for the active word — mirror of backend captions.word_anim so
// the preview matches the export. Returns {scale, dx, dy, alpha}.
const ANIM_DUR = 0.25;
export function wordAnim(name, e, dur, fs) {
  if (!name || name === "none") return { scale: 1, dx: 0, dy: 0, alpha: 1 };
  if (name === "pulse") return { scale: 1 + 0.05 * Math.sin((2 * Math.PI * e) / 0.7), dx: 0, dy: 0, alpha: 1 };
  const p = dur > 0 ? e / dur : 1;
  if (p < 0 || p > 1) return { scale: 1, dx: 0, dy: 0, alpha: 1 };
  const q = 1 - p;
  switch (name) {
    case "pop": return { scale: 1 + 0.3 * q, dx: 0, dy: 0, alpha: 1 };
    case "bounce": return { scale: 1 + 0.35 * Math.sin(Math.PI * p), dx: 0, dy: 0, alpha: 1 };
    case "scale_in": return { scale: 0.4 + 0.6 * p, dx: 0, dy: 0, alpha: p };
    case "float_in": return { scale: 1, dx: 0, dy: 0.55 * fs * q, alpha: p };
    case "drop_in": return { scale: 1, dx: 0, dy: -0.55 * fs * q, alpha: p };
    case "slide_in": return { scale: 1, dx: 0.6 * fs * q, dy: 0, alpha: p };
    case "stomp": return { scale: 1 + 0.8 * q * q, dx: 0, dy: 0, alpha: Math.min(1, 0.5 + 0.5 * p) };
    default: return { scale: 1, dx: 0, dy: 0, alpha: 1 };
  }
}

function roundRect(ctx, x, y, w, h, r) {
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    ctx.fill();
  } else {
    ctx.fillRect(x, y, w, h);
  }
}

// Reveal type mirrors backend/captions.py: which words show and how they colour.
function wordVisible(w, t, reveal) {
  if (reveal === "word") return t >= w.virtualStart && t <= w.virtualEnd;
  if (reveal === "build") return t >= w.virtualStart;
  return true; // highlight, line
}
function wordState(w, t, reveal) {
  if (reveal === "line") return "line";
  if (t >= w.virtualStart && t <= w.virtualEnd) return "active";
  if (reveal === "build") return "past";
  if (reveal === "word") return "active";
  return "upcoming";
}

// Mirror of backend captions.SPEAKER_PALETTE / is_keyword / _word_fill.
const SPEAKER_PALETTE = ["#8b6cf6", "#f6a04d", "#4dd0e1", "#e05d8f", "#7bc86c", "#d7c04d"];
const STOPWORDS = new Set(["the","and","for","are","but","not","you","your","with","that","this","have","has","had","was","were","will","would","they","them","then","than","from","into","just","like","what","when","where","which","there","their","about","been","some","such","only","over","also","these","those","here","very","much","more","most","each","onto","upon","because","while","gonna","wanna","kind","sort"]);
function isKeyword(word) {
  const t = (word || "").toLowerCase().replace(/[^\w']/g, "");
  return t.length >= 4 && !STOPWORDS.has(t);
}
function wordFill(style, w, state) {
  if (state === "active") return style.primary;
  if (style.emphasis && isKeyword(w.word)) return style.emphasis_color;
  if (style.speaker_colors && w.speaker != null) return SPEAKER_PALETTE[w.speaker % SPEAKER_PALETTE.length];
  return state === "past" || state === "line" ? style.primary : style.upcoming;
}

// Draw the caption active at virtual time t. `style` keys mirror presets.py.
export function drawCaptions(ctx, lines, t, W, H, style) {
  const line = lines.find((l) => t >= l.start && t <= l.end);
  if (!line) return;
  const reveal = style.reveal || "highlight";
  const shown = line.words.filter((w) => wordVisible(w, t, reveal));
  if (!shown.length) return;
  const fs = style.fontsize;
  const txt = (w) => (style.uppercase ? w.word.trim().toUpperCase() : w.word.trim());

  ctx.font = `700 ${fs}px ${style.font_family || '"DejaVu Sans", Arial, sans-serif'}`;
  ctx.textBaseline = "top";
  const space = ctx.measureText(" ").width;
  const pad = Math.max(6, fs * 0.22);
  const maxW = W - 80;

  // wrap
  const rows = [];
  let row = [], rowW = 0;
  for (const w of shown) {
    const tw = ctx.measureText(txt(w)).width;
    const add = tw + (row.length ? space : 0);
    if (row.length && rowW + add > maxW) {
      rows.push(row);
      row = [];
      rowW = 0;
    }
    row.push(w);
    rowW += row.length === 1 ? tw : add;
  }
  if (row.length) rows.push(row);

  const lineH = fs * 1.3;
  const totalH = lineH * rows.length;
  let y;
  if (style.position === "center") y = (H - totalH) / 2;
  else if (style.position === "top") y = H * 0.1;
  else y = H - H * 0.16 - totalH;

  for (const r of rows) {
    const widths = r.map((w) => ctx.measureText(txt(w)).width);
    const rw = widths.reduce((a, b) => a + b, 0) + space * (r.length - 1);
    let x = (W - rw) / 2;

    if (style.line_band) {
      ctx.fillStyle = style.line_band;
      roundRect(ctx, x - pad, y - pad / 2, rw + pad * 2, lineH, 12);
    }
    // boxes
    let bx = x;
    r.forEach((w, i) => {
      const st = wordState(w, t, reveal);
      const box = st === "active" && style.active_box ? style.active_box : style.word_box;
      if (box) {
        ctx.fillStyle = box;
        roundRect(ctx, bx - pad / 2, y, widths[i] + pad, lineH - 6, 8);
      }
      bx += widths[i] + space;
    });
    // text
    r.forEach((w, i) => {
      const st = wordState(w, t, reveal);
      const active = st === "active";
      const s = txt(w);
      ctx.save();
      // active-word motion (scale / offset / fade) around its centre
      if (active && style.animation && style.animation !== "none") {
        const dur = Math.min(ANIM_DUR, (w.virtualEnd - w.virtualStart) * 0.8) || ANIM_DUR;
        const a = wordAnim(style.animation, t - w.virtualStart, dur, fs);
        const cx = x + widths[i] / 2;
        const cy = y + fs / 2;
        ctx.translate(cx + a.dx, cy + a.dy);
        ctx.scale(a.scale, a.scale);
        ctx.translate(-cx, -cy);
        ctx.globalAlpha = a.alpha;
      }
      if (style.glow && active) {
        ctx.shadowColor = style.glow;
        ctx.shadowBlur = fs * 0.5;
      }
      if (style.outline_width > 0) {
        ctx.lineWidth = style.outline_width;
        ctx.strokeStyle = style.outline_color;
        ctx.lineJoin = "round";
        ctx.strokeText(s, x, y);
      }
      if (active && style.gradient) {
        const g = ctx.createLinearGradient(0, y, 0, y + fs);
        g.addColorStop(0, style.gradient[0]);
        g.addColorStop(1, style.gradient[1]);
        ctx.fillStyle = g;
      } else {
        ctx.fillStyle = wordFill(style, w, st);
      }
      ctx.fillText(s, x, y);
      ctx.restore();
      x += widths[i] + space;
    });
    y += lineH;
  }
}

// Static text overlays (mirror backend/overlays.py). Horizontally centred,
// top/center/bottom, outlined for legibility. size is a fraction of height.
export function drawTextOverlays(ctx, overlays, W, H) {
  if (!overlays || !overlays.length) return;
  const margin = H * 0.05;
  for (const ov of overlays) {
    const text = (ov.text || "").trim();
    if (!text) continue;
    const size = Math.max(10, (ov.size || 0.06) * H);
    ctx.save();
    ctx.font = `700 ${size}px "DejaVu Sans", Arial, sans-serif`;
    ctx.textBaseline = "top";
    ctx.textAlign = "center";
    const sw = Math.max(2, size / 16);
    let y;
    if (ov.position === "bottom") y = H - margin - size;
    else if (ov.position === "center") y = (H - size) / 2;
    else y = margin;
    ctx.lineWidth = sw;
    ctx.strokeStyle = "#000";
    ctx.lineJoin = "round";
    ctx.strokeText(text, W / 2, y);
    ctx.fillStyle = ov.color || "#ffffff";
    ctx.fillText(text, W / 2, y);
    ctx.restore();
  }
}

// Linear-interpolate the normalized face centre at source time s.
export function cxAt(centers, s) {
  if (!centers || !centers.length) return 0.5;
  let prev = null;
  for (const c of centers) {
    if (c.cx == null) continue;
    if (c.t <= s) prev = c;
    else {
      if (prev == null) return c.cx;
      const span = c.t - prev.t || 1;
      return prev.cx + ((s - prev.t) / span) * (c.cx - prev.cx);
    }
  }
  return prev ? prev.cx : 0.5;
}
