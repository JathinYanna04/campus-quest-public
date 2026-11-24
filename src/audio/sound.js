// Synthesized sound for Campus Quest: WebAudio only, no audio files.
// Nothing plays before unlock() (call it inside the first tap). Never throws.

const STORE_KEY = 'cq-muted';

function readMuted() {
  try { return localStorage.getItem(STORE_KEY) === '1'; } catch { return false; }
}
function writeMuted(v) {
  try { localStorage.setItem(STORE_KEY, v ? '1' : '0'); } catch { /* ignore */ }
}

let ctx = null;
let master = null; // mute gain
let sfxBus = null;
let musicBus = null;
let noiseBuf = null;
let unlocked = false;
let muted = readMuted();
let musicWanted = false;
let musicTimer = null;
let fadeTimer = null; // pending scheduler stop after fadeOutBgm()
let boxBus = null; // gain of the music-box tune currently playing
let nextBeat = 0;
let beatIndex = 0;
const listeners = new Set();

function makeCtx() {
  if (ctx) return ctx;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = muted ? 0 : 1;
    master.connect(ctx.destination);
    sfxBus = ctx.createGain();
    sfxBus.gain.value = 0.5;
    sfxBus.connect(master);
    musicBus = ctx.createGain();
    musicBus.gain.value = 0;
    musicBus.connect(master);
    const len = ctx.sampleRate; // 1 s of white noise
    noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  } catch {
    ctx = null;
  }
  return ctx;
}

function ready() {
  return unlocked && ctx && ctx.state !== 'closed';
}

// ---------- building blocks ----------
function tone(freq, t, dur, { type = 'sine', vol = 0.3, attack = 0.005, bus = sfxBus, slideTo = null, filter = null } = {}) {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  let node = o;
  if (filter) {
    const f = ctx.createBiquadFilter();
    f.type = 'lowpass';
    f.frequency.value = filter;
    o.connect(f);
    node = f;
  }
  node.connect(g);
  g.connect(bus);
  o.start(t);
  o.stop(t + dur + 0.05);
}

function noise(t, dur, { vol = 0.2, type = 'bandpass', freq = 2000, q = 1, bus = sfxBus, freqTo = null } = {}) {
  const s = ctx.createBufferSource();
  s.buffer = noiseBuf;
  const f = ctx.createBiquadFilter();
  f.type = type;
  f.frequency.setValueAtTime(freq, t);
  if (freqTo) f.frequency.exponentialRampToValueAtTime(freqTo, t + dur);
  f.Q.value = q;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + Math.min(0.02, dur / 3));
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  s.connect(f); f.connect(g); g.connect(bus);
  s.start(t, Math.random() * 0.5);
  s.stop(t + dur + 0.05);
}

const SFX = {
  tap(t) {
    tone(880, t, 0.07, { type: 'square', vol: 0.08, filter: 3000 });
    tone(1320, t + 0.03, 0.06, { type: 'square', vol: 0.05, filter: 3000 });
  },
  letter(t) {
    noise(t, 0.25, { vol: 0.12, freq: 1200, freqTo: 4000, q: 0.8 });
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, t + 0.08 + i * 0.07, 0.35, { type: 'triangle', vol: 0.14 }));
  },
  sparkle(t) {
    [1568, 2093, 2637, 3136, 2637].forEach((f, i) => tone(f, t + i * 0.05, 0.18, { type: 'sine', vol: 0.08 }));
  },
  blow(t) {
    noise(t, 0.7, { vol: 0.25, type: 'lowpass', freq: 900, freqTo: 300, q: 0.5 });
  },
  confetti(t) {
    noise(t, 0.12, { vol: 0.35, freq: 1500, q: 0.7 });
    for (let i = 0; i < 6; i++) tone(700 + Math.random() * 1600, t + 0.05 + i * 0.04, 0.12, { type: 'square', vol: 0.035, filter: 4000 });
    [523.25, 659.25, 783.99].forEach((f) => tone(f, t + 0.15, 0.6, { type: 'triangle', vol: 0.09 }));
  },
  step(t) {
    noise(t, 0.05, { vol: 0.08, type: 'lowpass', freq: 600, q: 1 });
  },
  whoosh(t) {
    noise(t, 0.4, { vol: 0.2, freq: 400, freqTo: 3000, q: 1.5 });
  },
  // Letter rustle on its own (friend letters add their chime on top).
  paper(t) {
    noise(t, 0.25, { vol: 0.12, freq: 1200, freqTo: 4000, q: 0.8 });
  },
  // Birds taking off: a few soft wing beats.
  flutter(t) {
    for (let i = 0; i < 5; i++) noise(t + i * 0.055, 0.05, { vol: 0.07 - i * 0.008, freq: 900 + i * 120, q: 0.9 });
  },
};

