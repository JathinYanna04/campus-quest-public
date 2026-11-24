// Ambient campus life on the map: a golden-hour tint that warms as letters
// are read, drifting petals, and birds that hop about and scatter when
// Vaishali walks up. All textures are generated here (no image files).
import Phaser from 'phaser';
import { PALETTE } from '../ui/palette.js';
import { pixelTexture } from './map.js';
import { pointInPolygon } from './nav.js';
import { sound } from '../audio/sound.js';

const hex = (n) => PALETTE[n];

export const AMBIENT_DEPTH = { tint: 95000, petals: 94500, flyingBird: 94000 };

export function ensureAmbientTextures(scene) {
  if (!scene.textures.exists('px_petal')) {
    pixelTexture(scene, 'px_petal', [
      '.ab.',
      'aaab',
      '.bb.',
    ], { a: hex('pink-pale'), b: hex('pink') });
  }
  const bird = { b: hex('brown'), d: hex('brown-dark'), k: hex('ink'), o: hex('orange'), t: hex('tan') };
  if (!scene.textures.exists('px_bird_idle')) {
    // sitting, facing right
    pixelTexture(scene, 'px_bird_idle', [
      '....bb.',
      '...bkbo',
      'dbbbtb.',
      '.dbbb..',
      '..d.d..',
    ], bird);
  }
  if (!scene.textures.exists('px_bird_flap')) {
    // wings up, legs tucked
    pixelTexture(scene, 'px_bird_flap', [
      '.d.....',
      '.dd..bb',
      '..dbbko',
      'dbbbtb.',
      '..bb...',
    ], bird);
  }
}

// ---------- golden hour ----------
// Tiers by share of letters read (7 friends: 0-2 clear, 3-4 amber, 5-6
// sunset, 7 dusk). Each tier = a MULTIPLY wash plus a faint normal glow.
const TIERS = [
  { mul: 'white', mulA: 0, glow: 'white', glowA: 0 },
  { mul: 'sand-light', mulA: 0.5, glow: 'yellow', glowA: 0.05 },
  { mul: 'coral', mulA: 0.38, glow: 'orange', glowA: 0.09 },
  { mul: 'lilac', mulA: 0.62, glow: 'pink', glowA: 0.1 },
];

export function tierFor(read, total) {
  if (!total) return 0;
  if (read >= total) return 3;
  const f = read / total;
  if (f >= 5 / 7 - 1e-6) return 2;
  if (f >= 3 / 7 - 1e-6) return 1;
  return 0;
}

let lastTier = null; // tier shown last time the map was open (this session)

export function createGoldenHour(scene, read, total) {
  const tier = tierFor(read, total);
  const mk = (blend) => {
    const r = scene.add.rectangle(0, 0, 10, 10, 0xffffff, 0).setOrigin(0, 0).setScrollFactor(0).setDepth(AMBIENT_DEPTH.tint);
    r.setBlendMode(blend);
    return r;
  };
  const mul = mk(Phaser.BlendModes.MULTIPLY);
  const glow = mk(Phaser.BlendModes.NORMAL);
  // Screen-sized and camera-fixed. Zoom (always >= 1) scales scrollFactor-0
  // objects about the screen centre, so a 3x-screen rect always covers it.
  const fit = () => {
    const { width, height } = scene.scale;
    for (const r of [mul, glow]) r.setPosition(-width, -height).setSize(width * 3, height * 3);
  };
  fit();
  scene.scale.on('resize', fit);
  scene.events.once('shutdown', () => scene.scale.off('resize', fit));

  const C = Phaser.Display.Color;
  const apply = (a, b, k) => {
    const A = TIERS[a], B = TIERS[b];
    // From/to "clear", keep the other tier's colour and only fade alpha.
    const mFrom = A.mulA ? A.mul : B.mul, mTo = B.mulA ? B.mul : A.mul;
    const gFrom = A.glowA ? A.glow : B.glow, gTo = B.glowA ? B.glow : A.glow;
    const mc = C.Interpolate.ColorWithColor(C.HexStringToColor(hex(mFrom)), C.HexStringToColor(hex(mTo)), 100, k * 100);
    const gc = C.Interpolate.ColorWithColor(C.HexStringToColor(hex(gFrom)), C.HexStringToColor(hex(gTo)), 100, k * 100);
    mul.setFillStyle(C.GetColor(mc.r, mc.g, mc.b), A.mulA + (B.mulA - A.mulA) * k);
    glow.setFillStyle(C.GetColor(gc.r, gc.g, gc.b), A.glowA + (B.glowA - A.glowA) * k);
  };
  const from = lastTier ?? tier;
  apply(from, from, 0);
  if (from !== tier) {
    // She just crossed into a new tier: let the light change slowly.
    scene.tweens.addCounter({ from: 0, to: 1, delay: 500, duration: 2600, ease: 'Sine.InOut', onUpdate: (tw) => apply(from, tier, tw.getValue()) });
  }
  lastTier = tier;
  return { tier };
}

