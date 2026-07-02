// A small, self-contained line-icon set (Lucide-style: 24-grid, currentColor
// stroke, rounded joins) so the UI never falls back to inconsistent OS emoji.
// Icons inherit `color`, so active/hover states colour them via CSS.

const ICONS = {
  // tool rail
  wand: (
    <>
      <path d="M5 19.5 14.5 10" />
      <path d="M17.5 2.5l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z" />
    </>
  ),
  sparkles: (
    <>
      <path d="M10 4l1.5 4.5 4.5 1.5-4.5 1.5L10 16l-1.5-4.5L4 10l4.5-1.5z" />
      <path d="M17.5 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
    </>
  ),
  captions: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
      <path d="M7 10.5h10M7 14h6" />
    </>
  ),
  edit: (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" />
    </>
  ),
  crop: (
    <>
      <path d="M6.5 2v14a1.5 1.5 0 0 0 1.5 1.5h14" />
      <path d="M17.5 22V8A1.5 1.5 0 0 0 16 6.5H2" />
    </>
  ),
  image: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="M21 15.5 16 11 6 20" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3 3 8l9 5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </>
  ),
  waveform: <path d="M4 10v4M8 6v12M12 9v6M16 4v16M20 8v8" />,

  // templates
  mic: (
    <>
      <rect x="9" y="2" width="6" height="11" rx="3" />
      <path d="M6 11v1a6 6 0 0 0 12 0v-1" />
      <path d="M12 18v3M9 21h6" />
    </>
  ),
  headphones: (
    <>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" />
      <rect x="3" y="13" width="4" height="6" rx="1.6" />
      <rect x="17" y="13" width="4" height="6" rx="1.6" />
    </>
  ),
  message: (
    <>
      <path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z" />
      <path d="M8 9h8M8 12h5" />
    </>
  ),
  square: <rect x="4" y="4" width="16" height="16" rx="2.5" />,

  // platform chips
  music: (
    <>
      <path d="M9 17V4l11-2v13" />
      <circle cx="6" cy="17" r="3" />
      <circle cx="17" cy="15" r="3" />
    </>
  ),
  camera: (
    <>
      <path d="M3 7h3l1.5-2.5h9L18 7h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" />
      <circle cx="12" cy="13" r="3.5" />
    </>
  ),
  play: <path d="M7 4.5v15l12-7.5z" />,
  portrait: <rect x="7" y="3" width="10" height="18" rx="2" />,
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </>
  ),

  // misc
  record: <circle cx="12" cy="12" r="5" fill="currentColor" stroke="none" />,
  upload: (
    <>
      <path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </>
  ),
  chevronLeft: <path d="M15 5l-7 7 7 7" />,
  chevronRight: <path d="M9 5l7 7-7 7" />,
  scissors: (
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <path d="M8 8l12 8M8 16 20 8" />
    </>
  ),
};

export function Icon({ name, size = 20, className, strokeWidth = 1.85 }) {
  const glyph = ICONS[name];
  if (!glyph) return null;
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {glyph}
    </svg>
  );
}
