// Campus Quest UI kit: pixel-styled DOM overlay above the Phaser canvas.
import './ui.css';
import { cssVars, pal } from './palette.js';
import { icon } from './icons.js';
import { particles, iris } from './fx.js';
import { POSTCARD_SCALE } from './postcard.js';
import { sound } from '../audio/sound.js';

export { sound };

let root = null;
const $ = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const asset = (p) => new URL(p, document.baseURI).href;
/** sprite may be a file stem ("friend-one"), a relative path or a URL/data URI. */
export function spriteURL(s) {
  if (!s) return '';
  if (/^(data:|blob:|https?:)/.test(s) || s.includes('/') || /\.\w{3,4}$/.test(s)) return /^(data:|blob:|https?:)/.test(s) ? s : asset(s);
  return asset(`assets/sprites/${s}.png`);
}
function ensure() { if (!root) throw new Error('initUI() must be called first'); }

function button(label, { cls = '', iconName = null, onClick, aria } = {}) {
  const b = $('button', `px-btn ${cls}`);
  b.type = 'button';
  b.innerHTML = (iconName ? icon(iconName, 28) : '') + (label ? `<span>${esc(label)}</span>` : '');
  if (aria || !label) b.setAttribute('aria-label', aria || iconName);
  b.addEventListener('click', (e) => { e.stopPropagation(); sound.play('tap'); onClick?.(e); });
  return b;
}

// ---------- textures generated at runtime (tiny PNGs) ----------
function textures() {
  const mk = (w, h, draw) => { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d')); return `url(${c.toDataURL()})`; };
  const paper = mk(32, 32, (g) => {
    const cols = [pal('cream'), pal('sand-light')];
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 70; i++) { g.fillStyle = cols[i % 2]; g.fillRect((rnd() * 32) | 0, (rnd() * 32) | 0, 1, 1); }
  });
  const torn = mk(8, 2, (g) => {
    g.fillStyle = pal('white');
    g.fillRect(0, 1, 8, 1);
    g.fillRect(0, 0, 3, 1); g.fillRect(5, 0, 2, 1);
  });
  const cork = mk(24, 24, (g) => {
    g.fillStyle = pal('tan'); g.fillRect(0, 0, 24, 24);
    const cols = [pal('sand'), pal('brown'), pal('sand'), pal('brown-dark')];
    let seed = 11;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 90; i++) { g.fillStyle = cols[i % 4]; g.fillRect((rnd() * 24) | 0, (rnd() * 24) | 0, 1, 1); }
  });
  root.style.setProperty('--paper-tex', paper);
  root.style.setProperty('--cork-tex', cork);
  root.style.setProperty('--torn', torn);
}

// ---------- fonts ----------
async function loadFonts() {
  const faces = [
    ['Pixelify Sans', 'assets/fonts/PixelifySans-VF.ttf', { weight: '400 700' }],
    ['Patrick Hand', 'assets/fonts/PatrickHand-Regular.ttf', {}],
    ['Silkscreen', 'assets/fonts/Silkscreen-Bold.ttf', {}],
  ];
  if (!('FontFace' in window) || !document.fonts) return;
  await Promise.all(faces.map(async ([fam, path, desc]) => {
    try {
      const f = new FontFace(fam, `url(${asset(path)})`, { display: 'swap', ...desc });
      document.fonts.add(f);
      await Promise.race([f.load(), new Promise((r) => setTimeout(r, 4000))]);
    } catch (e) { console.warn('[ui] font failed', fam, e?.message); }
  }));
}

/** Mount the overlay, inject palette/textures, load fonts. Resolves when ready. */
export async function initUI() {
  if (root) return root;
  root = $('div');
  root.id = 'ui';
  root.setAttribute('style', cssVars());
  document.body.appendChild(root);
  textures();
  root.appendChild(toastBox = $('div', 'cq-toasts'));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') escStack[escStack.length - 1]?.(); });
  await loadFonts();
  return root;
}

// ---------- modal helper ----------
const escStack = [];
let lockCount = 0;
function lock(on) {
  lockCount += on ? 1 : -1;
  document.documentElement.classList.toggle('cq-lock', lockCount > 0);
}
function modal(card, { onClose, backdropClose = true } = {}) {
  const m = $('div', 'cq-modal');
  const bd = $('div', 'cq-backdrop');
  m.append(bd, card);
  root.appendChild(m);
  lock(true);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    const i = escStack.indexOf(close); if (i >= 0) escStack.splice(i, 1);
    m.classList.add('closing');
    lock(false);
    setTimeout(() => m.remove(), 150);
    onClose?.();
  };
  if (backdropClose) bd.addEventListener('click', close);
  escStack.push(close);
  m.addEventListener('pointerdown', (e) => e.stopPropagation());
  return { el: m, close };
}

