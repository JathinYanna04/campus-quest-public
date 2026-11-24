// Progress that survives a refresh. Every storage access is wrapped so the
// game still works in private windows or with storage blocked.
const KEY = 'campus-quest:v1';

function load() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) {
      const s = JSON.parse(raw);
      if (s && typeof s === 'object') return s;
    }
  } catch {
    /* storage unavailable */
  }
  return {};
}

// Opening the site with ?reset (e.g. https://example.com/?reset)
// wipes this browser's saved progress and starts again from the title screen.
// The parameter is then removed from the address bar so a refresh keeps the
// new progress.
function consumeResetParam() {
  try {
    const url = new URL(window.location.href);
    if (!url.searchParams.has('reset')) return;
    url.searchParams.delete('reset');
    window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    window.localStorage.removeItem(KEY);
  } catch {
    /* storage or history unavailable: nothing saved to wipe */
  }
}

consumeResetParam();
const saved = load();

export const state = {
  read: saved.read && typeof saved.read === 'object' ? saved.read : {},
  finaleDone: !!saved.finaleDone,
  // Quiz answers: friendId -> true (right) / false (wrong or skipped).
  quiz: saved.quiz && typeof saved.quiz === 'object' ? saved.quiz : {},
  introSeen: !!saved.introSeen,
  // Where Vaishali stands on the map when the map scene starts.
  lastLocation: typeof saved.lastLocation === 'string' ? saved.lastLocation : null,
  // Easter-egg line counters: "map:<spot>" / "loc:<location>:<zone>" -> taps so far.
  eggs: saved.eggs && typeof saved.eggs === 'object' ? saved.eggs : {},
};

export function save() {
  try {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        read: state.read,
        finaleDone: state.finaleDone,
        quiz: state.quiz,
        introSeen: state.introSeen,
        lastLocation: state.lastLocation,
        eggs: state.eggs,
      }),
    );
  } catch {
    /* storage unavailable: progress lasts for this session only */
  }
}

export function markRead(id) {
  if (state.read[id]) return false;
  state.read[id] = true;
  save();
  return true;
}

export function recordQuiz(id, correct) {
  state.quiz[id] = !!correct;
  save();
}

// Next line of an easter egg, cycling through `lines` in order (back to the
// first after the last). The counter persists, so she picks up where she
// left off after a refresh. Returns null when there is nothing to say.
export function nextEggLine(key, lines) {
  const list = (Array.isArray(lines) ? lines : []).filter((l) => typeof l === 'string' && l.trim());
  if (!list.length) return null;
  const n = Number.isInteger(state.eggs[key]) && state.eggs[key] >= 0 ? state.eggs[key] : 0;
  state.eggs[key] = n + 1;
  save();
  return list[n % list.length];
}

// Counts one tap on something that has no lines (e.g. a place photo), so its
// sparkle stops once she has found it.
export function markSeen(key) {
  state.eggs[key] = (state.eggs[key] | 0) + 1;
  save();
}

export function eggSeen(key) {
  return (state.eggs[key] | 0) > 0;
}

// Wipes everything saved in this browser and reloads, so the game starts again
// from the title screen with every letter locked. Used by the Sticker Book's
// "Start over" button.
export function startOver() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: progress only lived in memory anyway */
  }
  window.location.reload();
}

export function resetProgress() {
  state.read = {};
  state.quiz = {};
  state.finaleDone = false;
  state.lastLocation = null;
  save();
}
