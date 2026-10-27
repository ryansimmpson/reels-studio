#!/usr/bin/env node
// capture.mjs: screenshot a web page for a screen figure, and measure where its text sits.
//
//   node capture.mjs <url> <out.png> [--w 1440] [--h 900] [--dpr 2] [--full] [--max-h 9000] [--scroll Y]
//        [--wait 1500] [--find "phrase"]... [--select "css"]... [--hide "css,css"] [--clip "css"] [--dark]
//        [--click "Monthly"]...
//
// Writes out.png and out.json: {url, title, viewport, dpr, size: [W, H], finds: {phrase: [[x, y, w, h], ...] per
// match}, selects: {css: [x, y, w, h] per element}}. Rects are PNG pixels, top-left origin. A phrase gets one rect per
// line it covers, so a three-line passage gives three rects (screenkit highlights each line).
// --full takes the whole page (up to --max-h CSS px) for scrolling figures; --clip takes one element (an article).
// --click presses a toggle or tab by its visible text (a Monthly/Yearly switch, a pricing tab) before the shot. It only
// touches buttons, tabs and radios: never links, inputs or anything that submits, and never consent banners.
// Consent and cookie banners are hidden with CSS, never clicked. Uses the Chrome that HyperFrames installed.
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const GFX = process.env.REELS_GFX || path.join(process.env.REELS_HOME || path.join(os.homedir(), "reels-studio"), "_graphics");
const puppeteer = createRequire(path.join(GFX, "package.json"))("puppeteer-core");

const argv = process.argv.slice(2), pos = [], opt = { find: [], select: [], click: [] };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith("--")) { pos.push(a); continue; }
  const k = a.slice(2);
  if (["full", "dark"].includes(k)) opt[k] = true;
  else if (k === "find" || k === "select" || k === "click") opt[k].push(argv[++i]);
  else opt[k] = argv[++i];
}
if (pos.length < 2) { console.error("usage: node capture.mjs <url> <out.png> [--w 1440 --h 900 --dpr 2 --full --find \"phrase\" ...]"); process.exit(1); }
const [url, out] = pos, W = +(opt.w || 1440), H = +(opt.h || 900), DPR = +(opt.dpr || 2), MAXH = +(opt["max-h"] || 9000);

function chrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const base = path.join(os.homedir(), ".cache/hyperframes/chrome/chrome-headless-shell");
  try {
    for (const v of fs.readdirSync(base).sort().reverse()) {
      for (const plat of ["mac-arm64", "mac-x64"]) {
        const p = path.join(base, v, `chrome-headless-shell-${plat}`, "chrome-headless-shell");
        if (fs.existsSync(p)) return p;
      }
    }
  } catch {}
  return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
}

const HIDE = ["#onetrust-banner-sdk", "#onetrust-consent-sdk", "#CybotCookiebotDialog", ".fc-consent-root", ".cc-window",
  "#usercentrics-root", "#didomi-host", ".qc-cmp2-container", "#truste-consent-track", "[id*='cookie-banner' i]",
  "[class*='cookie-banner' i]", "[class*='cookiebanner' i]", "[id*='consent-banner' i]", "[class*='consent-banner' i]",
  "[role='dialog'][aria-label*='cookie' i]", "[role='dialog'][aria-label*='consent' i]"];

const exe = chrome();
const browser = await puppeteer.launch({ executablePath: exe, headless: exe.includes("headless-shell") ? "shell" : true,
  args: ["--hide-scrollbars", "--force-color-profile=srgb", "--font-render-hinting=none"] });