// ---------- petals ----------
export function createPetals(scene, count = 16) {
  const cam = scene.cameras.main;
  const petals = [];
  const view = () => cam.worldView;
  const spawn = (p, inside) => {
    const v = view();
    if (inside || !v.width) {
      p.x = v.x + Math.random() * v.width;
      p.y = v.y + Math.random() * v.height;
    } else if (Math.random() < v.width / (v.width + v.height)) {
      p.x = v.x + Math.random() * v.width - 20;
      p.y = v.y - 6;
    } else {
      p.x = v.x - 6;
      p.y = v.y + Math.random() * v.height;
    }
    p.vx = 5 + Math.random() * 7; // a light breeze from the north-west
    p.vy = 7 + Math.random() * 7;
    p.amp = 2 + Math.random() * 4;
    p.freq = 0.0012 + Math.random() * 0.0015;
    p.ph = Math.random() * Math.PI * 2;
    p.flipAt = 0;
  };
  for (let i = 0; i < count; i++) {
    const img = scene.add.image(0, 0, 'px_petal').setOrigin(0.5).setDepth(AMBIENT_DEPTH.petals);
    const p = { img };
    spawn(p, true);
    petals.push(p);
  }
  return {
    update(time, delta) {
      const v = view();
      const dt = delta / 1000;
      for (const p of petals) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        const sx = Math.sin(time * p.freq + p.ph) * p.amp;
        if (time > p.flipAt) {
          p.flipAt = time + 260 + Math.random() * 420;
          p.img.setFlipX(!p.img.flipX);
          if (Math.random() < 0.4) p.img.setFlipY(!p.img.flipY);
        }
        if (p.x > v.right + 12 || p.y > v.bottom + 12 || p.x < v.x - 40 || p.y < v.y - 40) spawn(p, false);
        p.img.setPosition(Math.round(p.x + sx), Math.round(p.y));
      }
    },
  };
}

// ---------- birds ----------
const SCATTER_DIST = 55;
const RETURN_DIST = 110;

// Seeded perches inside an area's tap polygon, not too close to each other
// or to where she stands at the door.
function perches(campus, locationId, n, seed) {
  const place = (campus.areas || []).find((a) => a.location === locationId) || (campus.buildings || []).find((b) => b.location === locationId);
  if (!place) return [];
  let s = seed;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const door = place.door;
  const blocked = (x, y) => (campus.buildings || []).some((b) => b.footprint && pointInPolygon(x, y, b.footprint));
  const out = [];
  for (let tries = 0; tries < 400 && out.length < n; tries++) {
    const a = rnd() * Math.PI * 2;
    const r = 20 + rnd() * 50;
    const x = Math.round(door.x + Math.cos(a) * r);
    const y = Math.round(door.y + Math.sin(a) * r * 0.7);
    const inArea = place.hit ? pointInPolygon(x, y, place.hit) : true;
    // Canteen's own polygon is tiny: allow the open ground around it too.
    if (!inArea && locationId !== 'canteen') continue;
    if (blocked(x, y)) continue;
    if (out.some((q) => Math.hypot(q.x - x, q.y - y) < 12)) continue;
    out.push({ x, y });
  }
  return out;
}

