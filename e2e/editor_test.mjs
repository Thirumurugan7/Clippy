// E2E for the non-destructive editor through the REAL browser UI:
//   live transcript-delete (no export) -> reorder reflected in transcript ->
//   persistence across reload -> export of the edited EDL.
import { chromium } from "playwright";
import path from "path";

const URL = "http://localhost:5173";
const VIDEO = path.resolve(process.argv[2]);
const SHOT = path.resolve(process.argv[3] || "/tmp/clipforge_editor.png");

const log = (...a) => console.log(...a);
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

const wordsText = () =>
  page.$$eval(".transcript .word", (els) => els.map((e) => e.textContent.trim()));
const clipCount = () => page.$$eval(".timeline .clip", (e) => e.length);

let pass = true;
const check = (cond, msg) => { if (!cond) { pass = false; log("   ✗ " + msg); } else log("   ✓ " + msg); };

try {
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.setInputFiles('input[type="file"]', VIDEO);
  await page.click("button:has-text('Upload')");
  log("1. Uploaded", path.basename(VIDEO));

  await page.waitForSelector(".transcript .word", { timeout: 360000 });
  await page.waitForSelector(".timeline .clip", { timeout: 10000 });
  await page.waitForSelector(".clip .wave", { timeout: 15000 });
  const wordsBefore = await wordsText();
  const clipsBefore = await clipCount();
  log(`2. Editor ready: ${wordsBefore.length} words, ${clipsBefore} clip(s), waveform drawn`);

  // --- live transcript delete (no export) ---
  await page.locator(".transcript .word", { hasText: "crazy" }).first().dblclick();
  await page.locator(".transcript").focus();
  await page.keyboard.press("Delete");
  await page.waitForTimeout(400);
  const wordsAfter = await wordsText();
  const clipsAfter = await clipCount();
  log(`3. Deleted "crazy" in transcript -> ${wordsAfter.length} words, ${clipsAfter} clips`);
  check(!wordsAfter.includes("crazy"), 'live edit: "crazy" removed from transcript');
  check(wordsAfter.length < wordsBefore.length, "live edit: word count decreased");
  check(clipsAfter > clipsBefore, "live edit: clip split around the cut");
  check((await page.$(".export-panel")) === null, "live edit happened WITHOUT export");

  // --- reorder reflected in transcript ---
  const firstBefore = (await wordsText())[0];
  await page.locator(".timeline .clip").nth(0).dragTo(page.locator(".timeline .clip").nth(1));
  await page.waitForTimeout(400);
  const firstAfter = (await wordsText())[0];
  log(`4. Reordered clips -> transcript first word "${firstBefore}" => "${firstAfter}"`);
  check(firstAfter !== firstBefore, "reorder: transcript order updated to match timeline");

  // --- persistence across reload (autosave) ---
  await page.waitForTimeout(900); // let debounced autosave flush
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".transcript .word", { timeout: 20000 });
  const wordsReload = await wordsText();
  log(`5. Reloaded -> ${wordsReload.length} words, ${await clipCount()} clips`);
  check(!wordsReload.includes("crazy"), "persistence: edit survived reload");

  // --- export the edited EDL ---
  await page.click("button:has-text('Export edited video')");
  await page.waitForSelector(".export-panel video", { timeout: 120000 });
  await page.waitForFunction(() => {
    const v = document.querySelector(".export-panel video");
    return v && v.readyState >= 1 && v.duration > 0;
  }, { timeout: 30000 });
  const exportText = await page.textContent(".export-panel .mono");
  log(`6. Export: ${exportText.trim()}`);
  const m = exportText.match(/([\d.]+)s\s*→\s*([\d.]+)s\s*\((\d+) segments\)/);
  check(!!m, "export reports original→output and a segment count");
  if (m) {
    check(Number(m[2]) < Number(m[1]), `export shorter than original (${m[2]}s < ${m[1]}s)`);
    check(Number(m[3]) >= 2, `export has the edited segment count (${m[3]})`);
  }

  await page.screenshot({ path: SHOT, fullPage: true });
  log("7. Screenshot:", SHOT);
  if (errors.length) log("CONSOLE ERRORS:", errors);
  log(pass ? "RESULT: PASS" : "RESULT: FAIL");
  if (!pass) process.exitCode = 1;
} catch (e) {
  await page.screenshot({ path: SHOT, fullPage: true }).catch(() => {});
  log("RESULT: FAIL ->", e.message);
  if (errors.length) log("CONSOLE ERRORS:", errors);
  process.exitCode = 1;
} finally {
  await browser.close();
}
