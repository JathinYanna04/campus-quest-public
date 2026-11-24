# Campus Quest: build plan

Birthday game for Vaishali. She walks a pixel-art, geographically accurate map
of VNR VJIET, finds 7 friends in campus locations, reads their letters, and
unlocks a finale at the ground with a cake.

## Architecture

```
Phaser 3.90 canvas  (map, characters, location scenes, finale)
  pixelArt: true, roundPixels, Scale.RESIZE (canvas = viewport CSS size)
  every scene picks an INTEGER zoom for its camera -> crisp nearest-neighbour
DOM overlay #ui      (letter modal, sticker book, HUD buttons, toasts, intro,
                      loading bar, speech bubble, transitions)
WebAudio             (synthesised sfx + lo-fi loop, no audio files)
localStorage         (progress; every access wrapped in try/catch)
```

Python (tools/map-data/.venv) generates every pixel asset at build-prep time.
The browser only places pre-rendered sprites, so per-frame work stays tiny.

### Scenes (main session owns)

| Scene | Job |
|---|---|
| `Boot` | load campus.json, characters.json, locations.json, data JSON; DOM loading bar |
| `Intro` | slow pan over the map, DOM title + confetti, "Tap to start", how-to |
| `CampusMap` | map, player, A*, camera drag/pinch/inertia, building taps, signs, finale marker |
| `Location` | 192x288 stage, background + friends + Vaishali, letters |
| `Finale` | ground stage, all 8 + cake, blow candles, confetti, banner, credits |

## File ownership

| Owner | Files |
|---|---|
| Main session | `src/main.js`, `src/scenes/*`, `src/game/{nav,camera,state,data,map}.js`, `src/data/*.json`, `index.html`, README, CLAUDE.md, CREDITS.md |
| Agent A Characters | `tools/map-data/scripts/20_characters.py`, `public/assets/sprites/**`, `src/game/characters.js` |
| Agent B Map | `tools/map-data/scripts/10_render_pixel_map.py` (+ `pixelmap/` helper package if wanted), `public/assets/map/**`, `tools/map-data/output/pixel_map_*.png` |
| Agent C Locations | `tools/map-data/scripts/30_location_scenes.py`, `public/assets/locations/**` |
| Agent D UI kit | `src/ui/**`, `src/audio/**`, `public/assets/fonts/**`, `public/assets/ui/**` |

Nobody edits another owner's files. Shared read-only inputs:
`tools/map-data/palette.json`, `tools/map-data/fonts/*.ttf`,
`tools/map-data/data/processed/*`, `reference/**` (private, never copied).

## Shared conventions

- **Palette**: `tools/map-data/palette.json` (32 colours). Map, locations, props,
  UI use only these (characters keep their own limited palettes).
- **Fonts** (all SIL OFL, in `tools/map-data/fonts/`):
  - `silkscreen_Silkscreen-Regular.ttf` / `-Bold`: tiny pixel text baked into
    PNGs (map signs, name tags, location signs). Render with Pillow
    `draw.fontmode = "1"` at size 8 (crisp; caps look best).
  - `pixelifysans_PixelifySans-VF.ttf`: UI pixel font (DOM).
  - `patrickhand_PatrickHand-Regular.ttf`: letter handwriting (DOM).
- **No smoothing anywhere**: Pillow resizes use `Image.NEAREST`; no
  anti-aliased shapes (draw polygons/lines on 1-bit masks or with plain
  ImageDraw without supersampling); every PNG must contain only palette
  colours plus full transparency (alpha 0 or 255).
- **Private references**: `reference/` and satellite imagery may be *looked at*
  for colours/details only. Never copy, trace pixels from, or embed them.

## Coordinates

Processed GIS data is in metres, x east / y north, origin = SW corner of the
padded bbox (`data/processed/meta.json`, bbox 535.3 x 713.1 m).

Map pixel space (what campus.json uses): **0.5 m per px**, y down:

```
px = round(x_m * 2)
py = round((BBOX_H_M - y_m) * 2)          BBOX_H_M = meta.bbox_size_m.height
map size = ceil(535.3*2) x ceil(713.1*2) = 1071 x 1427 px
```

## Data formats

### `tools/map-data/data/processed/campus_final.geojson` (exists; main session)

Every structure to render. Properties: `id`, `kind` (`building` | `canopy` |
`area` | `point`), `location` (game location id or null), `label`, `levels`,
`placeholder` (label is a guess), `source` (OSM building ids). Locations:
`a-block b-block c-block d-block e-block pg-block peb siniti sac
sports-complex vjim ground canteen main-gate`.

### `public/assets/map/campus.json` (Agent B)

```jsonc
{
  "version": 1,
  "mpp": 0.5, "width": 1071, "height": 1427,
  "ground": "campus_ground.png",            // full-size flat layer (no buildings/props)
  "sheets": { "buildings": "campus_buildings.png", "props": "campus_props.png" },
  "spawn": { "x": 0, "y": 0, "node": 0 },  // just inside the main gate
  "buildings": [{
    "id": "b-block", "location": "b-block", "label": "B Block", "placeholder": false,
    "frame": { "x": 0, "y": 0, "w": 0, "h": 0 },   // rect in buildings sheet
    "pos":   { "x": 0, "y": 0 },                   // top-left of that frame on the map
    "depthY": 0,                                   // map y of the building's front (south) base
    "footprint": [[x, y], ...],                    // ground polygon, map px
    "hit": [[x, y], ...],                          // tappable outline (roof+walls), map px
    "door": { "x": 0, "y": 0, "node": 0 },         // walk target + graph node index
    "sign": { "x": 0, "y": 0 }                     // signboard anchor (bottom-centre), or null
  }],
  "areas": [{                                      // ground, canteen, main-gate
    "id": "ground", "location": "ground", "label": "College Ground", "placeholder": false,
    "hit": [[x, y], ...], "door": { "x": 0, "y": 0, "node": 0 }, "sign": { "x": 0, "y": 0 }
  }],
  "props": [{ "kind": "tree", "frame": {...}, "x": 0, "y": 0, "depthY": 0 }],  // x,y = top-left on map
  "graph": { "nodes": [[x, y], ...], "edges": [[a, b], ...] },  // undirected, map px
  "credits": "Map data © OpenStreetMap contributors"
}
```

Depth rule: an object is drawn in front of anything whose `depthY` is smaller.
Characters use their feet y. Ground layer is depth -inf.
Unlabelled buildings have `location: null` and are not tappable.

### `public/assets/sprites/characters.json` (Agent A)

```jsonc
{
  "player": "vaishali",
  "order": ["jathin", "anudeep", "laasya", "asritha", "joel", "bhavana", "prabhu"],
  "characters": {
    "vaishali": {
      "name": "Vaishali",
      "large": { "file": "vaishali.png", "w": 0, "h": 0, "feetY": 0 },     // location/finale/UI
      "small": { "file": "vaishali_map.png", "w": 0, "h": 0, "feetY": 0 }, // map
      "tag":   { "file": "tags/vaishali.png", "w": 0, "h": 0 },
      "walk":  null       // or { "file": "vaishali_walk.png", "frameW": 0, "frameH": 0, "frames": 0, "fps": 8 }
    }
  },
  "fx": { "bang": "fx/bang.png", "heart": "fx/heart.png", "sparkle": "fx/sparkle.png", "shadow": "fx/shadow.png", "shadowSmall": "fx/shadow_small.png" }
}
```

All `large` canvases share one size, all `small` canvases share one size, feet
on the same baseline. Large target: about 48 px tall figures; small: about
24 px (map).

### `public/assets/locations/locations.json` (Agent C)

```jsonc
{
  "stage": { "w": 192, "h": 288 },
  "scenes": {
    "b-block": { "file": "b-block.png", "floorTop": 200, "floorBottom": 270, "enterFrom": "left" },
    "...": {}
  },
  "finale": { "file": "finale.png", "floorTop": 0, "floorBottom": 0,
              "cake": { "file": "cake.png", "flames": "flames.png", "frameW": 0, "frameH": 0, "frames": 0,
                        "candles": [[x, y], ...] } }
}
```