// ---------- loading ----------
export const loading = (() => {
  let el = null, bar = null, pct = null;
  const N = 12;
  const mount = () => {
    if (el) return;
    ensure();
    el = $('div', 'cq-loading');
    el.innerHTML = `<div class="heart">${icon('heart', 44)}</div><h1>Campus Quest</h1>`;
    bar = $('div', 'cq-bar'); for (let i = 0; i < N; i++) bar.appendChild($('i'));
    pct = $('div', 'pct', 'Loading 0%');
    el.append(bar, pct);
    root.appendChild(el);
  };
  return {
    set(p) {
      mount();
      const v = Math.max(0, Math.min(1, +p || 0));
      [...bar.children].forEach((c, i) => c.classList.toggle('on', i < Math.round(v * N)));
      pct.textContent = `Loading ${Math.round(v * 100)}%`;
    },
    hide() {
      if (!el) return Promise.resolve();
      const e = el; el = null;
      e.classList.add('hide');
      return new Promise((r) => setTimeout(() => { e.remove(); r(); }, 300));
    },
  };
})();

// ---------- intro ----------
export function showIntro({ onStart, skipHowTo = false, friendCount = 7 } = {}) {
  ensure();
  return new Promise((resolve) => {
    const el = $('div', 'cq-intro');
    const fx = particles(el, { mode: 'fall', count: 60 });
    const title = $('h1', 'cq-title', `<span class="stars">${icon('star', 28)}${icon('heart', 30)}${icon('star', 28)}</span>Happy Birthday,<span class="name">Vaishali!</span>`);
    const tap = $('div', 'cq-tap', 'Tap to start');
    el.append(title, tap);
    root.appendChild(el);
    let started = false;
    const start = (e) => {
      e?.stopPropagation();
      if (started) return;
      started = true;
      sound.unlock();
      sound.play('sparkle');
      el.style.pointerEvents = 'none';
      el.style.visibility = 'hidden';
      setTimeout(() => el.remove(), 400);
      fx.stop();
      (skipHowTo ? Promise.resolve() : howTo(friendCount)).then(() => { try { onStart?.(); } catch (err) { console.error(err); } resolve(); });
    };
    el.addEventListener('pointerup', start);
    const onKey = (e) => { if (e.key === 'Enter' || e.key === ' ') { document.removeEventListener('keydown', onKey); start(); } };
    document.addEventListener('keydown', onKey);
  });
}

function howTo(friendCount = 7) {
  return new Promise((resolve) => {
    const card = $('div', 'cq-card px-frame paper cq-letter');
    const rows = [
      ['star', 'Tap a building and you will walk there.'],
      ['heart', `Find all ${friendCount} friends and read their letters.`],
      ['recenter', 'Drag to look around. Pinch or scroll to zoom.'],
      ['book', 'The sticker book tracks who you have found.'],
    ];
    card.innerHTML = `<h2 class="cq-head">How to play</h2><div class="stitch" style="margin:10px -18px 14px"></div>
      <ul style="list-style:none;margin:0;padding:0;display:grid;gap:14px">${rows.map(([i, t]) =>
        `<li style="display:flex;gap:14px;align-items:center;font-size:19px;line-height:1.25"><span style="flex:none;width:36px;display:flex;justify-content:center;color:var(--plum)">${icon(i, 32)}</span><span>${t}</span></li>`).join('')}</ul>`;
    const acts = $('div', 'cq-actions');
    const m = modal(card, { backdropClose: false, onClose: resolve });
    acts.appendChild(button("Let's go!", { cls: 'primary', onClick: () => m.close() }));
    card.appendChild(acts);
  });
}

