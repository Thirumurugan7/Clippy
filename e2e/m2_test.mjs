// Drives the REAL ClipForge UI through the M2 flow: upload -> transcript ->
// mark a word for deletion + one-click filler detect -> export edited video ->
// confirm the exported (shorter) video plays back.
import { chromium } from "playwright";
import path from "path";

const URL = "http://localhost:5173";
const VIDEO = path.resolve(process.argv[2]);
const SHOT = path.resolve(process.argv[3] || "/tmp/clipforge_m2.png");

const log = (...a) => console.log(...a);
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

try {
  await page.goto(URL, { waitUntil: "networkidle" });
  log("1. Loaded UI");

  await page.setInputFiles('input[type="file"]', VIDEO);
  await page.click("button:has-text('Upload')");
  await page.waitForSelector("text=/Stored\\. video_id=/", { timeout: 60000 });
  log("2. Uploaded", path.basename(VIDEO));

  log("3. Waiting for transcript...");
  await page.waitForSelector(".transcript .word", { timeout: 360000 });
  const totalWords = await page.$$eval(".transcript .word", (e) => e.length);
  log(`   transcript rendered (${totalWords} words)`);

  // Turn on edit mode and mark the distinctive word "crazy".
  await page.click("button:has-text('Edit mode')");
  const crazyIdx = await page.$$eval(".transcript .word", (els) =>
    els.findIndex((e) => e.textContent.trim().toLowerCase() === "crazy")
  );
  if (crazyIdx < 0) throw new Error("word 'crazy' not found in transcript");
  await page.click(`.transcript .word >> nth=${crazyIdx}`);
  const crazyDeleted = await page.$$eval(".transcript .word", (els, i) =>
    els[i].className.includes("word-deleted"), crazyIdx);
  log(`4. Marked "crazy" for deletion -> strikethrough applied: ${crazyDeleted}`);

  // One-click filler detection.
  await page.click("button:has-text('Detect filler words')");
  await page.waitForTimeout(500);
  const deletedCount = await page.$$eval(".transcript .word-deleted", (e) => e.length);
  const deletedWords = await page.$$eval(".transcript .word-deleted", (els) =>
    els.map((e) => e.textContent.trim()));
  log(`5. After filler detect, ${deletedCount} words marked:`, deletedWords);

  // Export.
  await page.click("button:has-text('Export edited video')");
  log("6. Clicked Export; waiting for render...");
  await page.waitForSelector(".export-panel video", { timeout: 120000 });
  await page.waitForFunction(() => {
    const v = document.querySelector(".export-panel video");
    return v && v.readyState >= 1 && v.duration > 0;
  }, { timeout: 30000 });

  const exportText = await page.textContent(".export-panel .mono");
  const outDur = await page.$eval(".export-panel video", (v) => v.duration);
  const origDur = await page.$eval("video", (v) => v.duration); // first video = original
  log(`7. Export panel: ${exportText.trim()}`);
  log(`   original=${origDur.toFixed(2)}s  exported=${outDur.toFixed(2)}s`);

  // Confirm the exported video actually plays.
  await page.$eval(".export-panel video", (v) => { v.muted = true; v.currentTime = 1; });
  await page.$eval(".export-panel video", (v) => v.play());
  await page.waitForFunction(() => {
    const v = document.querySelector(".export-panel video");
    return v && !v.paused && v.currentTime > 1;
  }, { timeout: 8000 });
  log("8. Exported video plays back (currentTime advancing)");

  await page.screenshot({ path: SHOT, fullPage: true });
  const ok = outDur < origDur && deletedCount >= 2;
  log("9. Screenshot:", SHOT);
  if (errors.length) log("CONSOLE ERRORS:", errors);
  log(ok ? "RESULT: PASS" : "RESULT: FAIL");
  if (!ok) process.exitCode = 1;
} catch (e) {
  await page.screenshot({ path: SHOT, fullPage: true }).catch(() => {});
  log("RESULT: FAIL ->", e.message);
  if (errors.length) log("CONSOLE ERRORS:", errors);
  process.exitCode = 1;
} finally {
  await browser.close();
}
