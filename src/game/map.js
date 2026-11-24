// Places the pre-rendered campus (ground layer, building sprites, props) from
// public/assets/map/campus.json. Everything is static sprites; nothing is
// redrawn per frame.
import Phaser from 'phaser';

export function registerMapFrames(scene, campus) {
  const b = scene.textures.get('map-buildings');
  for (const bl of campus.buildings) {
    const f = bl.frame;
    if (!b.has(bl.id)) b.add(bl.id, 0, f.x, f.y, f.w, f.h);
  }
  const p = scene.textures.get('map-props');
  campus.props.forEach((pr, i) => {
    const f = pr.frame;
    const key = `p${i}`;
    if (!p.has(key)) p.add(key, 0, f.x, f.y, f.w, f.h);
  });
}

export function buildMap(scene, campus) {
  scene.add.image(0, 0, 'map-ground').setOrigin(0, 0).setDepth(-100000);
  const buildings = campus.buildings.map((bl) => {
    const img = scene.add.image(bl.pos.x, bl.pos.y, 'map-buildings', bl.id).setOrigin(0, 0).setDepth(bl.depthY);
    return { data: bl, img };
  });
  campus.props.forEach((pr, i) => {
    scene.add.image(pr.x, pr.y, 'map-props', `p${i}`).setOrigin(0, 0).setDepth(pr.depthY);
  });
  return { buildings };
}

// Pixel-perfect 1px outline around a building sprite: four tinted copies of
// the same frame offset by one map pixel, drawn just behind the building.
export function makeOutline(scene, bl, color = 0xf5d061) {
  const parts = [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
  ].map(([dx, dy]) =>
    scene.add
      .image(bl.pos.x + dx, bl.pos.y + dy, 'map-buildings', bl.id)
      .setOrigin(0, 0)
      .setTintFill(color)
      .setDepth(bl.depthY - 0.5)
      .setVisible(false),
  );
  let tween = null;
  return {
    show() {
      parts.forEach((p) => p.setVisible(true).setAlpha(1));
      tween?.stop();
      tween = scene.tweens.add({ targets: parts, alpha: 0.35, duration: 420, yoyo: true, repeat: -1, ease: 'Stepped', easeParams: [4] });
    },
    hide() {
      tween?.stop();
      tween = null;
      parts.forEach((p) => p.setVisible(false));
    },
  };
}

// Small generated pixel textures used by the map scene (marker arrow, ring).
export function ensureMapTextures(scene) {
  if (!scene.textures.exists('marker-arrow')) {
    // 9x10 pixel arrow pointing down, yellow with ink outline
    const rows = [
      '..XXXXX..',
      '..XYYYX..',
      '..XYYYX..',
      '..XYYYX..',
      'XXXYYYXXX',
      'XYYYYYYYX',
      '.XYYYYYX.',
      '..XYYYX..',
      '...XYX...',
      '....X....',
    ];
    pixelTexture(scene, 'marker-arrow', rows, { X: '#1d1b2a', Y: '#f5d061' });
  }
  if (!scene.textures.exists('marker-star')) {
    const rows = [
      '....X....',
      '...XYX...',
      'XXXXYXXXX',
      'XYYYYYYYX',
      '.XYYYYYX.',
      '..XYYYX..',
      '.XYYXYYX.',
      '.XYX.XYX.',
      '.XX...XX.',
    ];
    pixelTexture(scene, 'marker-star', rows, { X: '#1d1b2a', Y: '#f5d061' });
  }
}

export function pixelTexture(scene, key, rows, colors) {
  const h = rows.length;
  const w = rows[0].length;
  const tex = scene.textures.createCanvas(key, w, h);
  const ctx = tex.getContext();
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const c = colors[rows[y][x]];
      if (c) {
        ctx.fillStyle = c;
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }
  tex.refresh();
  return tex;
}

export const ZOOM_EASE = Phaser.Math.Easing.Sine.InOut;