// ---------- letter ----------
export function showLetter({ id, name, sprite, title, text, photo, photoDate, photoLocation, photoCaption, chime = null, sfx = 'letter' } = {}) {
  ensure();
  if (Number.isInteger(chime)) {
    sound.play('paper');
    sound.playFriendChime(chime, 0.12);
  } else {
    sound.play(sfx);
  }
  return new Promise((resolve) => {
    const card = $('div', 'cq-card px-frame paper cq-letter');
    card.dataset.id = id ?? '';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-label', `Letter from ${name ?? ''}`);
    card.innerHTML = '<div class="torn top"></div><div class="torn bot"></div>';
    const sc = $('div', 'scroll');
    const who = $('div', 'who');
    if (sprite) {
      const img = $('img'); img.alt = ''; img.src = spriteURL(sprite);
      img.onerror = () => img.remove();
      img.onload = () => { const h = img.naturalHeight; img.style.height = `${h >= 80 ? h : Math.min(120, h * 3)}px`; }; // whole-number scale only
      who.appendChild(img);
    }
    who.appendChild($('div', '', `<div class="from">A letter from</div><div class="nm">${esc(name)}</div>`));
    sc.appendChild(who);
    sc.appendChild($('div', 'stitch'));
    if (title) sc.appendChild($('h2', '', esc(title)));
    sc.appendChild($('p', 'cq-body', esc(text)));
    if (photo) sc.appendChild(polaroid({ photo, date: photoDate, place: photoLocation, caption: photoCaption, name, onError: (pf) => pf.remove() }));
    card.appendChild(sc);
    const m = modal(card, { onClose: resolve });
    const x = button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() });
    card.appendChild(x);
    setTimeout(() => x.focus({ preventScroll: true }), 50);
  });
}

// ---------- polaroid ----------
// A photo in a polaroid frame that flips over (CSS 3D) on tap to show the
// date, a location stamp and a handwritten caption on the back.
// `photo` may be '' with `sprite` set: the front then shows the pixel sprite.
export function polaroid({ photo = '', sprite = '', date = '', place = '', caption = '', name = '', onError } = {}) {
  const wrap = $('div', 'polaroid');
  wrap.setAttribute('role', 'button');
  wrap.tabIndex = 0;
  wrap.setAttribute('aria-pressed', 'false');
  wrap.setAttribute('aria-label', 'Photo. Tap to flip it over.');
  const card = $('div', 'pol-card');
  const front = $('div', 'pol-face pol-front');
  const pic = $('div', 'pol-pic');
  const img = $('img');
  img.alt = '';
  img.draggable = false;
  const useSprite = () => {
    if (!sprite) { onError?.(wrap); return; }
    pic.classList.add('sprite');
    img.onerror = () => img.remove();
    img.src = spriteURL(sprite);
  };
  if (photo) {
    img.loading = 'lazy';
    img.onerror = useSprite;
    img.src = asset(photo);
  } else {
    useSprite();
  }
  pic.appendChild(img);
  front.append(pic, $('div', 'pol-hint', `${icon('replay', 14)}<span>Tap to flip</span>`));
  const back = $('div', 'pol-face pol-back');
  back.innerHTML = `${place ? `<div class="pol-stamp"><span>${esc(place)}</span></div>` : ''}`
    + `${date ? `<div class="pol-date">${esc(date)}</div>` : ''}`
    + `<p class="pol-cap">${esc(caption || (date || place ? '' : 'A little moment, kept safe.'))}</p>`
    + `${name ? `<div class="pol-sig">- ${esc(name)}</div>` : ''}`;
  card.append(front, back);
  wrap.appendChild(card);
  const flip = (e) => {
    e?.stopPropagation();
    const on = !wrap.classList.contains('flipped');
    wrap.classList.toggle('flipped', on);
    wrap.setAttribute('aria-pressed', String(on));
    sound.play('paper');
  };
  wrap.addEventListener('click', flip);
  wrap.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } });
  return wrap;
}

// ---------- a single photo ----------
// Opens one photo big as a flippable polaroid (the photos standing around
// campus). Resolves when closed.
export function showPhoto({ title = '', photo = '', date = '', place = '', caption = '' } = {}) {
  ensure();
  sound.play('paper');
  return new Promise((resolve) => {
    const c = $('div', 'cq-card px-frame paper cq-letter cq-inspect');
    if (title) c.innerHTML = `<h2 class="cq-head">${esc(title)}</h2>`;
    c.appendChild(polaroid({ photo, date, place, caption }));
    const m = modal(c, { onClose: resolve });
    c.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() }));
  });
}

// ---------- memory wall ----------
/**
 * Corkboard of everyone's photos. items: [{ id, name, sprite, found, photo,
 * photoDate, photoLocation, photoCaption }]. Found friends pin up as tilted
 * mini-polaroids (their sprite if there's no photo); the rest are "?" outlines.
 * Tapping one opens it big (flippable) with a button to re-read the letter.
 */
