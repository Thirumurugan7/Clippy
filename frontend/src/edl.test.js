import { describe, it, expect } from "vitest";
import {
  defaultEdl,
  segmentDuration,
  totalDuration,
  virtualToSource,
  sourceToVirtual,
  splitAtVirtual,
  trimSegment,
  deleteSegment,
  reorderSegment,
  deleteSourceRange,
  projectWords,
} from "./edl.js";

describe("edl core", () => {
  it("defaultEdl is one segment covering the whole video", () => {
    const edl = defaultEdl(10);
    expect(edl).toHaveLength(1);
    expect(edl[0].sourceStart).toBe(0);
    expect(edl[0].sourceEnd).toBe(10);
    expect(typeof edl[0].id).toBe("string");
  });
  it("segmentDuration and totalDuration", () => {
    const edl = defaultEdl(10);
    expect(segmentDuration(edl[0])).toBe(10);
    expect(totalDuration(edl)).toBe(10);
  });
});

describe("edl time mapping", () => {
  const edl = [
    { id: "a", sourceStart: 0, sourceEnd: 2 },
    { id: "b", sourceStart: 5, sourceEnd: 7 },
  ];
  it("virtualToSource maps across the join", () => {
    expect(virtualToSource(edl, 1)).toEqual({ segIndex: 0, source: 1 });
    expect(virtualToSource(edl, 2.5)).toEqual({ segIndex: 1, source: 5.5 });
    expect(virtualToSource(edl, 99)).toBeNull();
  });
  it("sourceToVirtual inverts, null for cut-out source", () => {
    expect(sourceToVirtual(edl, 1)).toBeCloseTo(1);
    expect(sourceToVirtual(edl, 5.5)).toBeCloseTo(2.5);
    expect(sourceToVirtual(edl, 3.5)).toBeNull();
  });
});

describe("edl operations", () => {
  it("splitAtVirtual splits the covering segment", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4);
    expect(edl).toHaveLength(2);
    expect(edl[0]).toMatchObject({ sourceStart: 0, sourceEnd: 4 });
    expect(edl[1]).toMatchObject({ sourceStart: 4, sourceEnd: 10 });
  });
  it("trimSegment moves an edge", () => {
    const noop = trimSegment(defaultEdl(10), "x", "end", 7);
    expect(noop).toHaveLength(1);
    const base = defaultEdl(10);
    const trimmed = trimSegment(base, base[0].id, "start", 3);
    expect(trimmed[0].sourceStart).toBe(3);
  });
  it("deleteSegment removes by id and reduces duration", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4);
    const after = deleteSegment(edl, edl[0].id);
    expect(after).toHaveLength(1);
    expect(totalDuration(after)).toBe(6);
  });
  it("reorderSegment moves a segment", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4);
    const after = reorderSegment(edl, 0, 1);
    expect(after[0].sourceStart).toBe(4);
    expect(after[1].sourceStart).toBe(0);
  });
  it("deleteSourceRange excises a sub-range, splitting as needed", () => {
    const after = deleteSourceRange(defaultEdl(10), 4, 5);
    expect(after).toHaveLength(2);
    expect(after[0]).toMatchObject({ sourceStart: 0, sourceEnd: 4 });
    expect(after[1]).toMatchObject({ sourceStart: 5, sourceEnd: 10 });
    expect(totalDuration(after)).toBe(9);
  });
  it("deleteSourceRange drops sub-MIN_SEG slivers (no invalid segment)", () => {
    // deleting [0.01, 5] would leave a 0.01s left sliver — it must be dropped.
    const after = deleteSourceRange(defaultEdl(10), 0.01, 5);
    expect(after).toHaveLength(1);
    expect(after[0]).toMatchObject({ sourceStart: 5, sourceEnd: 10 });
  });
});

describe("transcript projection", () => {
  const words = [
    { i: 0, word: "a", start: 0.0, end: 1.0, prob: 1 },
    { i: 1, word: "b", start: 1.0, end: 2.0, prob: 1 },
    { i: 2, word: "c", start: 2.0, end: 3.0, prob: 1 },
  ];
  it("keeps all words for full EDL, in order", () => {
    const out = projectWords(defaultEdl(3), words);
    expect(out.map((w) => w.word)).toEqual(["a", "b", "c"]);
    expect(out[1].virtualStart).toBeCloseTo(1.0);
  });
  it("drops words inside a cut, reflects reorder", () => {
    let edl = splitAtVirtual(splitAtVirtual(defaultEdl(3), 1), 2);
    edl = edl.filter((s) => !(s.sourceStart === 1 && s.sourceEnd === 2));
    edl = reorderSegment(edl, 1, 0);
    const out = projectWords(edl, words);
    expect(out.map((w) => w.word)).toEqual(["c", "a"]);
  });
});
