// Pure Edit Decision List (EDL) model — the single source of truth for an edit.
// An EDL is an ordered array of segments { id, sourceStart, sourceEnd } over the
// original video's timeline. The transcript, timeline, and preview are all pure
// projections of this array, so they can never desync. Every operation returns a
// NEW array (immutability) — callers keep undo history by snapshotting.

let _idCounter = 0;
export function newId() {
  _idCounter += 1;
  return `seg_${Date.now().toString(36)}_${_idCounter}`;
}

const MIN_SEG = 0.04; // ~1 frame at 25fps; minimum meaningful segment length

export function defaultEdl(duration) {
  return [{ id: newId(), sourceStart: 0, sourceEnd: duration }];
}

export function segmentDuration(seg) {
  return seg.sourceEnd - seg.sourceStart;
}

export function totalDuration(edl) {
  return edl.reduce((acc, s) => acc + segmentDuration(s), 0);
}

// virtual time (position in the edited timeline) -> source time (in original video)
export function virtualToSource(edl, vt) {
  let acc = 0;
  for (let i = 0; i < edl.length; i++) {
    const d = segmentDuration(edl[i]);
    if (vt < acc + d || (i === edl.length - 1 && vt <= acc + d + 1e-6)) {
      return { segIndex: i, source: edl[i].sourceStart + (vt - acc) };
    }
    acc += d;
  }
  return null;
}

// source time -> virtual time; null if that source time was cut out of the edit
export function sourceToVirtual(edl, source) {
  let acc = 0;
  for (const seg of edl) {
    if (source >= seg.sourceStart && source <= seg.sourceEnd) {
      return acc + (source - seg.sourceStart);
    }
    acc += segmentDuration(seg);
  }
  return null;
}

export function splitAtVirtual(edl, vt) {
  const map = virtualToSource(edl, vt);
  if (!map) return edl;
  const { segIndex, source } = map;
  const seg = edl[segIndex];
  if (source - seg.sourceStart < MIN_SEG || seg.sourceEnd - source < MIN_SEG) {
    return edl; // too close to an edge to split meaningfully
  }
  const left = { id: newId(), sourceStart: seg.sourceStart, sourceEnd: source };
  const right = { id: newId(), sourceStart: source, sourceEnd: seg.sourceEnd };
  return [...edl.slice(0, segIndex), left, right, ...edl.slice(segIndex + 1)];
}

export function trimSegment(edl, segId, edge, newSource) {
  return edl.map((s) => {
    if (s.id !== segId) return s;
    if (edge === "start") {
      const v = Math.min(newSource, s.sourceEnd - MIN_SEG);
      return { ...s, sourceStart: Math.max(0, v) };
    }
    const v = Math.max(newSource, s.sourceStart + MIN_SEG);
    return { ...s, sourceEnd: v };
  });
}

export function deleteSegment(edl, segId) {
  return edl.filter((s) => s.id !== segId);
}

export function reorderSegment(edl, fromIndex, toIndex) {
  if (fromIndex === toIndex) return edl;
  const copy = [...edl];
  const [moved] = copy.splice(fromIndex, 1);
  copy.splice(toIndex, 0, moved);
  return copy;
}

// Remove the source-time range [rangeStart, rangeEnd] from whichever segments it
// overlaps, splitting/trimming as needed. Used by transcript word/selection delete.
export function deleteSourceRange(edl, rangeStart, rangeEnd) {
  const out = [];
  for (const s of edl) {
    if (rangeEnd <= s.sourceStart || rangeStart >= s.sourceEnd) {
      out.push(s); // no overlap
      continue;
    }
    if (rangeStart > s.sourceStart) {
      out.push({ id: newId(), sourceStart: s.sourceStart, sourceEnd: rangeStart });
    }
    if (rangeEnd < s.sourceEnd) {
      out.push({ id: newId(), sourceStart: rangeEnd, sourceEnd: s.sourceEnd });
    }
  }
  return out;
}

// Transcript projection: walk segments in EDL order, emit words whose source
// timestamps fall inside each segment (>=minKeepRatio of the word retained),
// annotated with their virtual start/end. Guarantees transcript == timeline order.
export function projectWords(edl, words, minKeepRatio = 0.5) {
  const out = [];
  let acc = 0;
  for (const seg of edl) {
    const segLen = segmentDuration(seg);
    for (const w of words) {
      const overlapStart = Math.max(w.start, seg.sourceStart);
      const overlapEnd = Math.min(w.end, seg.sourceEnd);
      const overlap = overlapEnd - overlapStart;
      const wordLen = Math.max(w.end - w.start, 1e-6);
      if (overlap > 0 && overlap / wordLen >= minKeepRatio) {
        out.push({
          ...w,
          segId: seg.id,
          virtualStart: acc + (overlapStart - seg.sourceStart),
          virtualEnd: acc + (overlapEnd - seg.sourceStart),
        });
      }
    }
    acc += segLen;
  }
  return out;
}