export function showMemoryWall({ title = 'Memory Wall', items = [], onOpenLetter } = {}) {
  ensure();
  sound.play('paper');
  return new Promise((resolve) => {
    const found = items.filter((f) => f.found).length;
    const card = $('div', 'cq-card cq-wall');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-label', title);
    card.innerHTML = `<h2 class="cq-head">${esc(title)}</h2><div class="count"><b>${found}</b> / ${items.length}</div>`;
    const board = $('div', 'cq-board');
    items.forEach((f, i) => {
      const rot = [-5, 3, -2, 6, -4, 2, -6, 4][i % 8];
      if (!f.found) {
        const slot = $('div', 'mini empty', '<span>?</span>');
        slot.style.setProperty('--rot', `${rot / 2}deg`);
        slot.setAttribute('aria-label', 'Not found yet');
        board.appendChild(slot);
        return;
      }
      const b = $('button', 'mini');
      b.type = 'button';
      b.style.setProperty('--rot', `${rot}deg`);
      b.setAttribute('aria-label', `${f.name}'s photo`);
      const pic = $('div', 'mini-pic');
      const img = $('img');
      img.alt = '';
      img.draggable = false;
      const spriteFallback = () => { pic.classList.add('sprite'); img.onerror = () => img.remove(); img.src = spriteURL(f.sprite); };
      if (f.photo) { img.loading = 'lazy'; img.onerror = spriteFallback; img.src = asset(f.photo); } else spriteFallback();
      pic.appendChild(img);
      b.append($('i', 'pin'), pic, $('div', 'mini-nm', esc(f.name)));
      b.addEventListener('click', () => { sound.play('tap'); inspect(f); });
      board.appendChild(b);
    });
    card.appendChild(board);
    const m = modal(card, { onClose: resolve });
    card.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() }));

    function inspect(f) {
      const c = $('div', 'cq-card px-frame paper cq-letter cq-inspect');
      c.innerHTML = `<h2 class="cq-head">${esc(f.name)}</h2>`;
      c.appendChild(polaroid({ photo: f.photo, sprite: f.sprite, date: f.photoDate, place: f.photoLocation, caption: f.photoCaption || f.title || '', name: f.name }));
      const acts = $('div', 'cq-actions');
      const im = modal(c);
      if (onOpenLetter) {
        acts.appendChild(button('Read letter', { cls: 'primary', iconName: 'heart', onClick: async () => {
          im.close();
          m.el.style.visibility = 'hidden';
          try { await onOpenLetter(f.id); } catch (e) { console.error(e); }
          m.el.style.visibility = '';
        } }));
      }
      c.appendChild(acts);
      c.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => im.close() }));
    }
  });
}

// ---------- action button ----------
// One wide pixel button at the bottom centre (e.g. "Memory Wall (3 / 7)").
export function actionButton({ label = '', iconName = null, onClick } = {}) {
  ensure();
  const b = button(label, { cls: 'cq-action', iconName, onClick });
  b.addEventListener('pointerdown', (e) => e.stopPropagation());
  root.appendChild(b);
  return {
    el: b,
    setLabel(t) { const sp = b.querySelector('span'); if (sp) sp.textContent = t; },
    remove() { b.remove(); },
  };
}

