import { describe, it, expect } from "vitest";
import { ASPECTS, CAPTION_PRESETS, resolveCaptionStyle } from "./presets.js";
import { computeCrop, targetDims } from "./crop.js";

describe("presets mirror", () => {
  it("aspects match backend dims", () => {
    expect(ASPECTS["9:16"].w).toBe(1080);
    expect(ASPECTS["9:16"].h).toBe(1920);
    expect(ASPECTS["16:9"].w).toBe(1920);
  });
  it("has >= 12 presets incl. hormozi (uppercase)", () => {
    expect(Object.keys(CAPTION_PRESETS).length).toBeGreaterThanOrEqual(12);
    expect(CAPTION_PRESETS.hormozi.uppercase).toBe(true);
  });
  it("resolve applies overrides", () => {
    const s = resolveCaptionStyle({ preset: "karaoke", fontsize: 70, color: "#00ff00", position: "center" });
    expect(s.fontsize).toBe(70);
    expect(s.primary).toBe("#00ff00");
    expect(s.position).toBe("center");
  });
});

describe("crop mirror", () => {
  it("target dims", () => {
    expect(targetDims("4:5")).toEqual([1080, 1350]);
  });
  it("landscape to 9:16 centered + clamps", () => {
    const [sx, sy, cw, ch] = computeCrop(1920, 1080, "9:16", 0.5);
    expect(ch).toBe(1080);
    expect(cw).toBe(Math.round((1080 * 9) / 16));
    expect(sy).toBe(0);
    const [sx0] = computeCrop(1920, 1080, "9:16", 0.0);
    expect(sx0).toBe(0);
  });
  it("16:9 is full width", () => {
    const [, , cw] = computeCrop(1920, 1080, "16:9", 0.5);
    expect(cw).toBe(1920);
  });
});
