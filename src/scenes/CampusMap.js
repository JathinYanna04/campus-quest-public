import Phaser from 'phaser';
import { hud, toast, transition, showStickerBook, showLetter } from '../ui/index.js';
import { sound } from '../audio/sound.js';
import { assets, friendsAt, friendIds, friendName, readCount, allRead, letterFor, spriteUrl, mapSpots } from '../game/data.js';
import { state, save, startOver } from '../game/state.js';
import { buildMap, makeOutline, ensureMapTextures } from '../game/map.js';
import { MapCamera } from '../game/camera.js';
import { WalkGraph, pointInPolygon } from '../game/nav.js';
import { createPlayer } from '../game/characters.js';
import { sayEggLine, closeEggLine, twinkle } from '../game/eggs.js';
import { ensureAmbientTextures, createGoldenHour, createPetals, createBirds } from '../game/ambient.js';

const FINALE_LOCATION = 'ground';

export default class CampusMap extends Phaser.Scene {
  constructor() {
    super('CampusMap');
  }

  create(data = {}) {
    // Belt and braces: never start with a finger stuck 'down' from a DOM overlay.
    for (const p of this.input.manager.pointers) if (p.isDown) p.reset();
    const campus = assets.campus;
    this.campus = campus;
    this.graph = new WalkGraph(campus.graph);
    this.walking = null;
    this.selected = null;
    this.arriving = false;

    const { buildings } = buildMap(this, campus);
    this.places = [
      ...buildings.filter((b) => b.data.location).map((b) => ({ ...b.data, outline: makeOutline(this, b.data) })),
      ...campus.areas.map((a) => ({ ...a, outline: null })),
    ];
    ensureMapTextures(this);

    // Where she starts: the door she just came out of, else where she was
    // last time, else just inside the main gate.
    const from = data.from || state.lastLocation;
    const place = from && this.places.find((p) => p.location === from);
    const start = place ? standPoint(place) : campus.spawn;
    this.pos = { x: start.x, y: start.y };
    this.player = createPlayer(this, this.pos.x, this.pos.y, { size: 'small', data: assets.characters });
    this.player.setDepth(this.pos.y);

    this.camCtl = new MapCamera(this, campus.width, campus.height, { onTap: (x, y, sx, sy) => this.tap(x, y, sx, sy) });
    this.camCtl.setZoom(this.camCtl.defaultZoom());
    this.camCtl.centerOn(this.pos.x, this.pos.y);
    this.camCtl.startFollow(this.pos);

    this.markers = [];
    this.refreshMarkers();

    // Easter eggs: tappable lore spots, each twinkling until first found.
    this.spots = mapSpots();
    for (const sp of this.spots) twinkle(this, sp.x, sp.y - 4, `map:${sp.id}`, { depth: 99000 });
    this.events.once('shutdown', closeEggLine);

    // Ambient life: golden hour that warms with every letter, petals, birds.
    ensureAmbientTextures(this);
    createGoldenHour(this, readCount(), friendIds().length);
    this.petals = createPetals(this);
    this.birds = createBirds(this, campus, () => this.pos);

    hud.mount({
      onBook: () => this.openBook(),
      onRecenter: () => {
        sound.play('tap');
        this.camCtl.startFollow(this.pos);
      },
      onBack: null,
    });
    hud.show(['book', 'recenter']);
    hud.setCounter(readCount(), friendIds().length);

    transition.in();
    if (data.justFinishedAll) {
      this.time.delayedCall(700, () => this.announceFinale());
    }
  }

  // "!" above places with unread friends, a star over the ground once
  // every letter is read.
  refreshMarkers() {
    for (const m of this.markers) m.destroy();
    this.markers = [];
    const done = allRead();
    for (const p of this.places) {
      const unread = friendsAt(p.location).some((id) => !state.read[id]);
      const finale = done && p.location === FINALE_LOCATION;
      if (!unread && !finale) continue;
      const [x, y] = topOf(p.hit);
      const key = finale ? 'marker-star' : 'fx-bang';
      const m = this.add.image(Math.round(x), Math.round(y - 12), key).setOrigin(0.5, 1).setDepth(100000);
      this.tweens.add({ targets: m, y: m.y - 3, duration: 380, yoyo: true, repeat: -1, ease: 'Stepped', easeParams: [3] });
      this.markers.push(m);
      if (finale) {
        const glow = this.add.image(Math.round(x), Math.round(y - 12), 'marker-star').setOrigin(0.5, 1).setDepth(99999).setTintFill(0xfffaf0);
        glow.setScale(1.6).setAlpha(0.5);
        this.tweens.add({ targets: glow, alpha: 0.1, duration: 600, yoyo: true, repeat: -1 });
        this.markers.push(glow);
      }
    }
  }

  announceFinale() {
    toast("Something's waiting at the ground...", 4000);
    sound.play('sparkle');
    hud.pulseBook?.();
  }

  placeAt(x, y) {
    // Front-most tappable place under the finger; areas lose to buildings.
    let best = null;
    for (const p of this.places) {
      if (!p.hit || !pointInPolygon(x, y, p.hit)) continue;
      const rank = (p.depthY ?? -1) + (p.outline ? 100000 : 0);
      if (!best || rank > best.rank) best = { p, rank };
    }
    return best?.p || null;
  }

  // Closest easter-egg spot under the finger (at least a 32 px target).
  spotAt(x, y) {
    const minR = 16 / this.cameras.main.zoom;
    let best = null;
    for (const sp of this.spots) {
      const d = Math.hypot(sp.x - x, sp.y - y);
      if (d <= Math.max(sp.radius, minR) && (!best || d < best.d)) best = { sp, d };
    }
    return best?.sp || null;
  }