// ---------- music box ----------
// One tine: a pure sine fundamental plus a quieter triangle overtone an
// octave up that dies away faster, ~2 ms attack, then an exponential decay.
function pluck(freq, t, { vol = 0.14, decay = 1.6, bus = sfxBus } = {}) {
  const fund = ctx.createOscillator();
  const over = ctx.createOscillator();
  const g1 = ctx.createGain();
  const g2 = ctx.createGain();
  fund.type = 'sine';
  over.type = 'triangle';
  fund.frequency.setValueAtTime(freq, t);
  over.frequency.setValueAtTime(freq * 2, t);
  over.detune.setValueAtTime(4, t); // a hair sharp, like a real comb
  g1.gain.setValueAtTime(0.0001, t);
  g1.gain.exponentialRampToValueAtTime(vol, t + 0.002);
  g1.gain.exponentialRampToValueAtTime(vol * 0.35, t + 0.14);
  g1.gain.exponentialRampToValueAtTime(0.0001, t + decay);
  g2.gain.setValueAtTime(0.0001, t);
  g2.gain.exponentialRampToValueAtTime(vol * 0.32, t + 0.002);
  g2.gain.exponentialRampToValueAtTime(0.0001, t + decay * 0.3);
  fund.connect(g1);
  over.connect(g2);
  g1.connect(bus);
  g2.connect(bus);
  fund.start(t);
  over.start(t);
  fund.stop(t + decay + 0.05);
  over.stop(t + decay * 0.3 + 0.05);
}

const NOTE = { F3: 174.61, Bb3: 233.08, C4: 261.63, E4: 329.63, F4: 349.23, G4: 392.0, A4: 440.0, Bb4: 466.16,
  C5: 523.25, D5: 587.33, E5: 659.25, F5: 698.46, G5: 783.99, A5: 880.0, Bb5: 932.33, C6: 1046.5, F6: 1396.91 };

// "Happy Birthday to You" in F major, 3/4: [melody note, beats, lower-comb chord on that note].
const BIRTHDAY = [
  ['C5', 0.75], ['C5', 0.25], ['D5', 1, ['F3', 'C4']], ['C5', 1], ['F5', 1], ['E5', 2, ['C4', 'G4']],
  ['C5', 0.75], ['C5', 0.25], ['D5', 1, ['C4', 'Bb4']], ['C5', 1], ['G5', 1], ['F5', 2, ['F3', 'A4']],
  ['C5', 0.75], ['C5', 0.25], ['C6', 1, ['F3', 'A4']], ['A5', 1], ['F5', 1], ['E5', 1, ['Bb3', 'F4']], ['D5', 2],
  ['Bb5', 0.75], ['Bb5', 0.25], ['A5', 1, ['C4', 'F4']], ['F5', 1], ['G5', 1, ['C4', 'E4']], ['F5', 3, ['F3', 'C4', 'F4', 'A4']],
];
const BOX_BEAT = 0.62; // seconds per quarter note (~97 BPM)

function stopBox(fade = 0.25) {
  if (!boxBus || !ctx) return;
  const g = boxBus;
  boxBus = null;
  try {
    const now = ctx.currentTime;
    g.gain.cancelScheduledValues(now);
    g.gain.setValueAtTime(g.gain.value, now);
    g.gain.linearRampToValueAtTime(0, now + fade);
    setTimeout(() => { try { g.disconnect(); } catch { /* ignore */ } }, fade * 1000 + 100);
  } catch { /* ignore */ }
}

// F major pentatonic (F G A C D), for the friend chimes.
const PENTA = [0, 2, 4, 7, 9];
function pentatonic(degree, base = NOTE.F4) {
  const oct = Math.floor(degree / 5);
  return base * 2 ** ((12 * oct + PENTA[((degree % 5) + 5) % 5]) / 12);
}

