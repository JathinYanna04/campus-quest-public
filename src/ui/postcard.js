// Birthday keepsake postcard: drawn on a 180x320 canvas in palette colours,
// then scaled 3x with nearest-neighbour to a crisp 540x960 PNG.
// Pure canvas: the caller hands in already-loaded images.
import { pal } from './palette.js';

export const POSTCARD_W = 180;
export const POSTCARD_H = 320;
export const POSTCARD_SCALE = 3;

const FLAG_COLS = ['coral', 'yellow', 'mint', 'sky', 'lilac', 'pink-pale'];
const CONFETTI_COLS = ['coral', 'yellow', 'mint', 'sky', 'lilac', 'pink-pale', 'white'];

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function noSmooth(g) {
  g.imageSmoothingEnabled = false;
  g.webkitImageSmoothingEnabled = false;
  g.mozImageSmoothingEnabled = false;
  return g;
}

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

const fill = (g, col, x, y, w, h) => {
  g.fillStyle = pal(col);
  g.fillRect(x, y, w, h);
};

// ---------- pixel text ----------
// Silkscreen drawn by the browser is anti-aliased; snap every pixel's alpha
// to 0 or 255 so the glyphs keep hard edges, then trim to the ink.
// A bullet ("•") is drawn as a square dot: the font's own is a thin dash.
function textMask(text, size) {
  const font = `${size}px Silkscreen, monospace`;
  const probe = canvas(1, 1).getContext('2d');
  probe.font = font;
  const plain = String(text).replace(/\u2022/g, ' ');
  const w = Math.ceil(probe.measureText(plain).width) + 6;
  const h = Math.ceil(size * 1.6) + 6;
  const c = canvas(w, h);
  const g = c.getContext('2d');
  g.font = font;
  g.textBaseline = 'alphabetic';
  g.fillStyle = '#000';
  const base = 3 + Math.round(size * 1.05);
  g.fillText(plain, 3, base);
  const cap = Math.round(probe.measureText('H').actualBoundingBoxAscent || size * 0.625);
  const dot = Math.max(2, Math.round(size / 4));
  const space = probe.measureText(' ').width;
  for (let i = plain.indexOf(' '); i >= 0; i = plain.indexOf(' ', i + 1)) {
    if (text[i] !== '\u2022') continue;
    const x = Math.round(3 + probe.measureText(plain.slice(0, i)).width + (space - dot) / 2);
    g.fillRect(x, Math.round(base - cap / 2 - dot / 2), dot, dot);
  }
  const img = g.getImageData(0, 0, w, h);
  const d = img.data;
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const on = d[i + 3] >= 120;
      d[i] = d[i + 1] = d[i + 2] = 0;
      d[i + 3] = on ? 255 : 0;
      if (on) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  if (x1 < 0) return null;
  g.putImageData(img, 0, 0);
  const out = canvas(x1 - x0 + 1, y1 - y0 + 1);
  out.getContext('2d').drawImage(c, x0, y0, out.width, out.height, 0, 0, out.width, out.height);
  return out;
}

function tint(mask, col) {
  const c = canvas(mask.width, mask.height);
  const g = c.getContext('2d');
  g.drawImage(mask, 0, 0);
  g.globalCompositeOperation = 'source-in';
  g.fillStyle = pal(col);
  g.fillRect(0, 0, c.width, c.height);
  return c;
}

function measure(text, size) {
  const m = textMask(text, size);
  return m ? m.width : 0;
}

// Centred text with a 1-pixel (or 2 for big text) ink outline and a drop shadow.
// Returns the drawn height.
function drawText(g, text, size, cx, top, { color = 'white', outline = 'ink', shadow = null } = {}) {
  const m = textMask(text, size);
  if (!m) return 0;
  const x = Math.round(cx - m.width / 2);
  const o = size >= 24 ? 2 : 1;
  if (shadow) {
    const s = tint(m, shadow);
    const k = Math.max(1, size / 8);
    for (let dx = -o; dx <= o; dx++) g.drawImage(s, x + dx, top + o + k);
  }
  if (outline) {
    const ol = tint(m, outline);
    for (let dy = -o; dy <= o; dy++) for (let dx = -o; dx <= o; dx++) if (dx || dy) g.drawImage(ol, x + dx, top + dy);
  }
  g.drawImage(tint(m, color), x, top);
  return m.height;
}

