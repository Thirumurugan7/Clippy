// E2E for the editor sidebar: caption preset, aspect change, AI prompt-edit,
// and an aspect-correct export — through the real browser UI.
import { chromium } from "playwright";

const VID = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
const errs = [];
p.on("pageerror", (e) => errs.push(e.message));
let pass = true;
const check = (c, m) => { if (!c) { pass = false; console.log("  ✗ " + m); } else console.log("  ✓ " + m); };

try {
  await p.goto(`http://localhost:5173/?v=${VID}`, { waitUntil: "networkidle" });
  await p.waitForSelector(".vert-canvas", { timeout: 20000 });
  console.log("1. editor loaded");

  // Captions: pick Hormozi
  await p.click(".side-icon:has-text('Captions')");
  await p.click(".cap-card:has-text('Hormozi')");
  await p.waitForTimeout(500);
  const note1 = await p.textContent(".preview-note");
  check(note1.includes("hormozi"), `caption preset applied (note: ${note1.trim()})`);

  // Crop: switch to 1:1
  await p.click(".side-icon:has-text('Crop')");
  await p.click(".aspect-card:has-text('Square post')");
  await p.waitForTimeout(500);
  const note2 = await p.textContent(".preview-note");
  const sq = await p.$eval(".vert-canvas", (c) => c.width === c.height);
  check(note2.includes("1:1"), `aspect set to 1:1 (note: ${note2.trim()})`);
  check(sq, "preview canvas became square");

  // AI edit: generate + apply
  await p.click(".side-icon:has-text('AI edit')");
  await p.fill(".ai-input", "make a 20s instagram reel of the best part");
  await p.click("button:has-text('Generate edit')");
  console.log("2. AI thinking (gemma4)…");
  await p.waitForSelector(".ai-result button:has-text('Apply to editor')", { timeout: 180000 });
  const proposal = await p.textContent(".ai-result .mono");
  console.log("   proposal:", proposal.trim());
  await p.click("button:has-text('Apply to editor')");
  await p.waitForTimeout(800);
  const clips = await p.$$eval(".timeline .clip", (e) => e.length);
  const note3 = await p.textContent(".preview-note");
  check(clips === 1, `AI applied -> timeline narrowed to the clip (${clips})`);
  check(note3.includes("9:16"), `AI set reel aspect 9:16 (note: ${note3.trim()})`);

  // Export the vertical short, assert it's portrait 9:16
  await p.click("button:has-text('Make 9:16 short')");
  console.log("3. exporting…");
  await p.waitForSelector(".vertical-result", { timeout: 180000 });
  await p.waitForFunction(() => { const v = document.querySelector(".vertical-result"); return v && v.videoHeight > 0; }, { timeout: 30000 });
  const dims = await p.$eval(".vertical-result", (v) => ({ w: v.videoWidth, h: v.videoHeight }));
  check(dims.h > dims.w, `export is portrait 9:16 (${dims.w}x${dims.h})`);

  await p.screenshot({ path: "/tmp/clipforge_sidebar_e2e.png" });
  console.log("pageerrors:", errs.length ? errs : "none");
  console.log(pass ? "RESULT: PASS" : "RESULT: FAIL");
  if (!pass) process.exitCode = 1;
} catch (e) {
  await p.screenshot({ path: "/tmp/clipforge_sidebar_e2e.png" }).catch(() => {});
  console.log("RESULT: FAIL ->", e.message);
  if (errs.length) console.log("pageerrors:", errs);
  process.exitCode = 1;
} finally {
  await b.close();
}