// ---------- quiz ----------
// One multiple-choice question before a letter. Options arrive already in
// display order; `answer` is the index of the right one in that order.
// Resolves true/false once she taps "Read the letter". Escape skips the
// quiz (resolves false) so it can never stand between her and a letter.
export function showQuiz({ name, sprite, question, options = [], answer = 0, correctLine = '', wrongLine = '' } = {}) {
  ensure();
  sound.play('letter');
  return new Promise((resolve) => {
    let result = null;
    const card = $('div', 'cq-card px-frame paper cq-quiz');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-label', `A question from ${name ?? ''}`);
    const sc = $('div', 'scroll');
    const who = $('div', 'who');
    if (sprite) {
      const img = $('img'); img.alt = ''; img.src = spriteURL(sprite);
      img.onerror = () => img.remove();
      img.onload = () => { const h = img.naturalHeight; img.style.height = `${h >= 80 ? h : Math.min(96, h * 2)}px`; };
      who.appendChild(img);
    }
    const speech = $('div', 'speech', `<div class="from">${esc(name)} asks...</div><p class="q">${esc(question)}</p>`);
    who.appendChild(speech);
    sc.appendChild(who);
    const list = $('div', 'cq-options');
    const btns = options.map((opt, i) => {
      const b = $('button', 'px-btn opt', `<span class="key">${i + 1}</span><span class="txt">${esc(opt)}</span>`);
      b.type = 'button';
      b.addEventListener('click', () => pick(i));
      list.appendChild(b);
      return b;
    });
    sc.appendChild(list);
    const react = $('div', 'cq-react');
    sc.appendChild(react);
    card.appendChild(sc);
    const m = modal(card, { backdropClose: false, onClose: () => { document.removeEventListener('keydown', onKey); resolve(result === true); } });
    const onKey = (e) => {
      const n = Number(e.key);
      if (result === null && n >= 1 && n <= btns.length) { e.preventDefault(); pick(n - 1); }
    };
    document.addEventListener('keydown', onKey);
    setTimeout(() => btns[0]?.focus({ preventScroll: true }), 50);

    function pick(i) {
      if (result !== null) return;
      result = i === answer;
      btns.forEach((b, j) => {
        b.disabled = true;
        if (j === answer) b.classList.add('right');
        else if (j === i) b.classList.add('wrong');
      });
      sound.play(result ? 'sparkle' : 'tap');
      const line = result ? correctLine : wrongLine;
      const reveal = result ? '' : `<div class="was">The answer was: <b>${esc(options[answer])}</b></div>`;
      react.className = `cq-react ${result ? 'yay' : 'nope'}`;
      react.innerHTML = `<div class="mark">${icon(result ? 'tick' : 'cross', 28)}</div><div><p class="line">${esc(line)}</p>${reveal}</div>`;
      const go = button('Read the letter', { cls: 'primary', iconName: 'heart', onClick: () => m.close() });
      go.classList.add('go');
      react.appendChild(go);
      if (result) burst(card);
      setTimeout(() => { go.focus({ preventScroll: true }); react.scrollIntoView({ block: 'nearest' }); }, 60);
    }
  });
}

// Little pixel sparkles around the card on a right answer (CSS only).
function burst(card) {
  for (let i = 0; i < 10; i++) {
    const s = $('i', 'cq-spark');
    s.style.left = `${8 + Math.round(Math.random() * 84)}%`;
    s.style.top = `${10 + Math.round(Math.random() * 70)}%`;
    s.style.animationDelay = `${i * 40}ms`;
    s.style.background = pal(['yellow', 'pink-pale', 'mint', 'white'][i % 4]);
    card.appendChild(s);
    setTimeout(() => s.remove(), 900);
  }
}

// ---------- sticker book ----------
export function showStickerBook({ friends = [], onOpen, onReset } = {}) {
  ensure();
  return new Promise((resolve) => {
    const card = $('div', 'cq-card px-frame cq-book');
    const found = friends.filter((f) => f.found).length;
    card.innerHTML = `<h2 class="cq-head">Sticker Book</h2><div class="count"><b>${found}</b> / ${friends.length} found</div>`;
    const grid = $('div', 'cq-grid');
    friends.forEach((f, i) => {
      const s = $('button', `slot${f.found ? ' found' : ''}`);
      s.type = 'button';
      s.style.setProperty('--rot', `${[-2, 1, 2, -1][i % 4]}deg`);
      const src = spriteURL(f.sprite);
      s.innerHTML = `<div class="spr">${src ? `<img alt="" src="${esc(src)}">` : ''}</div><div class="nm">${f.found ? esc(f.name) : '???'}</div>${f.found ? `<span class="hrt">${icon('heart', 18)}</span>` : ''}${f.quiz === true ? `<span class="qz ok" title="Quiz: right">${icon('tick', 20)}</span>` : f.quiz === false ? `<span class="qz no" title="Quiz: wrong">${icon('cross', 20)}</span>` : ''}`;
      s.querySelector('img')?.addEventListener('error', (e) => e.target.remove());
      if (f.found) {
        s.setAttribute('aria-label', `Read ${f.name}'s letter`);
        s.addEventListener('click', async () => {
          sound.play('tap');
          m.el.style.visibility = 'hidden';
          try { await onOpen?.(f.id); } catch (e) { console.error(e); }
          m.el.style.visibility = '';
        });
      } else { s.disabled = true; s.setAttribute('aria-label', 'Not found yet'); }
      grid.appendChild(s);
    });
    card.appendChild(grid);
    if (onReset) {
      const acts = $('div', 'cq-actions');
      acts.appendChild(button('Start over', { iconName: 'replay', onClick: confirmReset }));
      card.appendChild(acts);
    }
    const m = modal(card, { onClose: resolve });
    card.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() }));

    // Asks first, so a stray tap can't wipe her progress.
    function confirmReset() {
      const c = $('div', 'cq-card px-frame paper cq-letter cq-confirm');
      c.innerHTML = '<h2 class="cq-head">Start over?</h2><p>Every letter locks again and the game restarts from the title screen.</p>';
      const a = $('div', 'cq-actions');
      const cm = modal(c);
      a.append(
        button('Cancel', { onClick: () => cm.close() }),
        button('Start over', { cls: 'primary', iconName: 'replay', onClick: () => onReset() }),
      );
      c.appendChild(a);
    }
  });
}