// Fit text to a width using only whole-pixel font sizes (multiples of 8).
function bestSize(text, maxW, sizes) {
  for (const s of sizes) if (measure(text, s) + 4 <= maxW) return s;
  return sizes[sizes.length - 1];
}

// ---------- scenery ----------
function sky(g, x0, y0, x1, horizon) {
  const bands = [
    ['blue-dark', y0],
    ['purple', 42],
    ['pink', 88],
    ['coral', 128],
    ['orange', 164],
  ];
  bands.forEach(([col, y], i) => {
    const yEnd = i + 1 < bands.length ? bands[i + 1][1] : horizon;
    fill(g, col, x0, y, x1 - x0, yEnd - y);
    // two rows of checkerboard dither into the next band
    if (i + 1 < bands.length) {
      g.fillStyle = pal(bands[i + 1][0]);
      for (let yy = yEnd - 2; yy < yEnd; yy++) for (let xx = x0 + ((yy & 1) ? 1 : 0); xx < x1; xx += 2) g.fillRect(xx, yy, 1, 1);
    }
  });
}

function sun(g, cx, cy, r) {
  for (let y = -r; y <= 0; y++) {
    const half = Math.floor(Math.sqrt(r * r - y * y));
    fill(g, 'yellow', cx - half, cy + y, half * 2 + 1, 1);
    const inner = r - 6;
    if (-y <= inner) {
      const hi = Math.floor(Math.sqrt(inner * inner - y * y));
      fill(g, 'sand-light', cx - hi, cy + y, hi * 2 + 1, 1);
    }
  }
}

function ground(g, x0, x1, top, bottom, rnd) {
  // distant tree line
  for (let x = x0; x < x1; x++) {
    const h = 3 + Math.round(2 * Math.sin(x * 0.45) + 1.5 * Math.sin(x * 0.17 + 1));
    fill(g, 'green-dark', x, top - h, 1, h);
  }
  fill(g, 'grass', x0, top, x1 - x0, bottom - top);
  fill(g, 'grass-light', x0, top, x1 - x0, 1);
  g.fillStyle = pal('grass-light');
  for (let x = x0 + 1; x < x1; x += 2) g.fillRect(x, top + 1, 1, 1);
  for (let i = 0; i < 70; i++) {
    const x = x0 + Math.floor(rnd() * (x1 - x0 - 3));
    const y = top + 4 + Math.floor(rnd() * (bottom - top - 6));
    fill(g, rnd() < 0.5 ? 'green' : 'grass-light', x, y, 1, 1);
    fill(g, 'green', x + 1, y + 1, 1, 1);
  }
}

function bunting(g, x0, x1, y0) {
  const mid = (x0 + x1) / 2;
  const half = (x1 - x0) / 2;
  const sag = (x) => Math.round(y0 + 5 * (1 - ((x - mid) / half) ** 2));
  for (let x = x0; x <= x1; x++) fill(g, 'ink', x, sag(x), 1, 1);
  let i = 0;
  for (let x = x0 + 5; x + 9 <= x1 - 3; x += 13, i++) {
    const cx = x + 4;
    const top = sag(cx) + 1;
    for (let r = 0; r < 9; r++) {
      const hw = 4 - (r >> 1);
      fill(g, 'ink', cx - hw - 1, top + r, hw * 2 + 3, 1);
    }
    fill(g, 'ink', cx, top + 9, 1, 1);
    for (let r = 0; r < 9; r++) {
      const hw = 4 - (r >> 1);
      fill(g, FLAG_COLS[i % FLAG_COLS.length], cx - hw, top + r, hw * 2 + 1, 1);
    }
    fill(g, 'white', cx - 3, top, 1, 1); // tiny highlight
  }
}

