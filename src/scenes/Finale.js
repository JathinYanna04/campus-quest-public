import Phaser from 'phaser';
import { hud, bubble, transition, confetti, showFinaleUI, showLetter, showKeepsake } from '../ui/index.js';
import { renderPostcard } from '../ui/postcard.js';
import { stageToScreen } from '../game/stage.js';
import { sound } from '../audio/sound.js';
import { assets, friendIds, notes, readCount, quizScore, keepsake, letterFor } from '../game/data.js';
import { state, save } from '../game/state.js';
import { createPlayer, createFriend } from '../game/characters.js';
import { fitStage, STAGE_W, ART_SCALE } from '../game/stage.js';

export const CREDITS = [
  'Made with love by your friends',
  'Map data © OpenStreetMap contributors',
  'Fonts: Pixelify Sans, Patrick Hand, Silkscreen (SIL Open Font License)',
  'Music and sounds: synthesised live in your browser',
  'Built with Phaser and Vite',
];

export default class Finale extends Phaser.Scene {
  constructor() {
    super('Finale');
  }

  create() {
    const f = assets.locations.finale;
    this.leaving = false;
    this.finaleUI = null;
    this.blownOut = false;
    this.musicWasOn = sound.musicOn;
    this.events.once('shutdown', () => {
      this.finaleUI?.close();
      // Leaving (back or replay) mid-song: stop the music box, bring the loop back.
      sound.stopMusicBox();
      if (this.musicWasOn && !sound.musicOn) sound.music(true);
    });
    this.add.image(0, 0, 'loc-finale').setOrigin(0, 0).setScale(ART_SCALE);
    const S = ART_SCALE;
    fitStage(this);
    const zoom = this.cameras.main.zoom;

    // Cake in the middle of the floor, Vaishali right behind it.
    const floorMid = Math.round(((f.floorTop + f.floorBottom) / 2) * S);
    const cakeTex = this.textures.get('cake').getSourceImage();
    const cakeW = cakeTex.width * S;
    const cakeH = cakeTex.height * S;
    const cakeX = Math.round(STAGE_W / 2 - cakeW / 2);
    const cakeY = floorMid + 12 - cakeH;
    this.add.image(cakeX, cakeY, 'cake').setOrigin(0, 0).setScale(S).setDepth(floorMid + 12);

    this.player = createPlayer(this, STAGE_W / 2, floorMid - 16, { size: 'large', data: assets.characters });
    this.player.setDepth(floorMid - 16);

    // Friends in a gentle arc around her: back row behind, front corners.
    const ids = friendIds();
    const arc = [
      [-120, -32], [120, -32], [-68, -56], [68, -56], [-160, 0], [160, 0], [-116, 24],
    ];
    this.friends = ids.map((id, i) => {
      const [dx, dy] = arc[i % arc.length];
      const x = Math.round(STAGE_W / 2 + dx);
      const y = Math.round(floorMid + dy);
      const fr = createFriend(this, id, x, y, { size: 'large', data: assets.characters, read: true, facing: dx < 0 ? 'right' : 'left' });
      fr.setDepth(y);
      return fr;
    });

    // Candles
    if (!this.anims.exists('flame')) {
      this.anims.create({ key: 'flame', frames: this.anims.generateFrameNumbers('flames'), frameRate: 8, repeat: -1 });
    }
    if (this.textures.exists('smoke') && !this.anims.exists('smoke')) {
      this.anims.create({ key: 'smoke', frames: this.anims.generateFrameNumbers('smoke'), frameRate: 8, repeat: 0 });
    }
    this.flames = f.cake.candles.map(([x, y], i) => {
      const s = this.add.sprite(cakeX + x * S, cakeY + y * S, 'flames').setOrigin(0, 0).setScale(S).setDepth(floorMid + 13);
      s.play({ key: 'flame', startFrame: i % (f.cake.frames || 1) });
      return s;
    });

    // Big, forgiving tap target over the cake.
    const pad = Math.ceil(44 / zoom);
    const zone = this.add
      .zone(STAGE_W / 2, cakeY + cakeH / 2, Math.max(cakeW + 16, pad), Math.max(cakeH + 32, pad))
      .setInteractive({ useHandCursor: true });
    zone.once('pointerup', () => this.blow());

    this.time.delayedCall(900, () => {
      const s = stageToScreen(this, STAGE_W / 2, cakeY - 2);
      if (!this.blownOut) this.hintBubble = bubble('Tap the candles!', s.x, s.y, 4000);
    });

    hud.mount({ onBack: () => this.back(), onBook: null, onRecenter: null });
    hud.show(['back']);
    hud.setCounter(readCount(), ids.length);
    transition.in();
  }

  update(time, delta) {
    this.player.update(time, delta);
    for (const f of this.friends) f.update(time, delta);
  }

  blow() {
    this.blownOut = true;
    this.hintBubble?.close();
    sound.play('blow');
    // The lo-fi loop bows out and a music box plays Happy Birthday.
    sound.fadeOutBgm(900);
    const songMs = sound.playMusicBoxBirthday({ delay: 0.45 });
    this.time.delayedCall(songMs + 400, () => {
      if (this.musicWasOn && !sound.musicOn) sound.music(true);
    });
    for (const s of this.flames) {
      if (this.anims.exists('smoke')) {
        s.play('smoke');
        s.once('animationcomplete', () => s.setVisible(false));
      } else {
        s.setVisible(false);
      }
    }
    state.finaleDone = true;
    save();
    this.time.delayedCall(350, () => {
      sound.play('confetti');
      confetti(4000);
    });
    this.time.delayedCall(1300, () => {
      const message = notes.finale?.text || 'Happy birthday, Vaishali!';
      const fin = letterFor('finale');
      showLetter({ id: 'finale', name: 'All of us', sprite: 'vaishali', title: 'Happy Birthday, Vaishali!', text: message, photo: fin.photo, photoDate: fin.photoDate, photoLocation: fin.photoLocation, photoCaption: fin.photoCaption, sfx: 'paper' });
      this.finaleUI = showFinaleUI({
        score: quizScore(),
        message: notes.finale?.text || 'Happy birthday, Vaishali!',
        credits: CREDITS,
        onReplay: () => this.scene.restart(),
        onKeepsake: () => this.saveKeepsake(),
      });
    });
  }

  // The downloadable postcard, drawn from the sprites already loaded.
  async saveKeepsake() {
    const chars = assets.characters;
    const tex = (key) => (this.textures.exists(key) ? this.textures.get(key).getSourceImage() : null);
    const f = assets.locations.finale;
    const score = quizScore();
    const ids = friendIds();
    const read = readCount();
    const canvas = await renderPostcard({
      title: keepsake.postcard.title,
      subtitle: keepsake.postcard.subtitle,
      scoreText: score.total ? `QUIZ SCORE ${score.right}/${score.total}` : `${read}/${ids.length} FRIENDS FOUND`,
      player: { img: tex(`char-${chars.player}`), feetY: chars.characters[chars.player]?.large?.feetY },
      friends: ids.map((id) => ({ img: tex(`char-${id}-map`), feetY: chars.characters[id]?.small?.feetY })).filter((x) => x.img),
      cake: { img: tex('cake'), flames: tex('flames'), flameW: f.cake.frameW, candles: f.cake.candles, scale: ART_SCALE },
    });
    await showKeepsake({ canvas, fileName: keepsake.postcard.fileName });
  }

  async back() {
    if (this.leaving) return;
    this.leaving = true;
    await transition.out();
    this.scene.start('CampusMap', { from: 'ground' });
  }
}
