import Phaser from 'phaser';
import { showIntro, transition } from '../ui/index.js';
import { sound } from '../audio/sound.js';
import { assets, friendIds } from '../game/data.js';
import { buildMap } from '../game/map.js';
import { state, save } from '../game/state.js';

// Title screen: a slow drift over the real campus map with the birthday
// title (DOM) on top.
export default class Intro extends Phaser.Scene {
  constructor() {
    super('Intro');
  }

  create() {
    const campus = assets.campus;
    buildMap(this, campus);
    const cam = this.cameras.main;
    cam.setBounds(0, 0, campus.width, campus.height);
    const z = Math.max(1, Math.round(Math.min(this.scale.width, this.scale.height) / 200));
    cam.setZoom(z);

    // Drift from the main gate down the campus and back, forever.
    const gate = campus.spawn;
    const south = campus.buildings.find((b) => b.location === 'b-block') || campus.buildings[0];
    cam.centerOn(gate.x, gate.y + 40);
    this.pan = { t: 0, a: { x: gate.x - 40, y: gate.y + 40 }, b: { x: south.door.x, y: south.door.y } };

    showIntro({
      skipHowTo: state.introSeen,
      friendCount: friendIds().length,
      onStart: () => {
        sound.music(true);
        state.introSeen = true;
        save();
      },
    }).then(async () => {
      await transition.out();
      this.scene.start('CampusMap', {});
    });
  }

  update(time, delta) {
    const p = this.pan;
    if (!p) return;
    p.t += delta / 45000;
    const k = (1 - Math.cos(p.t * Math.PI * 2)) / 2; // 0 -> 1 -> 0
    const x = p.a.x + (p.b.x - p.a.x) * k;
    const y = p.a.y + (p.b.y - p.a.y) * k;
    this.cameras.main.centerOn(x, y);
  }
}