// ---------- music: soft lo-fi loop, 84 BPM, lookahead scheduler ----------
const BPM = 84;
const EIGHTH = 60 / BPM / 2;
// Fmaj7 - Em7 - Dm7 - Cmaj7 (two bars each = 16 eighths per chord)
const CHORDS = [
  [174.61, 220.0, 261.63, 329.63],
  [164.81, 196.0, 246.94, 293.66],
  [146.83, 174.61, 220.0, 261.63],
  [130.81, 164.81, 196.0, 246.94],
];
const MELODY = [ // per eighth, 0 = rest; loops every 64 eighths
  659.25, 0, 0, 587.33, 523.25, 0, 0, 0, 0, 0, 440, 0, 523.25, 0, 0, 0,
  587.33, 0, 0, 523.25, 493.88, 0, 0, 0, 0, 0, 392, 0, 440, 0, 0, 0,
  523.25, 0, 0, 440, 349.23, 0, 0, 0, 0, 0, 440, 0, 523.25, 0, 587.33, 0,
  493.88, 0, 0, 0, 392, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
];

function epiano(freq, t, dur, vol) {
  tone(freq, t, dur, { type: 'triangle', vol, attack: 0.01, bus: musicBus, filter: 1400 });
  tone(freq * 2, t, dur * 0.4, { type: 'sine', vol: vol * 0.25, attack: 0.005, bus: musicBus });
}

function scheduleBeat(i, t) {
  const bar = Math.floor(i / 16) % 4;
  const chord = CHORDS[bar];
  const e = i % 16;
  if (e === 0 || e === 8) chord.forEach((f, k) => epiano(f, t + k * 0.012, EIGHTH * 7, 0.07));
  if (e === 6 || e === 14) chord.slice(1).forEach((f) => epiano(f, t, EIGHTH * 1.5, 0.04));
  const m = MELODY[i % 64];
  if (m) epiano(m, t, EIGHTH * 3, 0.06);
  if (e === 0 || e === 4) tone(chord[0] / 2, t, EIGHTH * 3, { type: 'sine', vol: 0.12, bus: musicBus }); // bass
  // drums
  if (e % 8 === 0 || e === 11) tone(110, t, 0.18, { type: 'sine', vol: 0.22, slideTo: 45, bus: musicBus });
  if (e % 8 === 4) noise(t, 0.12, { vol: 0.06, freq: 1800, q: 0.6, bus: musicBus });
  if (e % 2 === 1) noise(t, 0.035, { vol: 0.025, type: 'highpass', freq: 7000, bus: musicBus });
}

function scheduler() {
  if (!ctx) return;
  while (nextBeat < ctx.currentTime + 0.25) {
    scheduleBeat(beatIndex, nextBeat);
    beatIndex++;
    nextBeat += EIGHTH;
  }
}

const MUSIC_VOL = 0.35;

function startMusic() {
  if (!ready()) return;
  try {
    // Also rescues a fade-out in progress: ramp back up from wherever it is.
    clearTimeout(fadeTimer);
    fadeTimer = null;
    const now = ctx.currentTime;
    musicBus.gain.cancelScheduledValues(now);
    musicBus.gain.setValueAtTime(Math.max(0.0001, musicTimer ? musicBus.gain.value : 0), now);
    musicBus.gain.exponentialRampToValueAtTime(MUSIC_VOL, now + 1.5);
    if (!musicTimer) {
      nextBeat = now + 0.1;
      scheduler();
      musicTimer = setInterval(() => { try { scheduler(); } catch { /* ignore */ } }, 100);
    }
  } catch { /* ignore */ }
}

function stopMusic() {
  clearTimeout(fadeTimer);
  fadeTimer = null;
  if (!musicTimer) return;
  clearInterval(musicTimer);
  musicTimer = null;
  try {
    musicBus.gain.cancelScheduledValues(ctx.currentTime);
    musicBus.gain.setValueAtTime(musicBus.gain.value, ctx.currentTime);
    musicBus.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.3);
  } catch { /* ignore */ }
}

