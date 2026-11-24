import Phaser from 'phaser';
import { loading } from '../ui/index.js';
import { assets } from '../game/data.js';
import { preloadCharacters } from '../game/characters.js';
import { registerMapFrames } from '../game/map.js';

// Loads everything up front (total is a few MB) so scene switches are instant.
export default class Boot extends Phaser.Scene {
  constructor() {
    super('Boot');
  }

  preload() {
    loading.set(0.02);
    this.load.json('campus', 'assets/map/campus.json');
    this.load.json('characters', 'assets/sprites/characters.json');
    this.load.json('locations', 'assets/locations/locations.json');
  }

  create() {
    assets.campus = this.cache.json.get('campus');
    assets.characters = this.cache.json.get('characters');
    assets.locations = this.cache.json.get('locations');
    const { campus, locations } = assets;

    this.load.image('map-ground', `assets/map/${campus.ground}`);
    this.load.image('map-buildings', `assets/map/${campus.sheets.buildings}`);
    this.load.image('map-props', `assets/map/${campus.sheets.props}`);
    preloadCharacters(this, assets.characters, 'assets/sprites/');
    for (const [id, s] of Object.entries(locations.scenes)) {
      this.load.image(`loc-${id}`, `assets/locations/${s.file}`);
    }
    const f = locations.finale;
    this.load.image('loc-finale', `assets/locations/${f.file}`);
    this.load.image('cake', `assets/locations/${f.cake.file}`);
    this.load.spritesheet('flames', `assets/locations/${f.cake.flames}`, {
      frameWidth: f.cake.frameW,
      frameHeight: f.cake.frameH,
    });
    if (f.cake.smoke) {
      this.load.spritesheet('smoke', `assets/locations/${f.cake.smoke}`, {
        frameWidth: f.cake.smokeFrameW || f.cake.frameW,
        frameHeight: f.cake.smokeFrameH || f.cake.frameH,
      });
    }

    this.load.on('progress', (p) => loading.set(0.05 + p * 0.95));
    this.load.once('complete', () => {
      registerMapFrames(this, campus);
      loading.set(1);
      Promise.resolve(loading.hide()).then(() => this.scene.start('Intro'));
    });
    this.load.start();
  }
}