export function createBirds(scene, campus, getPlayer) {
  const homes = [...perches(campus, 'ground', 3, 4242), ...perches(campus, 'canteen', 2, 777)];
  let lastFlutter = 0;
  const birds = homes.map((h) => {
    const img = scene.add.image(h.x, h.y, 'px_bird_idle').setOrigin(0.5, 1).setDepth(h.y);
    img.setFlipX(Math.random() < 0.5);
    return { home: h, x: h.x, y: h.y, img, state: 'idle', next: 600 + Math.random() * 2500, hop: null, t: 0, vx: 0, vy: 0 };
  });

  const scatter = (b, p, time) => {
    b.state = 'fly';
    b.t = 0;
    const dir = Math.sign(b.x - p.x) || (Math.random() < 0.5 ? -1 : 1);
    b.vx = dir * (28 + Math.random() * 26);
    b.vy = -(46 + Math.random() * 26);
    b.img.setFlipX(dir < 0).setDepth(AMBIENT_DEPTH.flyingBird);
    if (time - lastFlutter > 500) {
      lastFlutter = time;
      sound.play('flutter');
    }
  };

  return {
    update(time, delta) {
      const p = getPlayer();
      const dt = delta / 1000;
      for (const b of birds) {
        const d = Math.hypot(p.x - b.x, p.y - b.y);
        if (b.state === 'idle') {
          if (d < SCATTER_DIST) { scatter(b, p, time); continue; }
          b.next -= delta;
          let oy = 0;
          if (b.hop) {
            b.hop.t += delta;
            const k = Math.min(1, b.hop.t / b.hop.dur);
            b.x = b.hop.x0 + (b.hop.x1 - b.hop.x0) * k;
            oy = b.hop.peck ? (k < 0.5 ? 1 : 0) : -Math.round(Math.sin(k * Math.PI) * 2);
            if (k >= 1) b.hop = null;
          } else if (b.next <= 0) {
            b.next = 900 + Math.random() * 3200;
            const peck = Math.random() < 0.35;
            const dx = peck ? 0 : Math.round((Math.random() * 2 - 1) * 4);
            // Stay near the perch.
            const x1 = Math.abs(b.x + dx - b.home.x) > 8 ? b.home.x : b.x + dx;
            if (!peck && x1 !== b.x) b.img.setFlipX(x1 < b.x);
            else if (!peck && Math.random() < 0.3) b.img.setFlipX(!b.img.flipX);
            b.hop = { t: 0, dur: peck ? 260 : 200, x0: b.x, x1, peck };
          }
          b.img.setTexture('px_bird_idle').setPosition(Math.round(b.x), Math.round(b.y + oy)).setDepth(b.y);
        } else if (b.state === 'fly') {
          b.t += delta;
          b.vy -= 12 * dt;
          b.x += b.vx * dt;
          b.y += b.vy * dt;
          b.img.setTexture(Math.floor(b.t / 90) % 2 ? 'px_bird_idle' : 'px_bird_flap');
          b.img.setPosition(Math.round(b.x), Math.round(b.y));
          if (b.t > 1600) b.img.setAlpha(Math.max(0, 1 - (b.t - 1600) / 700));
          if (b.t > 2300) {
            b.state = 'gone';
            b.img.setVisible(false).setAlpha(1);
            b.t = 7000 + Math.random() * 7000;
          }
        } else if (b.state === 'gone') {
          b.t -= delta;
          if (b.t <= 0 && Math.hypot(p.x - b.home.x, p.y - b.home.y) > RETURN_DIST) {
            // Glide back in from above.
            b.state = 'land';
            b.t = 0;
            b.from = { x: b.home.x + (Math.random() < 0.5 ? -1 : 1) * (30 + Math.random() * 20), y: b.home.y - 70 };
            b.img.setVisible(true).setFlipX(b.from.x > b.home.x).setDepth(AMBIENT_DEPTH.flyingBird);
          }
        } else if (b.state === 'land') {
          b.t += delta;
          const k = Math.min(1, b.t / 1400);
          const e = 1 - (1 - k) * (1 - k);
          b.x = b.from.x + (b.home.x - b.from.x) * e;
          b.y = b.from.y + (b.home.y - b.from.y) * e;
          b.img.setTexture(Math.floor(b.t / 110) % 2 ? 'px_bird_idle' : 'px_bird_flap');
          b.img.setPosition(Math.round(b.x), Math.round(b.y));
          if (k >= 1) {
            b.state = 'idle';
            b.next = 800 + Math.random() * 1500;
            b.img.setTexture('px_bird_idle').setDepth(b.y);
          } else if (d < SCATTER_DIST * 0.8) {
            scatter(b, p, time);
          }
        }
      }
    },
  };
}
