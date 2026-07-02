// Use-case templates for the prompt-first home (mirrors Veed/Descript's "what do
// you want to make?" entry). Picking one configures the new video — settings
// (aspect / caption / background / audio) plus a starter AI-edit prompt — so the
// editor opens already set up for that outcome.
export const TEMPLATES = [
  {
    id: "talking_head",
    title: "Talking-head reel",
    desc: "9:16, face-tracked, blurred background, karaoke captions",
    icon: "mic",
    prompt: "Make a punchy 30-second vertical reel of the strongest point.",
    settings: {
      aspect: "9:16",
      framing: "auto",
      enhance_audio: true,
      background: { mode: "blur", color: "#10121a" },
      caption: { preset: "karaoke" },
    },
  },
  {
    id: "podcast_clip",
    title: "Podcast clip",
    desc: "9:16, bold captions, cleaned-up audio",
    icon: "headphones",
    prompt: "Find the most engaging 40-second moment and make it a clip.",
    settings: {
      aspect: "9:16",
      framing: "auto",
      enhance_audio: true,
      background: { mode: "none", color: "#10121a" },
      caption: { preset: "beast" },
    },
  },
  {
    id: "subtitled_short",
    title: "Subtitled short",
    desc: "9:16, clean subtitles — great for sound-off feeds",
    icon: "message",
    prompt: "Make a 30-second clip with clear, readable subtitles.",
    settings: {
      aspect: "9:16",
      framing: "auto",
      enhance_audio: false,
      background: { mode: "none", color: "#10121a" },
      caption: { preset: "subtitle" },
    },
  },
  {
    id: "square_promo",
    title: "Square promo",
    desc: "1:1, bold pop captions — feed-native promo",
    icon: "square",
    prompt: "Make a punchy 20-second square promo of the best line.",
    settings: {
      aspect: "1:1",
      framing: "auto",
      enhance_audio: true,
      background: { mode: "none", color: "#10121a" },
      caption: { preset: "bold_pop" },
    },
  },
];