export const sound = {
  /** Call inside a user gesture (first tap). Safe to call repeatedly. */
  unlock() {
    try {
      if (!makeCtx()) return;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      // iOS: play a silent buffer inside the gesture
      const b = ctx.createBufferSource();
      b.buffer = ctx.createBuffer(1, 1, 22050);
      b.connect(ctx.destination);
      b.start(0);
      unlocked = true;
      if (musicWanted) startMusic();
    } catch { /* ignore */ }
  },
  play(name) {
    try {
      if (!ready() || muted || !SFX[name]) return;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      SFX[name](ctx.currentTime + 0.01);
    } catch { /* ignore */ }
  },
  /** Turn background music on or off (remembers the wish until unlock). */
  music(on) {
    musicWanted = !!on;
    if (musicWanted) startMusic(); else stopMusic();
  },
  /** True while background music is wanted (on, or waiting for unlock). */
  get musicOn() { return musicWanted; },
  /** Fade the lo-fi loop out over durationMs, then stop it. sound.music(true) brings it back. */
  fadeOutBgm(durationMs = 1500) {
    musicWanted = false;
    if (!ctx || !musicTimer) return;
    try {
      const d = Math.max(0.05, (Number(durationMs) || 0) / 1000);
      const now = ctx.currentTime;
      musicBus.gain.cancelScheduledValues(now);
      musicBus.gain.setValueAtTime(Math.max(0.0001, musicBus.gain.value), now);
      musicBus.gain.linearRampToValueAtTime(0, now + d);
      clearTimeout(fadeTimer);
      // Keep scheduling beats until the fade is done so it really fades.
      fadeTimer = setTimeout(() => {
        fadeTimer = null;
        if (!musicWanted && musicTimer) { clearInterval(musicTimer); musicTimer = null; }
      }, d * 1000 + 300);
    } catch { /* ignore */ }
  },
  /**
   * "Happy Birthday to You" on a synthesised music box, in F major to sit with
   * the Fmaj7 loop. Returns how long it lasts in ms (0 if muted or locked).
   */
  playMusicBoxBirthday({ delay = 0 } = {}) {
    try {
      if (!ready() || muted) return 0;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      stopBox(0.15);
      const bus = ctx.createGain();
      bus.gain.value = 0.6;
      bus.connect(master);
      boxBus = bus;
      const t0 = ctx.currentTime + 0.05 + Math.max(0, Number(delay) || 0);
      let t = t0;
      BIRTHDAY.forEach(([n, beats, chord], i) => {
        const last = i >= BIRTHDAY.length - 6; // gentle ritardando on the final line
        const len = beats * BOX_BEAT * (last ? 1 + (i - (BIRTHDAY.length - 6)) * 0.05 : 1);
        const human = (Math.random() - 0.5) * 0.012;
        const isEnd = i === BIRTHDAY.length - 1;
        pluck(NOTE[n], t + human, { vol: 0.15, decay: isEnd ? 3.2 : Math.min(2.2, 0.9 + len), bus });
        if (chord) {
          chord.forEach((c, k) => pluck(NOTE[c], t + human + (isEnd ? k * 0.09 : k * 0.012), { vol: 0.07, decay: isEnd ? 3.4 : 1.8, bus }));
        }
        t += len;
      });
      // A last high sparkle as the final note rings.
      pluck(NOTE.F6, t - 1.2, { vol: 0.05, decay: 2.4, bus });
      const end = t + 2.2;
      setTimeout(() => { if (boxBus === bus) boxBus = null; try { bus.disconnect(); } catch { /* ignore */ } }, (end - ctx.currentTime) * 1000 + 500);
      return Math.round((end - ctx.currentTime) * 1000);
    } catch {
      return 0;
    }
  },
  /** Stop the birthday tune early (short fade). */
  stopMusicBox() { stopBox(0.25); },
  /**
   * A gentle 3-note pentatonic arpeggio, shifted per friend (0-6, wraps), for
   * opening a friend's letter. delay in seconds.
   */
  playFriendChime(friendIndex, delay = 0) {
    try {
      if (!ready() || muted) return;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      const i = ((Math.floor(Number(friendIndex)) || 0) % 7 + 7) % 7;
      const t = ctx.currentTime + 0.02 + Math.max(0, Number(delay) || 0);
      [0, 2, 4].forEach((step, n) => pluck(pentatonic(i + step), t + n * 0.11, { vol: 0.12 - n * 0.015, decay: 1.5 - n * 0.2 }));
    } catch { /* ignore */ }
  },
  get muted() { return muted; },
  set muted(v) {
    muted = !!v;
    writeMuted(muted);
    try {
      if (master) {
        master.gain.cancelScheduledValues(ctx.currentTime);
        master.gain.setTargetAtTime(muted ? 0 : 1, ctx.currentTime, 0.03);
      }
    } catch { /* ignore */ }
    listeners.forEach((fn) => { try { fn(muted); } catch { /* ignore */ } });
  },
  toggleMute() { this.muted = !muted; return muted; },
  onMuteChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
  get unlocked() { return unlocked; },
};

// Resume after the tab returns (iOS suspends the context when backgrounded).
try {
  document.addEventListener('visibilitychange', () => {
    try { if (!document.hidden && ready() && ctx.state !== 'running') ctx.resume().catch(() => {}); } catch { /* ignore */ }
  });
} catch { /* ignore */ }

export default sound;