// ---------- HUD ----------
export const hud = (() => {
  let el = null, btns = {}, badge = null, muteBtn = null, cbs = {};
  const setMuteIcon = () => {
    if (!muteBtn) return;
    muteBtn.innerHTML = icon(sound.muted ? 'mute' : 'speaker', 30);
    muteBtn.setAttribute('aria-label', sound.muted ? 'Unmute' : 'Mute');
  };
  return {
    mount({ onBook, onRecenter, onBack } = {}) {
      ensure();
      cbs = { onBook, onRecenter, onBack };
      if (el) return;
      el = $('div', 'cq-hud');
      btns.back = button('', { cls: 'icon tl hidden', iconName: 'back', aria: 'Back to map', onClick: () => cbs.onBack?.() });
      muteBtn = button('', { cls: 'icon tr', onClick: () => { sound.unlock(); sound.toggleMute(); } });
      btns.book = button('', { cls: 'icon tr hidden', iconName: 'book', aria: 'Sticker book', onClick: () => cbs.onBook?.() });
      btns.book.style.right = 'calc(78px + var(--sar))';
      badge = $('span', 'badge', '0/0'); btns.book.appendChild(badge);
      btns.recenter = button('', { cls: 'icon br hidden', iconName: 'recenter', aria: 'Recenter', onClick: () => cbs.onRecenter?.() });
      el.append(btns.back, btns.book, muteBtn, btns.recenter);
      el.addEventListener('pointerdown', (e) => { if (e.target.closest('.px-btn')) e.stopPropagation(); });
      root.appendChild(el);
      setMuteIcon();
      sound.onMuteChange(setMuteIcon);
    },
    /** list of 'book' | 'recenter' | 'back' to show; the mute toggle is always visible. */
    show(list = []) {
      if (!el) return;
      for (const k of Object.keys(btns)) btns[k].classList.toggle('hidden', !list.includes(k));
    },
    setCounter(found, total) { if (badge) badge.textContent = `${found}/${total}`; },
    pulseBook() {
      const b = btns.book; if (!b) return;
      b.classList.remove('pulse'); void b.offsetWidth; b.classList.add('pulse');
      sound.play('sparkle');
    },
  };
})();

// ---------- toast ----------
let toastBox = null;
const toastQ = [];
let toastBusy = false;
export function toast(text, ms = 2500) {
  ensure();
  toastQ.push([text, ms]);
  if (!toastBusy) nextToast();
}
function nextToast() {
  const item = toastQ.shift();
  if (!item) { toastBusy = false; return; }
  toastBusy = true;
  const t = $('div', 'cq-toast', esc(item[0]));
  t.setAttribute('role', 'status');
  toastBox.appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => { t.remove(); nextToast(); }, 200); }, item[1]);
}

