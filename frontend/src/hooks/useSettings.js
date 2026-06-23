import { useEffect, useRef, useState, useCallback } from "react";

// Loads per-video settings (aspect/framing/crop_cx/caption) and autosaves
// partial updates (debounced). Single source of truth read by the preview; the
// export reads the same record server-side.
export function useSettings(videoId) {
  const [settings, setSettingsState] = useState(null);
  const [saving, setSaving] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setSettingsState(null);
    fetch(`/api/videos/${videoId}/settings`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setSettingsState(d);
      });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const save = useCallback(
    (next) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(async () => {
        setSaving(true);
        try {
          await fetch(`/api/videos/${videoId}/settings`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(next),
          });
        } finally {
          setSaving(false);
        }
      }, 400);
    },
    [videoId]
  );

  const setSettings = useCallback(
    (partial) => {
      setSettingsState((cur) => {
        if (!cur) return cur;
        // shallow merge, with a nested merge for `caption`
        const next = { ...cur, ...partial };
        if (partial.caption) next.caption = { ...cur.caption, ...partial.caption };
        save(next);
        return next;
      });
    },
    [save]
  );

  return { settings, setSettings, saving };
}
