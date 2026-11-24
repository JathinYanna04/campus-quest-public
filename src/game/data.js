// Content lives in JSON so friends never touch code.
import friendsRaw from '../data/friends.json';
import notesRaw from '../data/notes.json';
import quizRaw from '../data/quiz.json';
import eggsRaw from '../data/easter_eggs.json';
import keepsakeRaw from '../data/keepsake.json';
import { state } from './state.js';

const strip = (o) => Object.fromEntries(Object.entries(o).filter(([k]) => !k.startsWith('_')));

export const friendsConfig = strip(friendsRaw);
export const notes = strip(notesRaw);
const quizAll = strip(quizRaw);
const scoreLines = quizAll.score_lines || {};

// A usable quiz entry for a friend, or null (then the letter opens directly).
export function quizFor(id) {
  const q = quizAll[id];
  if (!q || id === 'score_lines' || !q.question || !Array.isArray(q.options) || q.options.length < 2) return null;
  const answer = Number.isInteger(q.answer) && q.answer >= 0 && q.answer < q.options.length ? q.answer : 0;
  return { question: q.question, options: q.options, answer, correctLine: q.correct_line || 'Yay!', wrongLine: q.wrong_line || 'Not quite!' };
}

export function quizScore() {
  const ids = friendIds().filter((id) => quizFor(id));
  const right = ids.filter((id) => state.quiz[id] === true).length;
  const total = ids.length;
  let line = '';
  if (total) line = right === total ? scoreLines.perfect : right * 2 >= total ? scoreLines.good : scoreLines.low;
  return { right, total, line: line || '' };
}

// Filled in by Boot from public/assets/**.json
export const assets = { campus: null, characters: null, locations: null };

export function friendIds() {
  const order = assets.characters?.order || Object.keys(friendsConfig);
  return order.filter((id) => friendsConfig[id]);
}

export function friendName(id) {
  return assets.characters?.characters?.[id]?.name || id.charAt(0).toUpperCase() + id.slice(1);
}

export function friendsAt(locationId) {
  return friendIds().filter((id) => friendsConfig[id].location === locationId);
}

export function readCount() {
  return friendIds().filter((id) => state.read[id]).length;
}

export function allRead() {
  const ids = friendIds();
  return ids.length > 0 && ids.every((id) => state.read[id]);
}

const str = (v) => (typeof v === 'string' ? v.trim() : '');

export function letterFor(id) {
  const n = notes[id] || {};
  const idx = friendIds().indexOf(id);
  return {
    id,
    name: friendName(id),
    sprite: spriteUrl(id),
    title: n.title || '',
    text: n.text || '',
    photo: n.photo ? new URL(n.photo, document.baseURI).href : '',
    // Optional back-of-the-polaroid details.
    photoDate: str(n.photoDate),
    photoLocation: photoPlace(n.photoLocation),
    photoCaption: str(n.photoCaption),
    // Friend letters get their own chime (index in the friend order).
    chime: idx >= 0 ? idx : null,
  };
}

// photoLocation may be a location id ("canteen") or free text.
function photoPlace(v) {
  const s = str(v);
  if (!s) return '';
  const label = locationLabel(s);
  return label && label !== s ? label : s;
}

export function spriteUrl(id) {
  const c = assets.characters?.characters?.[id];
  const file = c?.large?.file || `${id}.png`;
  return new URL(`assets/sprites/${file}`, document.baseURI).href;
}

export function locationLabel(locationId) {
  const c = assets.campus;
  if (!c) return locationId;
  const all = [...(c.buildings || []), ...(c.areas || [])];
  return all.find((b) => b.location === locationId)?.label || locationId;
}

// ---------- easter eggs (src/data/easter_eggs.json) ----------
const eggs = strip(eggsRaw);
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const lineList = (v) => (Array.isArray(v) ? v.filter((l) => typeof l === 'string' && l.trim()) : []);

/** Valid map spots: [{ id, x, y, radius, walkTo, lines }]. Bad entries are skipped. */
export function mapSpots() {
  const list = Array.isArray(eggs.mapSpots) ? eggs.mapSpots : [];
  const seen = new Set();
  return list
    .map((s, i) => {
      if (!s || num(s.x) === null || num(s.y) === null) return null;
      const lines = lineList(s.lines);
      if (!lines.length) return null;
      let id = str(s.id) || `spot-${i}`;
      while (seen.has(id)) id += '+';
      seen.add(id);
      return { id, x: s.x, y: s.y, radius: Math.max(4, num(s.radius) ?? 14), walkTo: s.walkTo !== false, lines };
    })
    .filter(Boolean);
}

/** { emptyLines: [], stageZones: [{ id, rect: [x, y, w, h], lines }] } for a location (art px). */
export function locationSpotsFor(locationId) {
  const all = eggs.locationSpots && typeof eggs.locationSpots === 'object' ? eggs.locationSpots : {};
  const l = all[locationId] && typeof all[locationId] === 'object' ? all[locationId] : {};
  const zones = (Array.isArray(l.stageZones) ? l.stageZones : [])
    .map((z, i) => {
      const r = z && Array.isArray(z.rect) ? z.rect.map(Number) : [];
      if (r.length !== 4 || r.some((v) => !Number.isFinite(v)) || r[2] <= 0 || r[3] <= 0) return null;
      const lines = lineList(z.lines);
      if (!lines.length) return null;
      return { id: str(z.id) || `zone-${i}`, rect: r, lines };
    })
    .filter(Boolean);
  return { emptyLines: lineList(l.emptyLines), stageZones: zones };
}

// ---------- keepsakes (src/data/keepsake.json) ----------
const keep = strip(keepsakeRaw);
const pc = keep.postcard && typeof keep.postcard === 'object' ? keep.postcard : {};
const wall = keep.memoryWall && typeof keep.memoryWall === 'object' ? keep.memoryWall : {};
export const keepsake = {
  postcard: {
    title: str(pc.title) || 'HAPPY BIRTHDAY!',
    subtitle: str(pc.subtitle),
    fileName: /\.png$/i.test(str(pc.fileName)) ? str(pc.fileName) : 'birthday-keepsake.png',
  },
  memoryWall: {
    location: str(wall.location) || 'sac',
    title: str(wall.title) || 'Memory Wall',
  },
};

// A photo standing at a place (keepsake.json placePhotos.<location id>), or null.
const placePhotos = keep.placePhotos && typeof keep.placePhotos === 'object' ? keep.placePhotos : {};
export function placePhotoFor(location) {
  const p = placePhotos[location];
  if (!p || typeof p !== 'object' || !str(p.photo)) return null;
  const at = Array.isArray(p.at) && p.at.length === 2 && p.at.every((v) => Number.isFinite(v)) ? p.at : null;
  return {
    photo: new URL(str(p.photo), document.baseURI).href,
    title: str(p.title),
    photoDate: str(p.photoDate),
    photoLocation: photoPlace(str(p.photoLocation) || location),
    photoCaption: str(p.photoCaption),
    at,
  };
}