// ---------- bubble ----------
export function bubble(text, x, y, ms = 2200) {
  ensure();
  const b = $('div', 'cq-bubble', esc(text));
  b.style.visibility = 'hidden';
  root.appendChild(b);
  const W = window.innerWidth, r = { width: b.offsetWidth, height: b.offsetHeight }; // offset*: unaffected by the pop-in scale
  const M = 12;
  let left = Math.round(x - r.width / 2);
  left = Math.max(M, Math.min(W - M - r.width, left));
  let top = Math.round(y - r.height - 18);
  let below = false;
  if (top < M) { top = Math.round(y + 18); below = true; }

  b.style.left = `${left}px`; b.style.top = `${top}px`;
  const tailX = Math.max(10, Math.min(r.width - 22, x - left - 3));
  const tail = $('div', 'tail', `<svg width="15" height="12" viewBox="0 0 5 4" shape-rendering="crispEdges"><rect x="0" y="0" width="1" height="1" fill="${pal('ink')}"/><rect x="1" y="0" width="1" height="1" fill="${pal('cream')}"/><rect x="2" y="0" width="1" height="1" fill="${pal('cream')}"/><rect x="3" y="0" width="1" height="1" fill="${pal('cream')}"/><rect x="4" y="0" width="1" height="1" fill="${pal('ink')}"/><rect x="1" y="1" width="1" height="1" fill="${pal('ink')}"/><rect x="2" y="1" width="1" height="1" fill="${pal('cream')}"/><rect x="3" y="1" width="1" height="1" fill="${pal('cream')}"/><rect x="4" y="1" width="1" height="1" fill="${pal('ink')}"/><rect x="2" y="2" width="1" height="1" fill="${pal('ink')}"/><rect x="3" y="2" width="1" height="1" fill="${pal('cream')}"/><rect x="4" y="2" width="1" height="1" fill="${pal('ink')}"/><rect x="3" y="3" width="1" height="1" fill="${pal('ink')}"/><rect x="4" y="3" width="1" height="1" fill="${pal('ink')}"/></svg>`);
  tail.style.left = `${tailX}px`;
  if (below) { tail.style.bottom = 'auto'; tail.style.top = '-12px'; tail.style.transform = 'scaleY(-1)'; }
  b.appendChild(tail);
  b.style.transformOrigin = `${tailX}px ${below ? 0 : '100%'}`;
  b.style.visibility = '';
  const kill = () => b.remove();
  setTimeout(kill, ms);
  return { close: kill };
}

// ---------- transition ----------
// Calls are serialised, and out() while already closed (or in() while open)
// is a no-op, so overlapping scene changes can never strand the iris canvas
// on top of the page.
export const transition = (() => {
  let cv = null;
  let chain = Promise.resolve();
  const run = (fn) => (chain = chain.then(fn, fn));
  return {
    out() {
      ensure();
      return run(async () => {
        if (cv) return;
        sound.play('whoosh');
        cv = await iris(root, 'out', cv);
        cv.style.pointerEvents = 'auto';
      });
    },
    in() {
      ensure();
      return run(async () => {
        if (!cv) return;
        const c = cv;
        cv = null;
        await iris(root, 'in', c);
        c.remove();
      });
    },
  };
})();

// ---------- confetti ----------
export function confetti(ms = 3000) {
  ensure();
  sound.play('confetti');
  const p = particles(root, { mode: 'burst', count: 110, ms });
  // particles stop themselves once the last piece falls off-screen
  setTimeout(() => p.stop(), ms + 8000);
  return new Promise((r) => setTimeout(r, ms));
}

// ---------- finale ----------
export function showFinaleUI({ message = '', onReplay, credits = [], score = null, onKeepsake = null } = {}) {
  ensure();
  const el = $('div', 'cq-finale');
  const flagCols = ['coral', 'yellow', 'mint', 'sky', 'lilac', 'pink-pale'];
  const flags = Array.from({ length: 12 }, (_, i) => `<i style="background:${pal(flagCols[i % flagCols.length])}"></i>`).join('');
  el.innerHTML = `<div class="bunting"><div class="flags">${flags}</div><h1>Happy Birthday!</h1></div>`;
  const card = $('div', 'cq-card px-frame paper cq-letter');
  card.innerHTML = '<div class="torn top"></div><div class="torn bot"></div>';
  card.appendChild($('p', 'cq-body', esc(message)));
  if (score && score.total) {
    card.appendChild($('div', 'cq-score', `<div class="num">${icon('star', 22)} Quiz score <b>${score.right} / ${score.total}</b></div>${score.line ? `<p>${esc(score.line)}</p>` : ''}`));
  }
  const acts = $('div', 'cq-actions');
  acts.append(
    button('Replay', { cls: 'primary', iconName: 'replay', onClick: () => { close(); onReplay?.(); } }),
    button('Credits', { iconName: 'star', onClick: showCredits }),
  );
  if (onKeepsake) {
    const kb = button('Save Keepsake', { iconName: 'save', onClick: async () => {
      if (kb.disabled) return;
      kb.disabled = true;
      kb.classList.add('busy');
      try { await onKeepsake(); } catch (e) { console.error(e); toast("Couldn't make the postcard, sorry!"); }
      kb.disabled = false;
      kb.classList.remove('busy');
    } });
    acts.appendChild(kb);
  }
  card.appendChild(acts);
  el.appendChild(card);
  root.appendChild(el);
  function showCredits() {
    const c = $('div', 'cq-card px-frame paper cq-letter');
    c.innerHTML = `<h2 class="cq-head">Credits</h2><div class="stitch" style="margin:10px -18px 14px"></div>`;
    const ul = $('ul', 'cq-credits scroll');
    (Array.isArray(credits) ? credits : String(credits).split('\n')).forEach((l) => ul.appendChild($('li', '', esc(l))));
    c.appendChild(ul);
    const m = modal(c);
    c.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() }));
  }
  function close() { el.remove(); }
  return { close };
}