function sparkle(g, x, y, col = 'yellow') {
  fill(g, col, x, y - 2, 1, 5);
  fill(g, col, x - 2, y, 5, 1);
  fill(g, 'white', x, y, 1, 1);
}

function shadow(g, cx, y, w) {
  const h = w >= 20 ? 2 : 1;
  fill(g, 'green-dark', cx - Math.round(w / 2) + 2, y - h, w - 4, h * 2 + 1);
  fill(g, 'green-dark', cx - Math.round(w / 2), y - h + 1, w, h * 2 - 1);
}

// Character image standing with its feet at (cx, feetY).
function stand(g, ch, cx, feetY) {
  if (!ch?.img) return;
  const w = ch.img.naturalWidth || ch.img.width;
  const h = ch.img.naturalHeight || ch.img.height;
  const f = ch.feetY ?? h;
  shadow(g, cx, feetY, Math.max(10, Math.round(w * (w > 40 ? 0.42 : 0.5))));
  g.drawImage(ch.img, Math.round(cx - w / 2), Math.round(feetY - f));
}

/**
 * Draw the postcard.
 * @param {object} o
 * @param {string} o.title          e.g. "HAPPY BIRTHDAY, V!" (split at the last comma if it doesn't fit)
 * @param {string} o.subtitle       e.g. "VNR VJIET"
 * @param {string} o.scoreText      line at the bottom, e.g. "QUIZ SCORE 5/7"
 * @param {{img, feetY}} o.player   large sprite
 * @param {{img, feetY}[]} o.friends small sprites (any number; 7 fit best)
 * @param {{img, candles?, flames?, flameW?}} o.cake
 * @returns {Promise<HTMLCanvasElement>} the 540x960 canvas
 */
