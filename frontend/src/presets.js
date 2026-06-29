// Mirror of backend/presets.py — keep in sync so the preview matches the export.

export const ASPECTS = {
  "9:16": { ratio: 9 / 16, w: 1080, h: 1920 },
  "1:1": { ratio: 1.0, w: 1080, h: 1080 },
  "4:5": { ratio: 4 / 5, w: 1080, h: 1350 },
  "16:9": { ratio: 16 / 9, w: 1920, h: 1080 },
};

const BASE = {
  font: null,
  fontsize: 58,
  primary: "#ff8a3d",
  upcoming: "#ffffff",
  outline_color: "#000000",
  outline_width: 6,
  uppercase: false,
  word_box: null,
  active_box: null,
  line_band: null,
  glow: null,
  gradient: null,
  position: "bottom",
  max_words: 4,
};
const p = (over) => ({ ...BASE, ...over });

export const CAPTION_PRESETS = {
  hormozi: p({ uppercase: true, fontsize: 64, outline_width: 9, primary: "#1c1c1c", active_box: "#ffd400", upcoming: "#ffffff", max_words: 4 }),
  beast: p({ fontsize: 70, outline_width: 10, glow: "#000000", primary: "#ffe14d", upcoming: "#ffffff", max_words: 3 }),
  karaoke: p({}),
  boxed: p({ word_box: "#11131aCC", active_box: "#ff8a3d", upcoming: "#ffffff", outline_width: 2, fontsize: 54 }),
  tiktok: p({ line_band: "#000000AA", outline_width: 2, primary: "#ffffff", upcoming: "#ffffff", fontsize: 52, max_words: 6 }),
  neon: p({ primary: "#39ff14", upcoming: "#d8ffd0", glow: "#39ff14", outline_color: "#063b00", outline_width: 4 }),
  bold_pop: p({ fontsize: 66, outline_width: 8, primary: "#ff8a3d", upcoming: "#ffffff" }),
  clean: p({ outline_width: 3, primary: "#ffd400", upcoming: "#ffffff", fontsize: 52 }),
  minimal: p({ fontsize: 42, outline_width: 2, primary: "#ffffff", upcoming: "#cfd5e0", position: "bottom", max_words: 6 }),
  uppercase: p({ uppercase: true, fontsize: 58, outline_width: 6, primary: "#ff8a3d" }),
  gradient: p({ fontsize: 64, outline_width: 6, gradient: ["#ffb259", "#ff5a3c"], upcoming: "#ffffff" }),
  subtitle: p({ line_band: "#0b0c0fEE", outline_width: 0, primary: "#ffffff", upcoming: "#ffffff", fontsize: 46, max_words: 8, position: "bottom" }),
};

export const DEFAULT_PRESET = "karaoke";
export const PRESET_NAMES = Object.keys(CAPTION_PRESETS);

export function resolveCaptionStyle(caption) {
  caption = caption || {};
  const preset = caption.preset || DEFAULT_PRESET;
  const style = { ...(CAPTION_PRESETS[preset] || CAPTION_PRESETS[DEFAULT_PRESET]) };
  if (caption.fontsize) style.fontsize = caption.fontsize;
  if (caption.color) style.primary = caption.color;
  if (caption.position) style.position = caption.position;
  style.animate = !!caption.animate;
  return style;
}