// ---------- keepsake postcard ----------
// In-app browsers (WhatsApp, Instagram, Facebook, Android WebViews, iOS
// WKWebViews) often can't download files and may even navigate away to the
// image, so there we rely on the preview's long-press save instead.
function inAppBrowser() {
  const ua = navigator.userAgent || '';
  if (/WhatsApp|FBAN|FBAV|FB_IAB|Instagram|Line\/|Snapchat|; wv\)/i.test(ua)) return true;
  const iOS = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  return iOS && !/Safari\//.test(ua);
}

function download(blob, fileName) {
  try {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    return true;
  } catch {
    return false;
  }
}

/**
 * Save a finished postcard canvas: triggers a PNG download (where that works)
 * and shows a preview to long-press, plus Download / Share buttons.
 * Resolves once the preview is open, with { close, closed } (closed resolves
 * when she dismisses it).
 */
export async function showKeepsake({ canvas, fileName = 'birthday-keepsake.png', title = 'Your keepsake' } = {}) {
  ensure();
  const dataURL = canvas.toDataURL('image/png');
  const blob = await new Promise((r) => {
    try { canvas.toBlob((b) => r(b), 'image/png'); } catch { r(null); }
  });
  const canDownload = !!blob && !inAppBrowser() && 'download' in HTMLAnchorElement.prototype;
  if (canDownload) download(blob, fileName);
  sound.play('sparkle');

  let resolveClosed;
  const closed = new Promise((r) => { resolveClosed = r; });
  const c = $('div', 'cq-card px-frame paper cq-letter cq-keepsake');
  c.innerHTML = `<h2 class="cq-head">${esc(title)}</h2>`;
  const img = $('img');
  img.alt = title;
  img.src = dataURL; // a data: URL long-presses to "Save image" even in in-app browsers
  // Show it at a whole number of device pixels per art pixel.
  const artW = canvas.width / POSTCARD_SCALE;
  const artH = canvas.height / POSTCARD_SCALE;
  const dpr = window.devicePixelRatio || 1;
  const availW = Math.min(window.innerWidth - 80, 360);
  const availH = window.innerHeight * 0.56;
  const k = Math.max(1, Math.floor(Math.min((availW * dpr) / artW, (availH * dpr) / artH)));
  img.style.width = `${(artW * k) / dpr}px`;
  img.style.height = `${(artH * k) / dpr}px`;
  const frame = $('div', 'kp-frame');
  frame.appendChild(img);
  c.appendChild(frame);
  c.appendChild($('p', 'kp-hint', canDownload ? 'Check your downloads, or long-press the image to save it.' : 'Long-press the image to save it.'));
  const acts = $('div', 'cq-actions');
  if (canDownload) acts.appendChild(button('Download', { iconName: 'save', onClick: () => { if (!download(blob, fileName)) toast('Long-press the image to save it.'); } }));
  let file = null;
  try { file = blob && typeof File === 'function' ? new File([blob], fileName, { type: 'image/png' }) : null; } catch { file = null; }
  if (file && navigator.canShare?.({ files: [file] })) {
    acts.appendChild(button('Share', { cls: 'primary', iconName: 'heart', onClick: () => { navigator.share({ files: [file], title }).catch(() => {}); } }));
  }
  c.appendChild(acts);
  const m = modal(c, { onClose: () => resolveClosed() });
  c.appendChild(button('', { cls: 'icon close', iconName: 'close', aria: 'Close', onClick: () => m.close() }));
  return { close: m.close, closed };
}
