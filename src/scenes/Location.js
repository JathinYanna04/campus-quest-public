import Phaser from 'phaser';
import { hud, toast, transition, showLetter, showStickerBook, showQuiz, showMemoryWall, showPhoto, actionButton } from '../ui/index.js';
import { sound } from '../audio/sound.js';
import { assets, friendsAt, friendsConfig, friendIds, friendName, readCount, allRead, letterFor, spriteUrl, quizFor, locationSpotsFor, keepsake, placePhotoFor } from '../game/data.js';
import { state, markRead, recordQuiz, nextEggLine, startOver, markSeen } from '../game/state.js';
import { createPlayer, createFriend } from '../game/characters.js';
import { fitStage, stageToScreen, STAGE_W, ART_SCALE } from '../game/stage.js';
import { sayEggLine, closeEggLine, twinkle } from '../game/eggs.js';

export default class Location extends Phaser.Scene {
  constructor() {
    super('Location');
  }

  create({ location }) {
    this.location = location;
    this.leaving = false;
    const scenes = assets.locations.scenes;
    const info = scenes[location] || scenes['b-block'];
    const bgKey = this.textures.exists(`loc-${location}`) ? `loc-${location}` : 'loc-b-block';
    this.add.image(0, 0, bgKey).setOrigin(0, 0).setScale(ART_SCALE);
    fitStage(this);
    this.busy = false;

    const ids = friendsAt(location);
    const zoom = this.cameras.main.zoom;
    const slots = layout(ids.length + 1, info.floorTop * ART_SCALE, info.floorBottom * ART_SCALE);
    // Vaishali takes the slot nearest the side she enters from.
    const enterLeft = info.enterFrom !== 'right';
    slots.sort((a, b) => (enterLeft ? a.x - b.x : b.x - a.x));
    const mine = slots.shift();

    this.friends = ids.map((id, i) => {
      const s = slots[i];
      const f = createFriend(this, id, s.x, s.y, {
        size: 'large',
        data: assets.characters,
        read: !!state.read[id],
        facing: friendsConfig[id].pose || (s.x < STAGE_W / 2 ? 'right' : 'left'),
      });
      f.setDepth(s.y);
      f.showTag(true);
      f.setInteractive(() => this.openLetter(id, f), { minHitPx: Math.ceil(44 / zoom) });
      return f;
    });

    // She walks in from the edge of the stage.
    const startX = enterLeft ? -40 : STAGE_W + 40;
    this.player = createPlayer(this, startX, mine.y, { size: 'large', data: assets.characters });
    this.player.setDepth(mine.y);
    this.player.face(enterLeft ? 1 : -1);
    this.player.setMoving(true);
    this.walk = { x: startX, to: mine.x, y: mine.y };

    // Easter eggs: tappable bits of the background (art px rects, drawn at ART_SCALE).
    const eggs = locationSpotsFor(location);
    const minSide = Math.ceil(32 / zoom); // >= 32 CSS px to tap
    eggs.stageZones.forEach((z) => {
      const [x, y, w, h] = z.rect.map((v) => v * ART_SCALE);
      const zw = Math.max(w, minSide);
      const zh = Math.max(h, minSide);
      const key = `loc:${location}:${z.id}`;
      const zone = this.add.zone(x + w / 2, y + h / 2, zw, zh).setInteractive({ useHandCursor: true }).setDepth(1);
      zone.on('pointerup', () => {
        if (this.busy || this.leaving) return;
        sound.play('tap');
        const s = stageToScreen(this, x + w / 2, y);
        sayEggLine(key, z.lines, s.x, s.y);
      });
      twinkle(this, x + w - 4, y + 4, key, { scale: ART_SCALE, depth: 5 });
    });
    this.events.once('shutdown', closeEggLine);

    // A photo standing on the floor (keepsake.json placePhotos).
    this.placePhoto = placePhotoFor(location);
    if (this.placePhoto) this.addPlacePhoto(info, [mine, ...slots.slice(0, ids.length)], enterLeft);

    // The memory wall lives at keepsake.memoryWall.location (default SAC).
    this.wallBtn = null;
    if (location === keepsake.memoryWall.location) {
      this.wallBtn = actionButton({ label: this.wallLabel(), iconName: 'photo', onClick: () => this.openWall() });
      this.events.once('shutdown', () => this.wallBtn?.remove());
    }

    hud.mount({
      onBack: () => this.back(),
      onBook: () => this.openBook(),
      onRecenter: null,
    });
    hud.show(['back', 'book']);
    hud.setCounter(readCount(), friendIds().length);
    transition.in();
    if (!ids.length) {
      const line = nextEggLine(`loc:${location}:empty`, eggs.emptyLines) || "Nobody's here right now :)";
      this.time.delayedCall(900, () => toast(line, 2600));
    }
  }

