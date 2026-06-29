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

// Word-pop: the active word scales up for the first POP_DUR of its window,
// easing back to 1.0. Shared shape with the backend Pillow renderer so the
// preview matches the export.
const POP_DUR = 0.18;
const POP_AMOUNT = 0.3;
export function popScale(t, w) {
  const e = t - w.virtualStart;
  if (e < 0 || e > POP_DUR) return 1;
  return 1 + POP_AMOUNT * (1 - e / POP_DUR);
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

// Draw the caption active at virtual time t. `style` keys mirror presets.py.
export function drawCaptions(ctx, lines, t, W, H, style) {
  const line = lines.find((l) => t >= l.start && t <= l.end);
  if (!line) return;
  const fs = style.fontsize;
  const txt = (w) => (style.uppercase ? w.word.trim().toUpperCase() : w.word.trim());

  ctx.font = `700 ${fs}px "DejaVu Sans", Arial, sans-serif`;
  ctx.textBaseline = "top";
  const space = ctx.measureText(" ").width;
  const pad = Math.max(6, fs * 0.22);
  const maxW = W - 80;

  // wrap
  const rows = [];
  let row = [], rowW = 0;
  for (const w of line.words) {
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
      const active = t >= w.virtualStart && t <= w.virtualEnd;
      const box = active && style.active_box ? style.active_box : style.word_box;
      if (box) {
        ctx.fillStyle = box;
        roundRect(ctx, bx - pad / 2, y, widths[i] + pad, lineH - 6, 8);
      }
      bx += widths[i] + space;
    });
    // text
    r.forEach((w, i) => {
      const active = t >= w.virtualStart && t <= w.virtualEnd;
      const s = txt(w);
      ctx.save();
      // word-pop: scale the active glyph around its centre
      if (style.animate && active) {
        const pop = popScale(t, w);
        if (pop !== 1) {
          const cx = x + widths[i] / 2;
          const cy = y + fs / 2;
          ctx.translate(cx, cy);
          ctx.scale(pop, pop);
          ctx.translate(-cx, -cy);
        }
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
        ctx.fillStyle = active ? style.primary : style.upcoming;
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
