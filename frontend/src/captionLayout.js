// Caption layout + canvas drawing for the live vertical preview. Mirrors the
// backend Pillow renderer (backend/captions.py) so the preview matches the
// exported short: words grouped into short lines, the spoken word highlighted.

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

// Draw the caption active at virtual time t onto a 2D context sized W x H.
export function drawCaptions(ctx, lines, t, W, H, opts = {}) {
  const { fontsize = 58, primary = "#ff8a3d", upcoming = "#ffffff", marginV = 300 } = opts;
  const line = lines.find((l) => t >= l.start && t <= l.end);
  if (!line) return;

  ctx.font = `700 ${fontsize}px DejaVu Sans, Arial, sans-serif`;
  ctx.textBaseline = "top";
  const space = ctx.measureText(" ").width;
  const maxW = W - 120;

  // wrap into rows
  const rows = [];
  let row = [];
  let rowW = 0;
  for (const w of line.words) {
    const tw = ctx.measureText(w.word.trim()).width;
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

  const lineH = fontsize * 1.25;
  let y = H - marginV - lineH * rows.length;
  ctx.lineWidth = 6;
  ctx.strokeStyle = "#000";
  ctx.lineJoin = "round";

  for (const r of rows) {
    const widths = r.map((w) => ctx.measureText(w.word.trim()).width);
    const totalW = widths.reduce((a, b) => a + b, 0) + space * (r.length - 1);
    let x = (W - totalW) / 2;
    r.forEach((w, idx) => {
      const txt = w.word.trim();
      const active = t >= w.virtualStart && t <= w.virtualEnd;
      ctx.strokeText(txt, x, y);
      ctx.fillStyle = active ? primary : upcoming;
      ctx.fillText(txt, x, y);
      x += widths[idx] + space;
    });
    y += lineH;
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
