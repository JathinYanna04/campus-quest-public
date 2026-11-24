# Campus Quest

A birthday-gift website: a small pixel-art game set on an accurate map of our
college campus, **VNR VJIET (Bachupally, Hyderabad)**. The birthday girl plays
as her own character:

1. She taps a building on the campus map (A, B, C, D, E blocks, Siniti, PG,
   PEB, etc.) and her character walks there.
2. The scene switches to that location.
3. Our friends' characters stand around the location. Tapping one opens a note
   with a memory about her, sometimes with a photo.
4. Once she has read every note, a final scene unlocks.

Stack: **Vite + Phaser 3, vanilla JavaScript (no TypeScript).**

## Commands

- `npm run dev`: dev server with hot reload (`npm run dev -- --host` to open it on a phone over LAN)
- `npm run build`: static build into `dist/`
- `npm run preview`: serve the built `dist/` locally

## Layout

```
index.html              page shell; mounts the game into #game
vite.config.js          base: './' so the build works on any host/subpath
src/main.js             Phaser config and scene registration
src/scenes/             one file per scene
  Boot.js               loads the minimum assets, then starts Intro
  Intro.js              birthday title screen
  CampusMap.js          walkable campus map; tap a building to go there
  Location.js           one building; friends' characters + notes (gets { locationId })
  Finale.js             unlocked after every note is read
  stub.js               temporary placeholder UI; delete when scenes are real
src/data/notes.json     ALL memory content (see schema below)
public/assets/sprites/  character sprites (her, each friend)
public/assets/map/      campus map layers
public/assets/locations/ location backgrounds
public/assets/photos/   memory photos referenced by notes.json
public/assets/audio/    music and sound effects
tools/map-data/         scripts for fetching OSM + satellite data (not shipped)
reference/              reference photos for drawing (not shipped, git-ignored)
```

Everything in `public/` is copied as-is into the build and is loaded at
runtime with paths like `assets/photos/foo.jpg` (no leading slash). Nothing in
`tools/` or `reference/` may be imported by `src/`.

## Content files (friends edit these, never code)

- `src/data/notes.json`: `{ "<friend>": { "title", "text", "photo" }, ..., "finale": { "text" } }`.
  `photo` is a path under `public/` (`assets/photos/x.jpg`) or "".
- `src/data/notes.json` letters may also carry optional `photoDate`,
  `photoLocation` (location id or free text) and `photoCaption`, shown on the
  back of the flippable polaroid and the Memory Wall.
- `src/data/friends.json`: `{ "<friend>": { "location", "pose", "placeholder" } }`.
  `location` is a location id from `public/assets/map/campus.json`.
- `src/data/quiz.json`: one question per friend plus `score_lines`.
- `src/data/easter_eggs.json`: `mapSpots` (`id`, `x`, `y`, `radius`, `walkTo`,
  `lines`) in map px, and `locationSpots.<id>` with `emptyLines` and
  `stageZones` (`id`, `rect: [x, y, w, h]` in 192x288 art px, `lines`). Tap
  counters persist in localStorage (`state.eggs`).
- `src/data/keepsake.json`: finale postcard text (`postcard.title`,
  `subtitle`, `fileName`) and the Memory Wall's `location` / `title`.

Formats for every generated asset (campus.json, characters.json,
locations.json) and the UI kit API are in `docs/BUILD_PLAN.md`.

## Rules

- **Pixel art, nearest-neighbour scaling.** `pixelArt: true` stays on in the
  Phaser config, and the canvas has `image-rendering: pixelated`. Never add
  smoothing. Location and finale stages are 192x288 and shown at whole-number
  zoom (`src/game/stage.js`); the map is 0.5 m per pixel. UI text is DOM in
  Pixelify Sans; text inside art is baked with Silkscreen.
- **Mobile-first.** She will open it on her phone. Design for a portrait
  touch screen first: tap targets at least ~16 game px, no hover-only
  interactions, no keyboard requirement, and it must also work on desktop.
  Keep the download small (compress images, prefer audio that starts on the
  first tap since mobile browsers block autoplay).
- **Map accuracy**: building positions, footprints and the path network come
  from the OSM data via `tools/map-data/`; stylise the look, never the layout.
- **All memory content lives in `src/data/notes.json`** (and placement in
  `src/data/friends.json`). Friends add or change
  notes, names and photos only by editing that file and dropping images into
  `public/assets/photos/` (and sprites into `public/assets/sprites/`). They
  never edit code. Code must read every piece of memory content from
  `notes.json` and must not hardcode names, notes or photo paths. Adding a
  location or friend to the JSON should work without code changes, as long
  as its art exists.
- **Static build only.** `npm run build` must produce plain static files in
  `dist/` that deploy unchanged on GitHub Pages (subpath) or Vercel (root).
  No server, no API routes, no environment secrets. Keep `base: './'` and
  relative asset paths.

## Privacy

The deployed site is public to anyone with the URL, and a GitHub Pages site
on a free account needs a public repo, so every note and photo is readable by
anyone who finds either. Keep that in mind when choosing what goes in
`notes.json`, and keep it away from her until the birthday.

## Map data (tools/map-data/)

Python scripts that fetch the OSM + satellite reference for the campus map;
see `tools/map-data/README.md`. The satellite imagery under
`tools/map-data/data/tiles/` and `data/satellite/` is a private drawing
reference only (Esri terms): never copy it into `public/` or the build.
