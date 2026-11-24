# Campus Quest

A pixel-art birthday game for Vaishali. She walks around an accurate map of
VNR VJIET (Bachupally, Hyderabad), finds seven friends in campus buildings,
reads each of their letters, and unlocks a finale at the college ground with
a cake. Built with Vite and Phaser 3; works on phones and desktops.

This public copy is the game itself: code, pixel art, map and tools. The
friends' real letters and photos are not included. `src/data/notes.json`
holds placeholder letters and `public/assets/photos/` is empty, so you can
run it as-is or drop in your own content.

## Run it locally

You need Node.js 20.19+ or 22.12+.

```sh
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173). To try it on your
phone on the same Wi-Fi:

```sh
npm run dev -- --host
```

and open the "Network" URL on the phone.

## For friends: writing your letter (no code needed)

Your letter, spot and quiz question are in the first three files below; the
last two are shared extras anyone can edit.

### `src/data/notes.json`: your letter

```json
"jathin": {
  "title": "That canteen day",
  "text": "Happy birthday!!\n\nRemember when we...",
  "photo": "assets/photos/jathin.jpg",
  "photoDate": "14 Feb 2025",
  "photoLocation": "canteen",
  "photoCaption": "The day the samosas ran out."
}
```

- `title`: a short heading.
- `text`: your memory. `\n` starts a new line, `\n\n` a new paragraph. Any
  length is fine; the letter scrolls.
- `photo`: optional. Put the image in `public/assets/photos/` (a JPG around
  800 px wide is plenty) and write its path as `assets/photos/<file>`. Use
  `""` for no photo; then no photo frame is shown.
- `photoDate`, `photoLocation`, `photoCaption`: optional, written on the back
  of your photo (she taps the polaroid to flip it). `photoLocation` can be a
  location id like `canteen` (shown as its name) or any short text. Leave
  them `""` if you like; your name is signed on the back anyway. Your photo
  also goes up on the Memory Wall once she has read your letter.
- `finale.text` at the bottom is the group message shown after the cake.

Keep the JSON valid: double quotes, a comma between entries, no comma after
the last one. Remove the `[PLACEHOLDER]` text.

### `src/data/friends.json`: where you wait on campus

```json
"jathin": { "location": "b-block", "pose": "right" }
```

- `location`: one of `a-block`, `b-block`, `c-block`, `d-block`, `e-block`,
  `pg-block`, `peb`, `siniti`, `sac`, `sports-complex`, `vjim`, `canteen`,
  `ground`, `main-gate`, `thatibellam` (the shop opposite the gate).
  Several friends can share a location.
- `pose`: `left` or `right`, which way you face.
- Delete `"placeholder": true` once the spot is final.

The current locations are placeholders spread over the map.

### `src/data/quiz.json`: your quiz question

The first time Vaishali taps you, you ask her one question before your
letter opens. Right or wrong, the letter opens afterwards.

```json
"jathin": {
  "question": "What did I order every single day at the canteen?",
  "options": ["Samosa", "Maggi", "Cold coffee", "Dosa"],
  "answer": 1,
  "correct_line": "YES! You remembered!",
  "wrong_line": "Haha no, it was always Maggi!"
}
```

- `options`: 3 or 4 choices. They are shuffled on screen, so order doesn't
  give the answer away.
- `answer`: which option is right, counting from 0 (here `1` = "Maggi").
- `correct_line` / `wrong_line`: what you say after she answers. On a wrong
  answer the game also shows the right one.
- Delete your entry to skip the quiz and go straight to the letter.
- `score_lines` at the bottom: the line shown with her score at the finale:
  `perfect` (all right), `good` (at least half), `low` (fewer than half).

### `src/data/easter_eggs.json`: hidden things to tap

- `mapSpots`: spots on the campus map. `x`, `y` are map pixels (the map is
  1071 x 1427, 0.5 m per pixel), `radius` is how close the tap must be,
  `walkTo: true` makes her walk over first. Each tap shows the next line of
  `lines` in a speech bubble; it loops, and the game remembers her place.
- `locationSpots.<location id>.stageZones`: tappable rectangles on a
  location picture, `rect: [x, y, width, height]` in the 192 x 288 picture
  (`public/assets/locations/<id>.png`), each with its own `lines`.
- `locationSpots.<location id>.emptyLines`: what she says on arriving
  somewhere nobody is waiting.

The lines there now are generic defaults; swap in your own inside jokes.

### `src/data/keepsake.json`: postcard and memory wall

- `postcard.title` / `postcard.subtitle`: text on the PNG postcard she can
  save at the finale. Tiny pixel font, so keep it short and in capitals; a
  comma in the title splits it over two lines with the second part big.
- `postcard.fileName`: name of the downloaded file (ends in `.png`).
- `memoryWall.location` / `memoryWall.title`: where the photo corkboard
  appears (default `sac`) and what it's called.

## Swapping in real walk frames for Vaishali

The player currently uses a procedural walk (whole-pixel bob, shadow,
flip). To use real frames:

1. Draw a horizontal strip of frames, each the same size as
   `public/assets/sprites/vaishali.png` (32x48, feet on the bottom row), and
   save it as `public/assets/sprites/vaishali_walk.png`.
2. In `public/assets/sprites/characters.json`, set
   `characters.vaishali.walk` to
   `{ "file": "vaishali_walk.png", "frameW": 32, "frameH": 48, "frames": 4, "fps": 8 }`.

Location scenes and the finale will play it automatically; the small map
sprite keeps the procedural walk.

## Build and deploy

```sh
npm run build     # static files in dist/
npm run preview   # serve dist/ locally to check
```

`dist/` is plain static files with relative paths (`base: './'`), so it works
at a domain root or a subpath.

- **Vercel**: import the repo; it detects Vite (build `npm run build`, output
  `dist`). Works with a private repo.
- **GitHub Pages**: build, then publish `dist/` (for example with the
  `actions/deploy-pages` workflow, or push `dist/` to a `gh-pages` branch).
  Free GitHub Pages needs a public repo, which makes every letter readable by
  anyone who finds it; Vercel with a private repo avoids that.

## Regenerating the art

All pixel art is generated by Python scripts in `tools/map-data/` (see its
README): `10_render_pixel_map.py` (campus map), `20_characters.py`
(sprites), `30_location_scenes.py` (location backgrounds). Satellite and
Street View imagery used as references stays in `tools/map-data/data/` and
`reference/` and is never copied into the build.

Credits: see [CREDITS.md](CREDITS.md).