  // A little pixel polaroid of the photo on a wooden easel, standing on an
  // empty bit of floor (or at placePhotos.<id>.at), sparkling until opened.
  addPlacePhoto(info, taken, enterLeft) {
    const p = this.placePhoto;
    const loc = this.location;
    const key = `place-photo-${loc}`;
    const W = 26, H = 36; // art px
    let ax, ay; // stage px, bottom centre of the easel
    if (p.at) {
      ax = Math.round(p.at[0] * ART_SCALE);
      ay = Math.round(p.at[1] * ART_SCALE);
    } else {
      const top = info.floorTop * ART_SCALE, bottom = info.floorBottom * ART_SCALE;
      // The floor spot farthest from everyone; ties go to the side she walks towards.
      const xs = enterLeft ? [288, 240, 192, 144, 96] : [96, 144, 192, 240, 288];
      const room = (x) => Math.min(...taken.map((t) => Math.abs(t.x - x)));
      ax = xs.reduce((best, x) => (room(x) > room(best) ? x : best), xs[0]);
      ay = Math.round(top + (bottom - top) * 0.72);
    }

    const place = () => {
      this.add.image(ax, ay, key).setOrigin(0.5, 1).setScale(ART_SCALE).setDepth(ay);
      const zoom = this.cameras.main.zoom;
      const minSide = Math.ceil(44 / zoom);
      const zone = this.add
        .zone(ax, ay - (H * ART_SCALE) / 2, Math.max(W * ART_SCALE + 8, minSide), Math.max(H * ART_SCALE, minSide))
        .setInteractive({ useHandCursor: true })
        .setDepth(ay);
      zone.on('pointerup', () => this.openPlacePhoto());
      twinkle(this, ax + 8 * ART_SCALE, ay - H * ART_SCALE + 4, `photo:${loc}`, { scale: ART_SCALE, depth: ay + 1 });
    };
    if (this.textures.exists(key)) return place();

    const token = (this.photoToken = {});
    this.events.once('shutdown', () => { this.photoToken = null; });
    const img = new Image();
    img.onload = () => {
      if (this.photoToken !== token) return;
      if (!this.textures.exists(key)) this.textures.addCanvas(key, drawEasel(img, W, H));
      place();
    };
    img.src = p.photo;
  }

  async openPlacePhoto() {
    if (this.busy || this.leaving) return;
    this.busy = true;
    closeEggLine();
    markSeen(`photo:${this.location}`);
    const p = this.placePhoto;
    await showPhoto({ title: p.title, photo: p.photo, date: p.photoDate, place: p.photoLocation, caption: p.photoCaption });
    this.busy = false;
  }

  wallLabel() {
    return `${keepsake.memoryWall.title} (${readCount()} / ${friendIds().length})`;
  }

  async openWall() {
    if (this.busy || this.leaving) return;
    this.busy = true;
    closeEggLine();
    const items = friendIds().map((id) => {
      const l = letterFor(id);
      return { ...l, found: !!state.read[id] };
    });
    await showMemoryWall({ title: keepsake.memoryWall.title, items, onOpenLetter: (id) => showLetter(letterFor(id)) });
    this.busy = false;
  }

  update(time, delta) {
    const w = this.walk;
    if (w) {
      const dir = Math.sign(w.to - w.x);
      w.x += dir * (delta / 1000) * 110;
      if ((dir > 0 && w.x >= w.to) || (dir < 0 && w.x <= w.to) || dir === 0) {
        w.x = w.to;
        this.walk = null;
        this.player.setMoving(false);
      }
      this.player.setPosition(Math.round(w.x), w.y);
    }
    this.player.update(time, delta);
    for (const f of this.friends) f.update(time, delta);
  }

