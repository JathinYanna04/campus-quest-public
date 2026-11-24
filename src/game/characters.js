// Character sprites: loading, the player (procedural walk) and friends (bubble/heart/tag).
// (x, y) for every container is the FEET point. All offsets are whole pixels.
import Phaser from 'phaser';

export function preloadCharacters(scene, data, base = 'assets/sprites/') {
  const L = scene.load;
  for (const [id, c] of Object.entries(data.characters)) {
    L.image(`char-${id}`, base + c.large.file);
    L.image(`char-${id}-map`, base + c.small.file);
    L.image(`tag-${id}`, base + c.tag.file);
    if (c.walk) {
      L.spritesheet(`char-${id}-walk`, base + c.walk.file, { frameWidth: c.walk.frameW, frameHeight: c.walk.frameH });
    }
  }
  const fx = data.fx;
  const sp = fx.sparkleFrame || { w: 7, h: 7 };
  L.image('fx-bang', base + fx.bang);
  L.image('fx-heart', base + fx.heart);
  L.spritesheet('fx-sparkle', base + fx.sparkle, { frameWidth: sp.w, frameHeight: sp.h });
  L.image('fx-shadow', base + fx.shadow);
  L.image('fx-shadow-small', base + fx.shadowSmall);
}

function baseFigure(scene, id, x, y, size, data) {
  const c = data.characters[id];
  const meta = size === 'large' ? c.large : c.small;
  const key = size === 'large' ? `char-${id}` : `char-${id}-map`;
  const container = scene.add.container(Math.round(x), Math.round(y));
  // large figures stand on 2x backgrounds: FX/tags/shadow drawn at 2x so their pixels match
  const fxScale = size === 'large' ? (data.fx.largeFxScale || 2) : 1;
  const shadow = scene.add.image(0, 0, size === 'large' ? 'fx-shadow' : 'fx-shadow-small').setAlpha(0.35);
  shadow.setOrigin(0.5, 0.5).setScale(fxScale);
  // origin at the feet: bottom-centre of the figure on the shared baseline
  const sprite = scene.add.image(0, 0, key).setOrigin(0.5, meta.feetY / meta.h);
  container.add([shadow, sprite]);
  return { c, meta, container, shadow, sprite, fxScale };
}

export function createPlayer(scene, x, y, { size = 'small', data } = {}) {
  const id = data.player;
  const f = baseFigure(scene, id, x, y, size, data);
  const { container, sprite } = f;
  const walk = size === 'large' && f.c.walk ? f.c.walk : null;
  let anim = null;
  if (walk) {
    const animKey = `${id}-walk`;
    if (!scene.anims.exists(animKey)) {
      scene.anims.create({
        key: animKey,
        frames: scene.anims.generateFrameNumbers(`char-${id}-walk`, { start: 0, end: walk.frames - 1 }),
        frameRate: walk.fps || 8,
        repeat: -1,
      });
    }
    anim = scene.add.sprite(0, 0, `char-${id}-walk`, 0).setOrigin(0.5, 1).setVisible(false);
    container.add(anim);
  }
  const amp = size === 'large' ? 2 : 1;
  let moving = false;
  let t0 = 0;

  const api = {
    container,
    setPosition(nx, ny) { container.setPosition(Math.round(nx), Math.round(ny)); return api; },
    setMoving(m) {
      if (m === moving) return api;
      moving = m;
      if (anim) {
        anim.setVisible(m); sprite.setVisible(!m);
        if (m) anim.play(`${id}-walk`); else anim.stop();
      }
      if (!m) { sprite.y = 0; f.shadow.x = 0; }
      return api;
    },
    face(dx) {
      if (dx === 0) return api;
      const flip = dx < 0;
      sprite.setFlipX(flip);
      if (anim) anim.setFlipX(flip);
      return api;
    },
    update(time) {
      if (!t0) t0 = time;
      const t = time - t0;
      if (moving && !anim) {
        // ~4 steps per second; bob up on each step, squash on contact
        const ph = (t / 125) % 2;              // 0..2, one step per unit
        const s = Math.abs(Math.sin(ph * Math.PI / 2 * 2)); // 0 at contact, 1 mid-step
        sprite.y = -Math.round(s * amp);
        // no squash/tilt: fractional scale or rotation would break the pixel grid (CLAUDE.md);
        // the shadow pulses 1px instead to sell the step contact
        f.shadow.x = s < 0.25 ? (Math.floor(ph) === 0 ? 1 : -1) * f.fxScale : 0;
      } else if (!moving) {
        // breathing: 1px rise every ~1.6s
        sprite.y = size === 'large' ? ((Math.floor(t / 800) % 2) ? -1 : 0) : 0;
      }
    },
    setDepth(d) { container.setDepth(d); return api; },
    destroy() { container.destroy(); },
  };
  return api;
}