try {
  const page = await browser.newPage();
  await page.setUserAgent((await browser.userAgent()).replace("HeadlessChrome", "Chrome"));
  await page.setViewport({ width: W, height: H, deviceScaleFactor: DPR });
  if (opt.dark) await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
  await page.goto(url, { waitUntil: "networkidle2", timeout: 45000 }).catch(e => console.error("load:", e.message));
  const hide = [...HIDE, ...(opt.hide ? opt.hide.split(",") : [])];
  await page.addStyleTag({ content: `${hide.join(",")}{display:none!important}html{scroll-behavior:auto!important}` });
  for (const label of opt.click) {
    const ok = await page.evaluate(label => {
      const want = label.trim().toLowerCase();
      const els = [...document.querySelectorAll("button:not([type=submit]), [role=button], [role=tab], [role=radio], [role=switch]")]
        .filter(e => e.closest("form") === null && (e.innerText || e.getAttribute("aria-label") || "").trim().toLowerCase() === want);
      if (!els.length) return false;
      els[0].click(); return true;
    }, label);
    console.log(`  click ${JSON.stringify(label)}: ${ok ? "ok" : "NOT FOUND"}`);
    await new Promise(r => setTimeout(r, 700));
  }
  if (opt.full) {    // walk the page once so lazy images load, then back to the top
    await page.evaluate(async maxH => {
      for (let y = 0; y < Math.min(document.documentElement.scrollHeight, maxH); y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 140)); }
      window.scrollTo(0, 0);
    }, MAXH);
  } else if (opt.scroll) await page.evaluate(y => window.scrollTo(0, y), +opt.scroll);
  await new Promise(r => setTimeout(r, +(opt.wait || 1500)));

  const m = await page.evaluate((finds, selects, clipSel) => {
    const doc = r => [r.left + scrollX, r.top + scrollY, r.width, r.height];
    const seen = n => { const e = n.parentElement; if (!e || !n.nodeValue.trim()) return false; const cs = getComputedStyle(e);
      return cs.visibility !== "hidden" && cs.display !== "none" && e.getClientRects().length > 0; };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = []; let flat = "";
    for (let n = walker.nextNode(); n; n = walker.nextNode()) if (seen(n)) { nodes.push({ n, s: flat.length }); flat += n.nodeValue + " "; }
    const at = off => { let lo = 0, hi = nodes.length - 1;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (nodes[mid].s <= off) lo = mid; else hi = mid - 1; }
      const k = nodes[lo]; return [k.n, Math.max(0, Math.min(off - k.s, k.n.nodeValue.length))]; };
    const lines = rs => {      // merge a range's client rects into one box per line
      const out = [];
      for (const r of rs.filter(r => r.width > 1 && r.height > 1).sort((a, b) => a.top - b.top || a.left - b.left)) {
        const l = out.find(o => Math.abs((o.top + o.bottom) / 2 - (r.top + r.bottom) / 2) < Math.min(o.bottom - o.top, r.height) * .5);
        if (l) { l.left = Math.min(l.left, r.left); l.right = Math.max(l.right, r.right); l.top = Math.min(l.top, r.top); l.bottom = Math.max(l.bottom, r.bottom); }
        else out.push({ left: r.left, right: r.right, top: r.top, bottom: r.bottom });
      }
      return out.map(o => [o.left + scrollX, o.top + scrollY, o.right - o.left, o.bottom - o.top]);
    };
    const res = { finds: {}, selects: {}, title: document.title, docW: document.documentElement.scrollWidth, docH: document.documentElement.scrollHeight };
    for (const ph of finds) {
      const re = new RegExp(ph.trim().split(/\s+/).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/-/g, "-\\s*")).join("\\s+"), "gi");
      const hits = []; let mt;
      while ((mt = re.exec(flat)) && hits.length < 6) {
        const r = document.createRange(), [a, ao] = at(mt.index), [b, bo] = at(mt.index + mt[0].length);
        r.setStart(a, ao); r.setEnd(b, bo);
        const ls = lines([...r.getClientRects()]); if (ls.length) hits.push(ls);
      }
      res.finds[ph] = hits;
    }
    for (const sel of selects) res.selects[sel] = [...document.querySelectorAll(sel)].slice(0, 12).map(e => doc(e.getBoundingClientRect())).filter(r => r[2] > 0 && r[3] > 0);
    res.clip = clipSel ? doc(document.querySelector(clipSel).getBoundingClientRect()) : null;
    res.scroll = [scrollX, scrollY];
    return res;
  }, opt.find, opt.select, opt.clip || null);

  // the captured area, in document CSS px
  let area;
  if (m.clip) area = { x: m.clip[0], y: m.clip[1], width: m.clip[2], height: Math.min(m.clip[3], MAXH) };
  else if (opt.full) area = { x: 0, y: 0, width: W, height: Math.min(m.docH, MAXH) };
  else area = { x: m.scroll[0], y: m.scroll[1], width: W, height: H };
  await page.screenshot({ path: out, type: "png", clip: area, captureBeyondViewport: true });

  const px = r => [r[0] - area.x, r[1] - area.y, r[2], r[3]].map(v => Math.round(v * DPR));
  const inside = r => r[1] + r[3] > 0 && r[1] < area.height * DPR && r[0] + r[2] > 0 && r[0] < area.width * DPR;
  const finds = {}, selects = {};
  for (const [k, hits] of Object.entries(m.finds)) finds[k] = hits.map(h => h.map(px).filter(inside)).filter(h => h.length);
  for (const [k, rs] of Object.entries(m.selects)) selects[k] = rs.map(px).filter(inside);
  const head = fs.readFileSync(out).subarray(16, 24);
  const meta = { url, title: m.title, viewport: [W, H], dpr: DPR, size: [head.readUInt32BE(0), head.readUInt32BE(4)], finds, selects };
  fs.writeFileSync(out.replace(/\.png$/i, "") + ".json", JSON.stringify(meta, null, 1));
  console.log(`${out}  ${meta.size[0]}x${meta.size[1]}  "${m.title}"`);
  for (const [k, v] of Object.entries(finds)) console.log(`  find ${JSON.stringify(k)}: ${v.length ? v.map(h => h.length + " line(s)").join(", ") : "NOT FOUND"}`);
  for (const [k, v] of Object.entries(selects)) console.log(`  select ${JSON.stringify(k)}: ${v.length} match(es)`);
} finally {
  await browser.close();
}