  async openLetter(id, f) {
    if (this.busy) return;
    this.busy = true;
    sound.play('tap');
    const wasAll = allRead();
    // First visit: their question comes before the letter (never blocks it).
    const quiz = !state.read[id] && !(id in state.quiz) ? quizFor(id) : null;
    if (quiz) {
      const order = shuffle(quiz.options.map((_, i) => i));
      const right = await showQuiz({
        name: friendName(id),
        sprite: spriteUrl(id),
        question: quiz.question,
        options: order.map((i) => quiz.options[i]),
        answer: order.indexOf(quiz.answer),
        correctLine: quiz.correctLine,
        wrongLine: quiz.wrongLine,
      });
      recordQuiz(id, right);
    }
    await showLetter(letterFor(id));
    if (markRead(id)) {
      f.setRead(true);
      sound.play('sparkle');
      hud.setCounter(readCount(), friendIds().length);
      this.wallBtn?.setLabel(this.wallLabel());
      hud.pulseBook?.();
      if (!wasAll && allRead()) {
        toast("Something's waiting at the ground...", 4000);
      } else {
        toast(`${friendName(id)} found! ${readCount()} / ${friendIds().length}`, 2200);
      }
    }
    this.busy = false;
  }

  async openBook() {
    if (this.busy) return;
    this.busy = true;
    sound.play('tap');
    const friends = friendIds().map((id) => ({ id, name: friendName(id), sprite: spriteUrl(id), found: !!state.read[id], quiz: state.quiz[id] }));
    await showStickerBook({ friends, onOpen: (id) => showLetter(letterFor(id)), onReset: startOver });
    this.busy = false;
  }

  async back() {
    if (this.leaving) return;
    this.leaving = true;
    await transition.out();
    this.scene.start('CampusMap', { from: this.location });
  }
}

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Spread n characters over the floor band without overlap: one row for up
// to 4, otherwise a staggered back row and front row.
// Pixel art (art px, drawn at ART_SCALE): a polaroid with an 18x18 pixelated
// copy of the photo and a little heart, resting on a wooden easel.
function drawEasel(img, W, H) {
  // Shrink in two steps so the tiny copy averages colours instead of aliasing.
  const mid = document.createElement('canvas');
  mid.width = mid.height = 72;
  const mg = mid.getContext('2d');
  mg.imageSmoothingEnabled = true;
  mg.imageSmoothingQuality = 'high';
  const side = Math.min(img.naturalWidth, img.naturalHeight);
  mg.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, 72, 72);

  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d');
  const px = (color, x, y, w = 1, h = 1) => { g.fillStyle = color; g.fillRect(x, y, w, h); };
  const wood = '#9a6440', woodDark = '#5e3a26', ink = '#2b2233';
  // Easel legs (back leg first so it sits behind).
  for (let y = 27; y < H - 1; y++) px(woodDark, 13, y);
  for (let i = 0; i < H - 27; i++) {
    const x = Math.round(5 - (i * 3) / (H - 28));
    px(wood, x, 27 + i, 2, 1);
    px(wood, W - 2 - x, 27 + i, 2, 1);
  }
  px('rgba(43,34,51,0.35)', 1, H - 1, W - 2, 1); // shadow on the floor
  // Polaroid.
  px(ink, 2, 0, 22, 26);
  px('#fbf6ec', 3, 1, 20, 24);
  g.imageSmoothingEnabled = true;
  g.imageSmoothingQuality = 'high';
  g.drawImage(mid, 0, 0, 72, 72, 4, 2, 18, 18);
  g.imageSmoothingEnabled = false;
  const red = '#e0525a';
  px(red, 12, 21); px(red, 14, 21);
  px(red, 11, 22, 5, 1);
  px(red, 12, 23, 3, 1);
  px(red, 13, 24);
  // Ledge the photo rests on.
  px(woodDark, 0, 26, W, 2);
  px(wood, 0, 26, W, 1);
  return c;
}

function layout(n, floorTop, floorBottom) {
  const margin = 60; // wide enough that name tags stay on screen
  const usable = STAGE_W - margin * 2;
  const rows = n <= 4 ? [n] : [Math.floor(n / 2), Math.ceil(n / 2)];
  const out = [];
  rows.forEach((count, r) => {
    const y = rows.length === 1 ? Math.round(floorBottom - (floorBottom - floorTop) * 0.35) : r === 0 ? floorTop + 28 : floorBottom - 8;
    const offset = rows.length > 1 && r === 0 ? usable / (count * 2 + 2) : 0;
    for (let i = 0; i < count; i++) {
      const x = margin + offset + (usable - offset * 2) * (count === 1 ? 0.5 : i / (count - 1));
      out.push({ x: Math.round(x), y: Math.round(y) });
    }
  });
  return out;
}
