// Easter-egg helpers shared by the map and location scenes: speak the next
// line of a spot in a speech bubble, and twinkle over spots not found yet.
import { bubble } from '../ui/index.js';
import { nextEggLine, eggSeen } from './state.js';

let current = null;

/** Show the next line for `key` in a bubble pointing at screen (sx, sy). */
export function sayEggLine(key, lines, sx, sy) {
  const line = nextEggLine(key, lines);
  if (!line) return null;
  current?.close();
  const ms = Math.max(2200, Math.min(6500, 1400 + line.length * 45));
  current = bubble(line, sx, sy, ms);
  return line;
}

export function closeEggLine() {
  current?.close();
  current = null;
}

/** An fx sparkle that pops every few seconds until the egg `key` is first tapped. */
export function twinkle(scene, x, y, key, { scale = 1, depth = 99000 } = {}) {
  if (eggSeen(key)) return null;
  if (!scene.anims.exists('fx-sparkle')) {
    scene.anims.create({
      key: 'fx-sparkle',
      frames: scene.anims.generateFrameNumbers('fx-sparkle', { frames: [0, 1, 2, 3, 2, 1, 0] }),
      frameRate: 12,
      repeat: 0,
    });
  }
  const s = scene.add.sprite(Math.round(x), Math.round(y), 'fx-sparkle', 0).setScale(scale).setDepth(depth).setVisible(false);
  s.on('animationcomplete', () => s.setVisible(false));
  const ev = scene.time.addEvent({
    delay: 2200 + Math.floor(Math.random() * 2600),
    startAt: Math.floor(Math.random() * 2000),
    loop: true,
    callback: () => {
      if (eggSeen(key)) {
        ev.remove();
        s.destroy();
        return;
      }
      s.setVisible(true).play('fx-sparkle');
    },
  });
  return s;
}