One scene per location id listed above (14) + finale. Building name on a sign
baked into each background.

### `src/data/friends.json` (main session; friends edit)

```json
{ "jathin": { "location": "b-block", "pose": "left", "placeholder": true } }
```

`location` = any location id; several friends may share one. `pose` =
`left` | `right` (which way they face).

### `src/data/notes.json` (main session; friends edit)

```json
{
  "jathin": { "title": "", "text": "", "photo": "" },
  "finale": { "text": "" }
}
```

`photo` is a path under `public/` like `assets/photos/jathin.jpg`, or "" for none.

## UI kit API (Agent D) — `src/ui/index.js`

```js
initUI()                                   // mounts #ui overlay, fonts, styles
loading.set(progress0to1) / loading.hide()
showIntro({ onStart })                      // title, confetti, Tap to start, then how-to; resolves when done
showLetter({ id, name, sprite, title, text, photo }) -> Promise   // resolves on close
showStickerBook({ friends: [{ id, name, sprite, found }], onOpen(id) }) -> Promise
hud.mount({ onBook, onRecenter, onBack })   // fixed buttons; mute toggle always visible
hud.setCounter(found, total); hud.show(['book','recenter','back']); hud.pulseBook()
toast(text, ms)
bubble(text, screenX, screenY, ms)          // speech bubble pointing at a screen point
transition.out() / transition.in()          // pixel iris; Promises
showFinaleUI({ message, onReplay, credits }) // banner + message card + replay + credits
confetti(ms)                                // DOM pixel confetti burst
polaroid({ photo, sprite, date, place, caption, name }) -> element   // flips on tap
showMemoryWall({ title, items, onOpenLetter }) -> Promise  // corkboard of mini-polaroids
actionButton({ label, iconName, onClick }) -> { setLabel, remove }  // bottom-centre button
showKeepsake({ canvas, fileName }) -> { close, closed }  // download + long-press preview
```

`src/ui/postcard.js`: `renderPostcard({ title, subtitle, scoreText, player,
friends, cake })` draws the 180x320 keepsake and returns a 3x (540x960)
nearest-neighbour canvas. `src/game/ambient.js`: golden-hour tint, petals,
birds (procedural `px_petal`, `px_bird_idle`, `px_bird_flap`).
`src/game/eggs.js`: easter-egg bubbles and twinkles.

`src/audio/sound.js`: `sound.unlock()` (call on first tap), `sound.play(name)`
for `tap|letter|sparkle|blow|confetti|step|whoosh`, `sound.music(on)`,
`sound.muted` (persisted, default muted until first tap),
`sound.fadeOutBgm(ms)`, `sound.playMusicBoxBirthday({ delay })` (returns ms),
`sound.stopMusicBox()`, `sound.playFriendChime(index, delay)`.

## Task split

- **A Characters**: clean 8 JPEG sprites from ~/Downloads (edge flood-fill bg
  removal, halo cleanup, trim, uniform canvases, consistent pixel grid and
  limited palette), name tags, fx icons, `src/game/characters.js` with
  `createPlayer(scene, x, y, { size })` (procedural walk: bob, squash/stretch,
  flip, shadow; spritesheet-ready) and `createFriend(scene, id, x, y, opts)`
  (idle bob, shadow, tag, "!" / heart+sparkle states).
- **B Map**: `10_render_pixel_map.py` -> ground/buildings/props/campus.json,
  walk graph, debug overlay; validation (no props on roofs/roads/footprints,
  no overlapping buildings or signs, every location reachable from spawn).
- **C Locations**: 14 location stages + finale stage + cake/candles.
- **D UI kit**: everything in the API above, pixel-styled DOM, synthesized audio.
- **Main**: data JSON, scenes, navigation, camera, integration, README, review
  loop with a fresh reviewer agent (Playwright, 390x844 and 1440x900).
