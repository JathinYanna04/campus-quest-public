import Phaser from 'phaser';
import { initUI } from './ui/index.js';
import Boot from './scenes/Boot.js';
import Intro from './scenes/Intro.js';
import CampusMap from './scenes/CampusMap.js';
import Location from './scenes/Location.js';
import Finale from './scenes/Finale.js';

async function start() {
  await initUI();
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game',
    backgroundColor: '#1d1b2a',
    pixelArt: true, // nearest-neighbour, no antialiasing
    roundPixels: true,
    scale: {
      // Canvas matches the viewport; each scene picks its own zoom so pixels
      // stay crisp on phones and desktops alike.
      mode: Phaser.Scale.RESIZE,
      width: window.innerWidth,
      height: window.innerHeight,
    },
    input: { activePointers: 3 },
    scene: [Boot, Intro, CampusMap, Location, Finale],
  });
  if (import.meta.env.DEV) window.__game = game;
}

start();
