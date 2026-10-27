// screenkit.js: screenshots and screen recordings in a browser, window or phone frame, presented in 3D, with eased
// zooms and scrolls, marker highlights, hand-drawn circles, boxes and arrows, headline pop-outs and focus blur.
// Built by screenkit.py; every call adds
// tweens to the page's paused GSAP timeline `tl` at an absolute time. Calls run in time order per screen, so sizes
// that depend on the zoom (stroke widths, blur radius) use the camera as of the latest zoom call.
const SK = (() => {
  const S = {}, NS = "http://www.w3.org/2000/svg";
  const $ = (id, sel) => document.querySelector("#" + id + " " + sel);
  const clampv = (v, a, b) => Math.min(b, Math.max(a, v));
  const FULL = "inset(0px 0px 0px 0px round 0px)", CLEAR = "blur(0px) brightness(1) saturate(1)";

  // where the page sits for a region (r = [x, y, w, h] in source px), or the top of the page when r is null
  function camFor(s, r, pad, zmax) {
    const { sw, sh } = s.o;
    let z = s.k0, cx = sw / 2, cy;
    if (r) {
      z = clampv(Math.min(s.vw * (1 - 2 * pad) / r[2], s.vh * (1 - 2 * pad) / r[3]), s.k0, s.k0 * zmax);
      cx = r[0] + r[2] / 2; cy = r[1] + r[3] / 2;
    } else cy = s.vh / (2 * z);
    const pw = sw * z, ph = sh * z;
    let x = s.vw / 2 - cx * z, y = s.vh / 2 - cy * z;
    x = pw <= s.vw ? (s.vw - pw) / 2 : clampv(x, s.vw - pw, 0);
    y = ph <= s.vh ? (s.vh - ph) / 2 : clampv(y, s.vh - ph, 0);
    return { x, y, s: z };
  }
  const px = (s, v) => v / s.cam.s;     // screen px -> source px at the current zoom

  function init(id, o) {
    const s = { id, o, el: document.getElementById(id), card: $(id, ".sk-card"), fl: $(id, ".sk-float"), view: $(id, ".sk-view"),
      page: $(id, ".sk-page"), base: $(id, ".sk-base"), sharp: $(id, ".sk-sharp"), mark: $(id, ".sk-mark"), ink: $(id, ".sk-ink"),
      vig: $(id, ".sk-vig"), n: 0, clip: FULL, flt: CLEAR, ring: null };
    s.vw = s.view.clientWidth; s.vh = s.view.clientHeight;
    s.k0 = o.fit === "contain" ? Math.min(s.vw / o.sw, s.vh / o.sh) : o.fit === "height" ? s.vh / o.sh : s.vw / o.sw;
    s.cam = camFor(s, null, 0, 1);
    s.pose = o.tilt.slice();
    gsap.set(s.page, { x: s.cam.x, y: s.cam.y, scale: s.cam.s, transformOrigin: "0 0" });
    gsap.set(s.card, { rotationX: s.pose[0], rotationY: s.pose[1], rotationZ: s.pose[2] });
    gsap.set([s.base, s.sharp], { width: o.sw, height: o.sh });
    for (const g of [s.mark, s.ink]) { g.setAttribute("viewBox", `0 0 ${o.sw} ${o.sh}`); g.setAttribute("width", o.sw); g.setAttribute("height", o.sh); }
    S[id] = s;
  }

  // ---- in, out, pose ----
  function enter(id, t, style = "tilt") {
    const s = S[id], p = s.pose;
    tl.fromTo(s.el, { opacity: 0, filter: "blur(12px)" }, { opacity: 1, filter: "blur(0px)", duration: .55, ease: "power2.out" }, t);
    if (style === "tilt") tl.fromTo(s.card, { rotationX: p[0] + 16, rotationY: p[1] - 24, rotationZ: p[2], y: 90, scale: .92 },
      { rotationX: p[0], rotationY: p[1], rotationZ: p[2], y: 0, scale: 1, duration: 1.0, ease: "power3.out" }, t);
    else if (style === "rise") tl.fromTo(s.card, { y: 80, scale: .96 }, { y: 0, scale: 1, duration: .8, ease: "power3.out" }, t);
    else if (style === "snap") tl.fromTo(s.card, { scale: 1.06, filter: "brightness(1.9)" }, { scale: 1, filter: "brightness(1)", duration: .55, ease: "power3.out" }, t);
    else tl.fromTo(s.card, { scale: .82 }, { scale: 1, duration: .8, ease: "back.out(1.4)" }, t);
  }
  function exit(id, t) { tl.to(S[id].el, { opacity: 0, y: -20, filter: "blur(10px)", duration: .45, ease: "power2.in" }, t); }
  function tilt(id, t, pose, o = {}) {
    const s = S[id]; s.pose = pose.slice();
    tl.to(s.card, { rotationX: pose[0], rotationY: pose[1], rotationZ: pose[2], duration: o.dur ?? 1.0, ease: o.ease ?? "power3.inOut" }, t);
  }
  function float(id, t0, t1, amp = 7, period = 2.8) {
    const halves = Math.max(1, Math.floor((t1 - t0) / (period / 2)));
    tl.fromTo(S[id].fl, { y: -amp / 2 }, { y: amp / 2, duration: period / 2, yoyo: true, repeat: halves - 1, ease: "sine.inOut", immediateRender: false }, t0);
  }

  // ---- camera ----
  function zoom(id, t, r, o = {}) {
    const s = S[id]; s.cam = camFor(s, r, o.pad ?? .14, o.zmax ?? 3.2);
    tl.to(s.page, { x: s.cam.x, y: s.cam.y, scale: s.cam.s, duration: o.dur ?? 1.1, ease: o.ease ?? "power3.inOut" }, t);
  }
  function reset(id, t, o = {}) {
    const s = S[id]; s.cam = camFor(s, null, 0, 1);
    tl.to(s.page, { x: s.cam.x, y: s.cam.y, scale: s.cam.s, duration: o.dur ?? 1.0, ease: o.ease ?? "power3.inOut" }, t);
  }
  function scroll(id, t, y, o = {}) {       // bring source y to about a fifth of the way down the view
    const s = S[id], z = s.cam.s;
    s.cam = { ...s.cam, y: clampv(-y * z + s.vh * (o.at ?? .2), Math.min(0, s.vh - s.o.sh * z), 0) };
    tl.to(s.page, { y: s.cam.y, duration: o.dur ?? 1.6, ease: o.ease ?? "power2.inOut" }, t);
  }

  // ---- ink ----
  function mk(g, tag, attrs) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); g.appendChild(e); return e; }
  function drawIn(e, t, d, ease = "power2.inOut") {
    const n = e.getTotalLength(); gsap.set(e, { strokeDasharray: n + " " + n, strokeDashoffset: n, opacity: 0 });
    tl.set(e, { opacity: 1 }, t);                // a round cap would show as a dot before the stroke draws
    tl.to(e, { strokeDashoffset: 0, duration: d, ease }, t); return e;
  }
  const gone = (e, t) => { if (t != null) tl.to(e, { opacity: 0, duration: .35 }, t); };
  const stroke = (s, o, w) => ({ fill: "none", stroke: o.color ?? "__ACC__", "stroke-width": px(s, o.width ?? w), "stroke-linecap": "round",
    "stroke-linejoin": "round", style: "filter:drop-shadow(0 2px 6px rgba(0,0,0,.28))" });

  function highlight(id, t, rects, o = {}) {      // marker sweep, one bar per line of the passage
    const s = S[id], list = Array.isArray(rects[0]) ? rects : [rects];
    const col = o.color ?? (s.o.dark ? "rgba(__ACC2RGB__,.42)" : "rgba(__MARKRGB__,.55)"), ex = px(s, 6);
    list.forEach((r, i) => {
      const e = mk(s.mark, "rect", { x: r[0] - ex, y: r[1] - px(s, 1), width: 0, height: r[3] + px(s, 3), rx: px(s, 5), fill: col });
      tl.to(e, { attr: { width: r[2] + 2 * ex }, duration: o.dur ?? .42, ease: "power2.inOut" }, t + i * (o.stagger ?? .24));
      gone(e, o.until);
    });
  }
  function underline(id, t, r, o = {}) {
    const s = S[id], y = r[1] + r[3] + px(s, 6), wv = px(s, 3);
    const e = mk(s.ink, "path", { d: `M${r[0]} ${y} C${r[0] + r[2] * .3} ${y + wv} ${r[0] + r[2] * .7} ${y - wv} ${r[0] + r[2]} ${y}`, ...stroke(s, o, 5) });
    drawIn(e, t, o.dur ?? .5); gone(e, o.until);
  }
  function circle(id, t, r, o = {}) {           // hand-drawn: slightly wobbly, the end overshoots the start
    const s = S[id], pad = px(s, o.pad ?? 18), cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2, rx = r[2] / 2 + pad, ry = r[3] / 2 + pad * .9;
    const seed = (++s.n) * 1.7, N = 72, a0 = -2.2, span = 2 * Math.PI + .5, rot = (o.rot ?? -2.5) * Math.PI / 180, pts = [];
    for (let k = 0; k <= N; k++) {
      const a = a0 + span * k / N, w = 1 + .035 * Math.sin(3 * a + seed) + .018 * Math.sin(7 * a + 2 * seed) + .05 * k / N;
      const x = rx * w * Math.cos(a), y = ry * w * Math.sin(a);
      pts.push((cx + x * Math.cos(rot) - y * Math.sin(rot)).toFixed(1) + " " + (cy + x * Math.sin(rot) + y * Math.cos(rot)).toFixed(1));
    }
    drawIn(mk(s.ink, "path", { d: "M" + pts.join(" L"), ...stroke(s, o, 6) }), t, o.dur ?? .65);
    gone(s.ink.lastChild, o.until);
  }
  function box(id, t, r, o = {}) {
    const s = S[id], p = px(s, o.pad ?? 10), c = px(s, 12), x0 = r[0] - p, y0 = r[1] - p, x1 = r[0] + r[2] + p, y1 = r[1] + r[3] + p;
    const d = `M${x0 + c} ${y0} H${x1 - c} Q${x1} ${y0} ${x1} ${y0 + c} V${y1 - c} Q${x1} ${y1} ${x1 - c} ${y1} H${x0 + c} Q${x0} ${y1} ${x0} ${y1 - c} V${y0 + c} Q${x0} ${y0} ${x0 + c} ${y0}`;
    drawIn(mk(s.ink, "path", { d, ...stroke(s, o, 4) }), t, o.dur ?? .6); gone(s.ink.lastChild, o.until);
  }
  function arrow(id, t, r, o = {}) {
    const s = S[id], side = o.from ?? "left", g = px(s, 14), L = px(s, o.len ?? 230);
    let ex = r[0] - g, ey = r[1] + r[3] / 2, sx = ex - L, sy = ey + L * .45;
    if (side === "right") { ex = r[0] + r[2] + g; sx = ex + L; }
    if (side === "top") { ex = r[0] + r[2] / 2; ey = r[1] - g; sx = ex - L * .45; sy = ey - L; }
    if (side === "bottom") { ex = r[0] + r[2] / 2; ey = r[1] + r[3] + g; sx = ex - L * .45; sy = ey + L; }
    const qx = (sx + ex) / 2 + (ey - sy) * .25, qy = (sy + ey) / 2 - (ex - sx) * .25, an = Math.atan2(ey - qy, ex - qx), hl = px(s, 24);
    const shaft = mk(s.ink, "path", { d: `M${sx} ${sy} Q${qx} ${qy} ${ex} ${ey}`, ...stroke(s, o, 6) });
    const head = mk(s.ink, "path", { d: `M${ex - hl * Math.cos(an - .5)} ${ey - hl * Math.sin(an - .5)} L${ex} ${ey} L${ex - hl * Math.cos(an + .5)} ${ey - hl * Math.sin(an + .5)}`, ...stroke(s, o, 6) });
    drawIn(shaft, t, o.dur ?? .5); drawIn(head, t + (o.dur ?? .5) - .08, .18, "power2.out");
    gone(shaft, o.until); gone(head, o.until);
  }

  // ---- focus: everything outside the region blurs and dims; a thin ring marks the edge ----
  function focus(id, t, r, o = {}) {
    const s = S[id], pad = px(s, o.pad ?? 16), rr = px(s, o.radius ?? 14), d = o.dur ?? .7;
    const ins = [r[1] - pad, s.o.sw - r[0] - r[2] - pad, s.o.sh - r[1] - r[3] - pad, r[0] - pad].map(v => Math.max(0, v).toFixed(1) + "px");
    const clip = `inset(${ins.join(" ")} round ${rr.toFixed(1)}px)`;
    const flt = `blur(${px(s, o.blur ?? 7).toFixed(2)}px) brightness(${o.dim ?? .5}) saturate(.85)`;
    tl.fromTo(s.sharp, { clipPath: s.clip }, { clipPath: clip, duration: d, ease: "power3.inOut", immediateRender: false }, t);
    tl.fromTo(s.base, { filter: s.flt }, { filter: flt, duration: d, ease: "power2.inOut", immediateRender: false }, t);
    s.clip = clip; s.flt = flt;
    if (s.ring) { tl.to(s.ring, { opacity: 0, duration: .25 }, t); s.ring = null; }
    if (o.ring !== false) {
      const x0 = r[0] - pad, y0 = r[1] - pad;
      s.ring = mk(s.ink, "rect", { x: x0, y: y0, width: r[2] + 2 * pad, height: r[3] + 2 * pad, rx: rr, fill: "none",
        stroke: "rgba(__ACC2RGB__,.85)", "stroke-width": px(s, 2.5), opacity: 0 });
      tl.to(s.ring, { opacity: 1, duration: .4 }, t + d * .6);
    }
  }
  function unfocus(id, t, o = {}) {
    const s = S[id], d = o.dur ?? .6;
    tl.fromTo(s.sharp, { clipPath: s.clip }, { clipPath: FULL, duration: d, ease: "power3.inOut", immediateRender: false }, t);
    tl.fromTo(s.base, { filter: s.flt }, { filter: CLEAR, duration: d, ease: "power2.inOut", immediateRender: false }, t);
    s.clip = FULL; s.flt = CLEAR;
    if (s.ring) { tl.to(s.ring, { opacity: 0, duration: .3 }, t); s.ring = null; }
  }
  function edges(id, t, on = true, o = {}) {     // soft blur and shade on the outer edges of the whole view
    tl.to(S[id].vig, { opacity: on ? 1 : 0, duration: o.dur ?? .6, ease: "power2.inOut" }, t);
  }

  // ---- pop-out: the region lifts off the page (images only) ----
  function popout(id, t, r, o = {}) {
    const s = S[id];
    if (s.o.kind !== "image") return focus(id, t, r, o);
    const d = document.createElement("div"); d.className = "sk-pop";
    Object.assign(d.style, { left: r[0] + "px", top: r[1] + "px", width: r[2] + "px", height: r[3] + "px", borderRadius: px(s, 10) + "px" });
    const im = document.createElement("img"); im.src = s.o.src;
    Object.assign(im.style, { position: "absolute", left: -r[0] + "px", top: -r[1] + "px", width: s.o.sw + "px", height: s.o.sh + "px", maxWidth: "none" });
    d.appendChild(im); s.page.insertBefore(d, s.ink);
    if (o.dim !== false) focus(id, t, r, { blur: 2.5, dim: .62, ring: false, pad: 0, radius: 10, dur: .5 });
    tl.set(d, { opacity: 1 }, t);
    tl.fromTo(d, { scale: 1, boxShadow: "0px 0px 0px rgba(0,0,0,0)" },
      { scale: o.scale ?? 1.12, boxShadow: `0px ${px(s, 22)}px ${px(s, 56)}px rgba(0,0,0,.45)`, duration: .6, ease: "back.out(1.7)", immediateRender: false }, t);
    if (o.until != null) {
      tl.to(d, { scale: 1, boxShadow: "0px 0px 0px rgba(0,0,0,0)", duration: .45, ease: "power2.inOut" }, o.until);
      tl.set(d, { opacity: 0 }, o.until + .45);
      if (o.dim !== false) unfocus(id, o.until, { dur: .45 });
    }
  }

  return { init, enter, exit, tilt, float, zoom, reset, scroll, highlight, underline, circle, box, arrow, focus, unfocus, edges, popout, S };
})();