  tap(x, y) {
    if (this.arriving) return;
    const spot = this.spotAt(x, y);
    if (spot) {
      this.tapSpot(spot);
      return;
    }
    const p = this.placeAt(x, y);
    if (!p) return;
    sound.play('tap');
    this.select(p);
  }

  select(p) {
    if (this.selected && this.selected !== p) this.selected.outline?.hide();
    this.selected = p;
    p.outline?.show();
    const route = this.graph.route(this.pos.x, this.pos.y, p.door.node, standPoint(p));
    if (!route) {
      toast("Hmm, can't find a way there.");
      return;
    }
    const len = route.reduce((s, q, i) => s + (i ? Math.hypot(q.x - route[i - 1].x, q.y - route[i - 1].y) : Math.hypot(q.x - this.pos.x, q.y - this.pos.y)), 0);
    // Natural pace on short hops, a bit brisker across campus.
    const speed = Phaser.Math.Clamp(len / 9, 45, 95);
    this.camCtl.startFollow(this.pos);
    if (len < 2) {
      // Already standing at this door.
      this.walking = null;
      this.player.setMoving(false);
      this.arrive(p);
      return;
    }
    this.walking = { route, i: 0, speed, onArrive: () => this.arrive(p) };
    this.player.setMoving(true);
  }

  tapSpot(sp) {
    sound.play('tap');
    if (!sp.walkTo) {
      this.sayEgg(sp);
      return;
    }
    // Walk to the closest point on the paths, then speak.
    this.selected?.outline?.hide();
    this.selected = null;
    const e = this.graph.nearestEdgePoint(sp.x, sp.y);
    const end = e ? { x: e.x, y: e.y } : { x: sp.x, y: sp.y };
    const n = this.graph.nodes;
    const near = (i) => Math.hypot(n[i].x - e.x, n[i].y - e.y);
    const goal = e ? (near(e.a) <= near(e.b) ? e.a : e.b) : this.graph.nearestNode(sp.x, sp.y);
    const route = this.graph.route(this.pos.x, this.pos.y, goal, end);
    this.camCtl.startFollow(this.pos);
    if (!route || Math.hypot(end.x - this.pos.x, end.y - this.pos.y) < 2) {
      this.walking = null;
      this.player.setMoving(false);
      this.sayEgg(sp);
      return;
    }
    const len = route.reduce((s, q, i) => s + Math.hypot(q.x - (i ? route[i - 1].x : this.pos.x), q.y - (i ? route[i - 1].y : this.pos.y)), 0);
    this.walking = { route, i: 0, speed: Phaser.Math.Clamp(len / 9, 45, 95), onArrive: () => this.sayEgg(sp) };
    this.player.setMoving(true);
    if (sp.x !== this.pos.x) this.player.face(sp.x - this.pos.x);
  }

  sayEgg(sp) {
    const cam = this.cameras.main;
    if (Math.abs(sp.x - this.pos.x) > 0.5) this.player.face(sp.x - this.pos.x);
    sayEggLine(`map:${sp.id}`, sp.lines, (sp.x - cam.worldView.x) * cam.zoom, (sp.y - 6 - cam.worldView.y) * cam.zoom);
  }

  update(time, delta) {
    this.camCtl.update(delta);
    const w = this.walking;
    if (w) {
      let step = (w.speed * delta) / 1000;
      while (step > 0 && w.i < w.route.length) {
        const t = w.route[w.i];
        const dx = t.x - this.pos.x;
        const dy = t.y - this.pos.y;
        const d = Math.hypot(dx, dy);
        if (d <= step) {
          this.pos.x = t.x;
          this.pos.y = t.y;
          step -= d;
          w.i++;
        } else {
          this.pos.x += (dx / d) * step;
          this.pos.y += (dy / d) * step;
          if (Math.abs(dx) > 0.3) this.player.face(dx);
          step = 0;
        }
      }
      if (w.i >= w.route.length) {
        this.walking = null;
        this.player.setMoving(false);
        w.onArrive?.();
      }
    }
    this.player.setPosition(Math.round(this.pos.x), Math.round(this.pos.y));
    // Depth-sorted while walking (she passes behind buildings); on top while
    // standing, since some doors sit just behind another wing's roof.
    this.player.setDepth(this.walking ? this.pos.y : 90000);
    this.player.update(time, delta);
    this.petals.update(time, delta);
    this.birds.update(time, delta);
  }

  arrive(p) {
    const loc = p.location;
    state.lastLocation = loc;
    save();
    const here = friendsAt(loc);
    if (loc === FINALE_LOCATION && allRead()) {
      this.enter('Finale', {});
      return;
    }
    this.enter('Location', { location: loc });
  }

  enter(sceneKey, data) {
    if (this.arriving) return;
    this.arriving = true;
    this.time.delayedCall(350, async () => {
      await transition.out();
      this.selected?.outline?.hide();
      this.scene.start(sceneKey, data);
    });
  }

  async openBook() {
    sound.play('tap');
    const friends = friendIds().map((id) => ({ id, name: friendName(id), sprite: spriteUrl(id), found: !!state.read[id], quiz: state.quiz[id] }));
    await showStickerBook({
      friends,
      onOpen: (id) => showLetter(letterFor(id)),
      onReset: startOver,
    });
  }
}

// Where she stands at a place: its door, nudged just south of the building's
// front wall if the door point falls inside the drawn footprint.
function standPoint(p) {
  const d = { x: p.door.x, y: p.door.y };
  if (p.footprint && p.depthY != null && pointInPolygon(d.x, d.y, p.footprint)) d.y = p.depthY + 2;
  return d;
}

function topOf(poly) {
  let top = poly[0];
  let sx = 0;
  for (const p of poly) {
    sx += p[0];
    if (p[1] < top[1]) top = p;
  }
  return [sx / poly.length, top[1]];
}
