import { useEffect, useRef, useState, useCallback } from "react";
import * as E from "../edl.js";

// Holds the working EDL for a video, applies operations immutably, keeps an
// undo/redo snapshot stack, and autosaves (debounced) to the backend so edits
// survive a reload. Every edit goes through `ops`, the single mutation surface.
export function useEdl(videoId) {
  const [edl, setEdl] = useState(null);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const saveTimer = useRef(null);

  // Load saved EDL (or backend default) when the video changes.
  useEffect(() => {
    let cancelled = false;
    setEdl(null);
    setPast([]);
    setFuture([]);
    fetch(`/api/videos/${videoId}/edit`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setEdl(d.segments);
      });
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  const scheduleSave = useCallback(
    (next) => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        setSaving(true);
        try {
          const res = await fetch(`/api/videos/${videoId}/edit`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ segments: next }),
          });
          setSaveError(!res.ok);
        } catch (e) {
          setSaveError(true);
        } finally {
          setSaving(false);
        }
      }, 500);
    },
    [videoId]
  );

  const apply = useCallback(
    (fn) => {
      setEdl((cur) => {
        if (!cur) return cur;
        const next = fn(cur);
        if (next === cur) return cur; // no-op op, don't pollute history
        setPast((p) => [...p, cur]);
        setFuture([]);
        scheduleSave(next);
        return next;
      });
    },
    [scheduleSave]
  );

  const ops = {
    split: (vt) => apply((e) => E.splitAtVirtual(e, vt)),
    trim: (id, edge, src) => apply((e) => E.trimSegment(e, id, edge, src)),
    del: (id) => apply((e) => E.deleteSegment(e, id)),
    reorder: (from, to) => apply((e) => E.reorderSegment(e, from, to)),
    deleteSourceRange: (a, b) => apply((e) => E.deleteSourceRange(e, a, b)),
    setAll: (next) => apply(() => next),
  };

  const undo = useCallback(() => {
    setPast((p) => {
      if (!p.length) return p;
      const prev = p[p.length - 1];
      setEdl((cur) => {
        setFuture((f) => [cur, ...f]);
        scheduleSave(prev);
        return prev;
      });
      return p.slice(0, -1);
    });
  }, [scheduleSave]);

  const redo = useCallback(() => {
    setFuture((f) => {
      if (!f.length) return f;
      const nxt = f[0];
      setEdl((cur) => {
        setPast((p) => [...p, cur]);
        scheduleSave(nxt);
        return nxt;
      });
      return f.slice(1);
    });
  }, [scheduleSave]);

  return {
    edl,
    ops,
    undo,
    redo,
    canUndo: past.length > 0,
    canRedo: future.length > 0,
    saving,
    saveError,
  };
}
