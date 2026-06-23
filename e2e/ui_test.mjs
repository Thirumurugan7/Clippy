// Drives the REAL ClipForge UI in a browser: uploads a video through the file
// picker, waits for the worker to transcribe it, and verifies the transcript
// renders synced to the player (active-word highlight + click-to-seek).
import { chromium } from "playwright";
import path from "path";

const URL = "http://localhost:5173";
const VIDEO = path.resolve(process.argv[2]);
const SHOT = path.resolve(process.argv[3] || "/tmp/clipforge_ui.png");

function log(...a) {
  console.log(...a);
}

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});

try {
  await page.goto(URL, { waitUntil: "networkidle" });
  log("1. Loaded UI:", await page.title());

  // Upload through the actual <input type=file> + Upload button.
  await page.setInputFiles('input[type="file"]', VIDEO);
  log("2. Selected file in picker:", path.basename(VIDEO));
  await page.click("button:has-text('Upload')");

  // Wait for the success message the app shows on a real stored upload.
  await page.waitForSelector("text=/Stored\\. video_id=/", { timeout: 60000 });
  const stored = await page.textContent(".card p.mono");
  log("3. Upload accepted by backend ->", stored.trim());

  // Player should appear and load the streamed video.
  await page.waitForSelector("video", { timeout: 15000 });
  await page.waitForFunction(() => {
    const v = document.querySelector("video");
    return v && v.readyState >= 1 && v.duration > 0;
  }, { timeout: 30000 });
  const dur = await page.$eval("video", (v) => v.duration);
  log(`4. Video element loaded & seekable (duration=${dur.toFixed(2)}s via range streaming)`);

  // Wait for the worker (probe -> transcribe) to produce the transcript and the
  // UI to render words. Generous timeout: model load + transcription.
  log("5. Waiting for worker transcription + transcript render...");
  await page.waitForSelector(".transcript .word", { timeout: 360000 });
  const meta = await page.textContent(".card .mono:has-text('language=')");
  const wordCount = await page.$$eval(".transcript .word", (els) => els.length);
  log(`   transcript rendered: ${wordCount} words | ${meta.trim()}`);

  // ---- Verify SYNC: playback highlights the current word ----
  await page.$eval("video", (v) => {
    v.muted = true;
    v.currentTime = 1.0;
  });
  await page.$eval("video", (v) => v.play());
  await page.waitForFunction(
    () => document.querySelector(".transcript .word-active") !== null,
    { timeout: 8000 }
  );
  const activeWord = await page.textContent(".transcript .word-active");
  log(`6. SYNC OK: during playback the active word highlighted -> "${activeWord.trim()}"`);
  await page.$eval("video", (v) => v.pause());

  // ---- Verify SEEK: clicking a word moves the player to its start time ----
  const target = await page.$$eval(".transcript .word", (els) => {
    // pick word #8 and read its title "<start>s – <end>s"
    const el = els[8] || els[0];
    return { idx: els[8] ? 8 : 0, title: el.getAttribute("title"), text: el.textContent };
  });
  const wantStart = parseFloat(target.title);
  await page.click(`.transcript .word >> nth=${target.idx}`);
  await page.waitForTimeout(300);
  const curT = await page.$eval("video", (v) => v.currentTime);
  const seekOk = Math.abs(curT - wantStart) < 0.75;
  log(
    `7. SEEK ${seekOk ? "OK" : "MISMATCH"}: clicked word "${target.text.trim()}" ` +
      `(start≈${wantStart.toFixed(2)}s) -> video.currentTime=${curT.toFixed(2)}s`
  );

  await page.screenshot({ path: SHOT, fullPage: true });
  log("8. Screenshot saved:", SHOT);

  if (errors.length) log("BROWSER CONSOLE ERRORS:", errors);
  log(seekOk && wordCount > 0 ? "RESULT: PASS" : "RESULT: FAIL");
} catch (e) {
  await page.screenshot({ path: SHOT, fullPage: true }).catch(() => {});
  log("RESULT: FAIL ->", e.message);
  if (errors.length) log("BROWSER CONSOLE ERRORS:", errors);
  process.exitCode = 1;
} finally {
  await browser.close();
}
