// Mirror of backend/crop.py.
import { ASPECTS } from "./presets.js";

export function targetDims(aspect) {
  const a = ASPECTS[aspect] || ASPECTS["9:16"];
  return [a.w, a.h];
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export function computeCrop(W, H, aspect, cxNorm, cyNorm = 0.5) {
  const ratio = (ASPECTS[aspect] || ASPECTS["9:16"]).ratio;
  let cw, ch;
  if (W / H >= ratio) {
    ch = H;
    cw = Math.round(H * ratio);
  } else {
    cw = W;
    ch = Math.round(W / ratio);
  }
  cw = Math.min(cw, W);
  ch = Math.min(ch, H);
  const sx = Math.round(clamp(cxNorm * W - cw / 2, 0, W - cw));
  const sy = Math.round(clamp(cyNorm * H - ch / 2, 0, H - ch));
  return [sx, sy, cw, ch];
}