export function createFriend(scene, id, x, y, { size = 'large', data, read = false, facing = 'left', minHitPx = size === 'large' ? 40 : 20 } = {}) {
  const f = baseFigure(scene, id, x, y, size, data);
  const { container, sprite, meta } = f;
  sprite.setFlipX(facing === 'right'); // source art faces the viewer; flip gives variety
  const k = f.fxScale;
  // top of the actual figure (canvas is full height; Bhavana's cropped figure is shorter but ends at the same feet)
  const headY = -meta.feetY;
  const iconY = headY - 2 * k;
  const bang = scene.add.image(0, iconY, 'fx-bang').setOrigin(0.5, 1).setScale(k);
  const heart = scene.add.image(0, iconY, 'fx-heart').setOrigin(0.5, 1).setScale(k);
  const sparkle = scene.add.sprite(6 * k, iconY - 6 * k, 'fx-sparkle', 0).setOrigin(0.5, 1).setScale(k);
  const iconH = Math.max(bang.height, heart.height) * k;
  const tag = scene.add.image(0, iconY - iconH - 2 * k, `tag-${id}`).setOrigin(0.5, 1).setScale(k).setVisible(false);
  container.add([bang, heart, sparkle, tag]);

  if (!scene.anims.exists('fx-sparkle')) {
    scene.anims.create({
      key: 'fx-sparkle',
      frames: scene.anims.generateFrameNumbers('fx-sparkle', { frames: [0, 1, 2, 3, 2, 1, 0] }),
      frameRate: 12,
      repeat: 0,
    });
  }
  sparkle.setVisible(false);
  sparkle.on('animationcomplete', () => sparkle.setVisible(false));

  // desync per friend
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const phase = h % 1600;
  let isRead = read;
  let nextSparkle = 0;
  let hitZone = null;

  const api = {
    container,
    setRead(r) {
      isRead = r;
      bang.setVisible(!r);
      heart.setVisible(r);
      if (!r) sparkle.setVisible(false);
      return api;
    },
    showTag(v) { tag.setVisible(v); return api; },
    update(time) {
      const t = time + phase;
      sprite.y = (Math.floor(t / 800) % 2) ? -1 : 0;
      if (!isRead) {
        const st = Math.floor(t / 250) % 4;
        bang.y = iconY - (st === 1 ? 2 * k : st === 2 ? k : 0);
      } else {
        heart.y = iconY + sprite.y * k;
        if (time > nextSparkle) {
          nextSparkle = time + 1800 + (h % 900);
          sparkle.setVisible(true).play('fx-sparkle');
        }
      }
    },
    setInteractive(callback, opts = {}) {
      const min = opts.minHitPx || minHitPx;
      const w = Math.max(min, sprite.width + 4);
      const hh = Math.max(min, meta.feetY + 4);  // canvas height covers the figure
      if (hitZone) hitZone.destroy();
      hitZone = scene.add.zone(0, -Math.round(hh / 2) + 2, w, hh).setInteractive({ useHandCursor: true });
      container.add(hitZone);
      hitZone.on('pointerup', (p) => callback(api, p));
      return api;
    },
    setDepth(d) { container.setDepth(d); return api; },
    destroy() { container.destroy(); },
  };
  api.setRead(read);
  return api;
}

export default { preloadCharacters, createPlayer, createFriend };
