// Dev preview: exercises every UI kit component with sample data.
// Usage: import('./ui/preview.js').then(m => m.runPreview()) e.g. behind ?ui-preview.
import * as ui from './index.js';

const SAMPLE_SPRITE = (() => {
  const c = document.createElement('canvas'); c.width = 16; c.height = 28;
  const g = c.getContext('2d');
  const r = (col, x, y, w, h) => { g.fillStyle = col; g.fillRect(x, y, w, h); };
  r('#1d1b2a', 4, 0, 8, 2); r('#1d1b2a', 3, 2, 10, 8); r('#dcae7a', 4, 3, 8, 7);
  r('#1d1b2a', 6, 6, 1, 1); r('#1d1b2a', 9, 6, 1, 1); r('#f08a72', 7, 8, 2, 1);
  r('#1d1b2a', 3, 10, 10, 11); r('#7a4e8c', 4, 11, 8, 9); r('#dcae7a', 2, 13, 1, 5); r('#dcae7a', 13, 13, 1, 5);
  r('#1d1b2a', 4, 21, 3, 6); r('#1d1b2a', 9, 21, 3, 6); r('#3f6fb0', 5, 21, 1, 5); r('#3f6fb0', 10, 21, 1, 5);
  return c.toDataURL();
})();

const FRIENDS = ['Ananya', 'Rahul', 'Sneha', 'Karthik', 'Priya', 'Arjun', 'Meghana'].map((name, i) => ({
  id: `f${i}`, name, sprite: SAMPLE_SPRITE, found: i < 4,
}));
const TEXT = 'Happy birthday!!\n\nRemember the day we bunked the lab and ate four plates of momos at the canteen? I still laugh about it.\n\nYou make every boring Monday better. Never change.\n\n- with love';

export async function runPreview(step = new URLSearchParams(location.search).get('step') || 'all') {
  await ui.initUI();
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  window.__ui = ui;
  if (step === 'loading') { ui.loading.set(0.58); return; }
  if (step === 'intro') { ui.showIntro({ onStart: () => ui.toast('Started!') }); return; }
  if (step === 'howto') { ui.showIntro({}); await wait(100); document.querySelector('.cq-intro').dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); return; }
  ui.hud.mount({ onBook: () => ui.showStickerBook({ friends: FRIENDS, onOpen: openF }), onRecenter: () => ui.toast('Recentered'), onBack: () => ui.toast('Back') });
  ui.hud.show(['book', 'recenter', 'back']); ui.hud.setCounter(4, 7);
  const openF = (id) => { const f = FRIENDS.find((x) => x.id === id); return ui.showLetter({ ...f, title: 'That canteen day', text: TEXT }); };
  if (step === 'hud') { ui.toast('You found Sneha!'); ui.toast('Second toast queued'); ui.bubble('Hi Vaishali! Tap me!', 60, 300, 60000); ui.bubble('Over here!', 330, 40, 60000); return; }
  if (step === 'letter') { ui.showLetter({ ...FRIENDS[0], title: 'That canteen day', text: TEXT, photo: 'assets/photos/does-not-exist.jpg' }); return; }
  if (step === 'photo') { ui.showLetter({ ...FRIENDS[1], title: 'Polaroid', text: 'Short one.', photo: SAMPLE_SPRITE }); return; }
  if (step === 'book') { ui.showStickerBook({ friends: FRIENDS, onOpen: openF }); return; }
  if (step === 'iris') { await ui.transition.out(); return; }
  if (step === 'irishalf') { ui.transition.out(); return; }
  if (step === 'finale') { ui.hud.show([]); ui.showFinaleUI({ message: 'From all seven of us: happy birthday, Vaishali! Thank you for four years of chaos, chai and kindness. We love you!', credits: ['Made by your friends', 'Fonts: Pixelify Sans, Patrick Hand (SIL OFL)', 'Map data: OpenStreetMap contributors'], onReplay: () => ui.toast('Replay') }); ui.confetti(3000); return; }
  // all: quick tour
  ui.loading.set(0.3); await wait(400); ui.loading.set(1); await ui.loading.hide();
  await ui.showIntro({});
  ui.toast('Welcome!');
  await openF('f0');
  await ui.transition.out(); await ui.transition.in();
}
