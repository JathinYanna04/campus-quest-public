// Low-res canvas effects scaled up with image-rendering: pixelated.
import { pal } from './palette.js';

// CSS px per fx pixel: 3 on phones, chunkier on big screens
const scale = () => Math.max(3, Math.round(Math.min(window.innerWidth, window.innerHeight) / 150));

function makeCanvas(cls) {
  const c = document.createElement('canvas');
  c.className = `px-canvas ${cls}`;
  return c;
}

function fit(c) {
  const w = Math.max(1, Math.ceil(window.innerWidth / scale()));
  const h = Math.max(1, Math.ceil(window.innerHeight / scale()));
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return [w, h];
}

const CONFETTI_COLS = ['coral', 'yellow', 'mint', 'sky', 'lilac', 'pink', 'pink-pale', 'orange', 'grass-light'];

function spawn(w, h, fromTop, burst) {
  const petal = Math.random() < 0.3;
  const p = {
    x: Math.random() * w,
    y: fromTop ? Math.random() * h : Math.random() * -20,
    vx: (Math.random() - 0.5) * 0.3,
    vy: 0.25 + Math.random() * 0.35,
    ph: Math.random() * Math.PI * 2,
    sway: 0.3 + Math.random() * 0.6,
    petal,
    col: pal(petal ? (Math.random() < 0.5 ? 'pink-pale' : 'pink') : CONFETTI_COLS[(Math.random() * CONFETTI_COLS.length) | 0]),
    big: Math.random() < 0.4,
  };
  if (burst) {
    p.x = w / 2 + (Math.random() - 0.5) * w * 0.2;
    p.y = h * 0.55;
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 2.2;
    const s = 1.5 + Math.random() * 2.8;
    p.vx = Math.cos(a) * s;
    p.vy = Math.sin(a) * s;
    p.burst = true;
  }
  return p;
}

function drawP(g, p, t) {
  const x = Math.round(p.x), y = Math.round(p.y);
  g.fillStyle = p.col;
  if (p.petal) {
    // tiny 3x2 petal that flips
    if (Math.sin(t / 300 + p.ph) > 0) { g.fillRect(x, y, 2, 1); g.fillRect(x + 1, y + 1, 2, 1); }
    else { g.fillRect(x + 1, y, 2, 1); g.fillRect(x, y + 1, 2, 1); }
  } else {
    const flip = Math.sin(t / 180 + p.ph);
    const wpx = p.big ? 2 : 1;
    if (flip > 0.3) g.fillRect(x, y, wpx, 2);
    else if (flip < -0.3) g.fillRect(x, y, 2, wpx);
    else g.fillRect(x, y, 1, 1);
  }
}

/**
 * Falling ambient confetti + petals. Returns { el, stop() }.
 * mode 'fall' loops forever; 'burst' explodes once then rains for ms.
 */
export function particles(parent, { mode = 'fall', count = 60, ms = 3000 } = {}) {
  const c = makeCanvas(mode === 'burst' ? 'fx-burst' : 'fx-fall');
  parent.appendChild(c);
  const g = c.getContext('2d');
  let [w, h] = fit(c);
  let ps = [];
  for (let i = 0; i < count; i++) ps.push(spawn(w, h, mode === 'fall', mode === 'burst'));
  let raf = 0, running = true;
  const t0 = performance.now();
  let last = t0;
  const onResize = () => { [w, h] = fit(c); };
  window.addEventListener('resize', onResize);
  const frame = (now) => {
    if (!running) return;
    const dt = Math.min(3, (now - last) / 16.67);
    last = now;
    if (document.hidden) { raf = requestAnimationFrame(frame); return; }
    g.clearRect(0, 0, w, h);
    const age = now - t0;
    const ending = mode === 'burst' && age > ms;
    for (const p of ps) {
      if (p.burst) {
        p.vy += 0.06 * dt;
        p.vx *= 0.98;
        if (p.vy > 0.6) { p.burst = false; p.vy = 0.4 + Math.random() * 0.3; }
        p.x += p.vx * dt; p.y += p.vy * dt;
      } else {
        p.x += (p.vx + Math.sin(now / 600 + p.ph) * p.sway * 0.3) * dt;
        p.y += p.vy * dt;
      }
      if (p.y > h + 4 && !ending) Object.assign(p, spawn(w, h, false, false));
      drawP(g, p, now);
    }
    if (ending) ps = ps.filter((p) => p.y <= h + 4);
    if (ending && ps.length === 0) { stop(); return; }
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  function stop() {
    if (!running) return;
    running = false;
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', onResize);
    c.remove();
  }
  return { el: c, stop };
}

/** Pixel iris wipe. dir 'out' closes to ink, 'in' opens. Resolves after ~400ms. */
export function iris(parent, dir, existing) {
  return new Promise((resolve) => {
    const c = existing || makeCanvas('fx-iris');
    if (!existing) parent.appendChild(c);
    const S = 6;
    const w = Math.ceil(window.innerWidth / S), h = Math.ceil(window.innerHeight / S);
    c.width = w; c.height = h;
    const g = c.getContext('2d');
    const R = Math.hypot(w, h) / 2 + 1;
    const STEPS = 10, DUR = 400;
    const ink = pal('ink');
    const draw = (k) => { // k: 0 open .. 1 closed
      g.fillStyle = ink;
      g.fillRect(0, 0, w, h);
      const r = Math.round(R * (1 - k));
      if (r <= 0) return;
      g.globalCompositeOperation = 'destination-out';
      const cx = Math.floor(w / 2), cy = Math.floor(h / 2);
      for (let y = -r; y <= r; y++) {
        const half = Math.floor(Math.sqrt(r * r - y * y));
        g.fillRect(cx - half, cy + y, half * 2 + 1, 1);
      }
      g.globalCompositeOperation = 'source-over';
    };
    const t0 = performance.now();
    let lastStep = -1;
    const frame = (now) => {
      const step = Math.min(STEPS, Math.floor(((now - t0) / DUR) * STEPS));
      if (step !== lastStep) {
        lastStep = step;
        const k = step / STEPS;
        draw(dir === 'out' ? k : 1 - k);
      }
      if (step >= STEPS) { resolve(c); return; }
      requestAnimationFrame(frame);
    };
    draw(dir === 'out' ? 0 : 1);
    requestAnimationFrame(frame);
    // rAF pauses in background tabs: never leave the promise hanging.
    setTimeout(() => { if (lastStep < STEPS) { lastStep = STEPS; draw(dir === 'out' ? 1 : 0); resolve(c); } }, DUR + 400);
  });
}