export async function renderPostcard({ title = '', subtitle = '', scoreText = '', player, friends = [], cake } = {}) {
  try {
    await Promise.race([document.fonts?.load('8px Silkscreen'), new Promise((r) => setTimeout(r, 1500))]);
  } catch { /* fall back to whatever font is there */ }

  const W = POSTCARD_W, H = POSTCARD_H;
  const c = canvas(W, H);
  const g = noSmooth(c.getContext('2d'));
  const rnd = rng(251126);

  // Postcard border, then the scene inside it.
  fill(g, 'white', 0, 0, W, H);
  fill(g, 'ink', 4, 4, W - 8, H - 8);
  const X0 = 5, Y0 = 5, X1 = W - 5, Y1 = H - 5;
  const HORIZON = 206;
  sky(g, X0, Y0, X1, HORIZON);
  for (let i = 0; i < 26; i++) fill(g, rnd() < 0.7 ? 'white' : 'yellow', X0 + Math.floor(rnd() * (X1 - X0)), Y0 + 20 + Math.floor(rnd() * 60), 1, 1);
  sun(g, 90, HORIZON, 26);
  ground(g, X0, X1, HORIZON, Y1, rnd);
  for (let i = 0; i < 34; i++) {
    const x = X0 + 2 + Math.floor(rnd() * (X1 - X0 - 4));
    const y = 92 + Math.floor(rnd() * 100);
    const col = CONFETTI_COLS[Math.floor(rnd() * CONFETTI_COLS.length)];
    if (rnd() < 0.5) fill(g, col, x, y, 2, 1); else fill(g, col, x, y, 1, 2);
  }
  sparkle(g, 22, 104);
  sparkle(g, 158, 96);
  sparkle(g, 30, 150, 'white');
  sparkle(g, 150, 142, 'white');
  bunting(g, X0 + 1, X1 - 2, 8);

  // Title: one line if it fits, else split at the last comma with the second
  // part drawn big ("HAPPY BIRTHDAY," / "V!").
  const maxW = X1 - X0 - 8;
  let y = 28;
  const t = String(title).trim();
  if (measure(t, 16) + 4 <= maxW) {
    y += drawText(g, t, 16, W / 2, y, { color: 'yellow', shadow: 'red-dark' }) + 8;
  } else {
    const k = t.lastIndexOf(',');
    const parts = k > 0 ? [t.slice(0, k + 1).trim(), t.slice(k + 1).trim()] : [t, ''];
    const s1 = bestSize(parts[0], maxW, [16, 8]);
    y += drawText(g, parts[0], s1, W / 2, y, { color: 'white', shadow: 'plum' }) + 7;
    if (parts[1]) y += drawText(g, parts[1], bestSize(parts[1], maxW, [32, 24, 16, 8]), W / 2, y, { color: 'yellow', shadow: 'red-dark' }) + 9;
  }
  if (subtitle) drawText(g, subtitle, 8, W / 2, y, { color: 'sand-light' });

  // Everyone around the cake: friends behind and in front, Vaishali in the middle.
  const feet = 244;
  const back = [[22, 210], [48, 199], [132, 199], [158, 210]];
  const front = [[30, 286], [150, 286], [90, 296]];
  const extra = (i) => [X0 + 14 + ((i * 37) % (X1 - X0 - 28)), 300];
  const spots = friends.map((f, i) => ({ f, at: i < back.length ? back[i] : i - back.length < front.length ? front[i - back.length] : extra(i) }));
  spots.filter((s) => s.at[1] < feet).sort((a, b) => a.at[1] - b.at[1]).forEach((s) => stand(g, s.f, s.at[0], s.at[1]));
  stand(g, player, 90, feet);
  if (cake?.img) {
    // Same proportions as the finale stage: cake art at 2x beside the 1x sprite.
    const k = cake.scale || 2;
    const cw = (cake.img.naturalWidth || cake.img.width) * k;
    const chh = (cake.img.naturalHeight || cake.img.height) * k;
    const cx = Math.round(90 - cw / 2);
    const cy = feet + 14 - chh;
    shadow(g, 90, feet + 14, cw + 4);
    g.drawImage(cake.img, cx, cy, cw, chh);
    if (cake.flames && Array.isArray(cake.candles)) {
      const fw = cake.flameW || 3;
      const fh = cake.flames.naturalHeight || cake.flames.height;
      cake.candles.forEach(([x, yy]) => g.drawImage(cake.flames, 0, 0, fw, fh, cx + x * k, cy + yy * k, fw * k, fh * k));
    }
  }
  spots.filter((s) => s.at[1] >= feet).sort((a, b) => a.at[1] - b.at[1]).forEach((s) => stand(g, s.f, s.at[0], s.at[1]));

  // Score ribbon at the bottom.
  if (scoreText) {
    const m = textMask(scoreText, 8);
    if (m) {
      const bw = m.width + 22;
      const bx = Math.round(W / 2 - bw / 2);
      const by = Y1 - 14;
      fill(g, 'ink', bx - 1, by - 1, bw + 2, 13);
      fill(g, 'cream', bx, by, bw, 11);
      fill(g, 'white', bx, by, bw, 1);
      drawText(g, scoreText, 8, W / 2, by + 3, { color: 'red-dark', outline: null });
      // little hearts either side
      for (const hx of [bx + 4, bx + bw - 9]) {
        fill(g, 'red', hx, by + 4, 2, 1); fill(g, 'red', hx + 3, by + 4, 2, 1);
        fill(g, 'red', hx, by + 5, 5, 1); fill(g, 'red', hx + 1, by + 6, 3, 1); fill(g, 'red', hx + 2, by + 7, 1, 1);
      }
    }
  }

  // 3x nearest-neighbour upscale.
  const big = canvas(W * POSTCARD_SCALE, H * POSTCARD_SCALE);
  const bg = noSmooth(big.getContext('2d'));
  bg.drawImage(c, 0, 0, big.width, big.height);
  return big;
}
