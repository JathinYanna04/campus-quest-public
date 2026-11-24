// Map camera: drag to pan (with inertia), pinch / wheel to zoom, clamped to
// the map, smooth follow, and tap detection that never fires after a drag.

const TAP_SLOP = 10; // CSS px a finger may wiggle and still count as a tap
const TAP_MS = 450;

export class MapCamera {
  constructor(scene, mapW, mapH, { onTap } = {}) {
    this.scene = scene;
    this.cam = scene.cameras.main;
    this.mapW = mapW;
    this.mapH = mapH;
    this.onTap = onTap;
    this.vx = 0;
    this.vy = 0;
    this.follow = null; // { x, y } object to follow (reads .x/.y each frame)
    this.following = false;
    this.pointers = new Map();
    this.pinch = null;
    this.enabled = true;

    this.cam.setBounds(0, 0, mapW, mapH);
    this.cam.roundPixels = true;
    scene.input.addPointer(2);

    const input = scene.input;
    input.on('pointerdown', this.down, this);
    input.on('pointermove', this.move, this);
    input.on('pointerup', this.up, this);
    input.on('pointerupoutside', this.up, this);
    input.on('wheel', this.wheel, this);
    scene.scale.on('resize', this.resize, this);
    scene.events.once('shutdown', () => {
      input.off('pointerdown', this.down, this);
      input.off('pointermove', this.move, this);
      input.off('pointerup', this.up, this);
      input.off('pointerupoutside', this.up, this);
      input.off('wheel', this.wheel, this);
      scene.scale.off('resize', this.resize, this);
      clearTimeout(this.wheelTimer);
    });
    this.resize();
  }

  // Zoom limits depend on the screen: never smaller than "whole map fits",
  // never so big that pixels get silly.
  limits() {
    const { width, height } = this.scene.scale;
    const fit = Math.max(width / this.mapW, height / this.mapH);
    const min = Math.max(1, Math.ceil(fit - 0.001)); // whole numbers only
    const max = 6;
    return { min: Math.min(min, max), max };
  }

  defaultZoom() {
    const { width, height } = this.scene.scale;
    // About 140 map px (70 m) across the short side of the screen.
    const z = Math.round(Math.min(width, height) / 130);
    return this.clampZoom(Math.max(2, Math.min(4, z)));
  }

  clampZoom(z) {
    const { min, max } = this.limits();
    return Math.max(min, Math.min(max, z));
  }

  resize() {
    this.setZoom(this.cam.zoom || this.defaultZoom());
  }

  setZoom(z, sx, sy) {
    const cam = this.cam;
    const { width, height } = this.scene.scale;
    sx = sx ?? width / 2;
    sy = sy ?? height / 2;
    const before = cam.getWorldPoint(sx, sy);
    cam.setZoom(this.clampZoom(z));
    cam.preRender();
    const after = cam.getWorldPoint(sx, sy);
    cam.scrollX += before.x - after.x;
    cam.scrollY += before.y - after.y;
  }

  centerOn(x, y) {
    this.cam.centerOn(x, y);
  }

  startFollow(target) {
    this.follow = target;
    this.following = true;
    this.vx = this.vy = 0;
  }

  stopFollow() {
    this.following = false;
  }

  down(p) {
    if (!this.enabled) return;
    this.pointers.set(p.id, { x: p.x, y: p.y, sx: p.x, sy: p.y, t: p.downTime, moved: false });
    this.vx = this.vy = 0;
    if (this.pointers.size === 2) this.beginPinch();
  }

  beginPinch() {
    const [a, b] = [...this.pointers.values()];
    this.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: this.cam.zoom };
    for (const q of this.pointers.values()) q.moved = true; // a pinch is never a tap
  }

  move(p) {
    const q = this.pointers.get(p.id);
    if (!q || !p.isDown) return;
    const dx = p.x - q.x;
    const dy = p.y - q.y;
    q.x = p.x;
    q.y = p.y;
    if (Math.hypot(p.x - q.sx, p.y - q.sy) > TAP_SLOP) q.moved = true;

    if (this.pointers.size >= 2 && this.pinch) {
      const [a, b] = [...this.pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const cx = (a.x + b.x) / 2;
      const cy = (a.y + b.y) / 2;
      this.setZoom((this.pinch.z * d) / this.pinch.d, cx, cy);
      this.cam.scrollX -= dx / 2 / this.cam.zoom;
      this.cam.scrollY -= dy / 2 / this.cam.zoom;
      this.following = false;
      return;
    }
    if (q.moved) {
      this.cam.scrollX -= dx / this.cam.zoom;
      this.cam.scrollY -= dy / this.cam.zoom;
      const dt = Math.max(1, p.event?.timeStamp - (q.lastT || p.event?.timeStamp - 16) || 16);
      q.lastT = p.event?.timeStamp;
      // velocity in world px per ms, smoothed
      this.vx = this.vx * 0.6 + (-dx / this.cam.zoom / dt) * 0.4;
      this.vy = this.vy * 0.6 + (-dy / this.cam.zoom / dt) * 0.4;
      this.following = false;
    }
  }

  // After a pinch or wheel gesture settles, ease to a whole-number zoom so
  // every art pixel is the same size on screen (no shimmer on dithering).
  snapZoom(sx, sy) {
    const { min, max } = this.limits();
    let z = Math.round(this.cam.zoom);
    if (z < min) z = min; // fully zoomed out may be fractional (whole map)
    z = Math.min(max, z);
    if (Math.abs(z - this.cam.zoom) < 0.001) return;
    const from = this.cam.zoom;
    this.snapTween?.stop();
    this.snapTween = this.scene.tweens.addCounter({
      from: 0,
      to: 1,
      duration: 160,
      ease: 'Sine.Out',
      onUpdate: (t) => this.setZoom(from + (z - from) * t.getValue(), sx, sy),
    });
  }

  up(p) {
    const q = this.pointers.get(p.id);
    this.pointers.delete(p.id);
    if (this.pinch && this.pointers.size < 2) this.snapZoom(p.x, p.y);
    if (this.pointers.size < 2) this.pinch = null;
    if (!q || !this.enabled) return;
    const wasPinching = this.pointers.size > 0;
    const far = Math.hypot(p.x - q.sx, p.y - q.sy) > TAP_SLOP; // touchmoves can be dropped
    if (!q.moved && !far && !wasPinching && p.upTime - q.t < TAP_MS) {
      this.vx = this.vy = 0;
      const w = this.cam.getWorldPoint(p.x, p.y);
      this.onTap?.(w.x, w.y, p.x, p.y);
    }
    // Inertia only if the finger was still moving when lifted.
    if (!q.moved || p.upTime - (q.lastT ? q.lastT : 0) > 80) {
      if (p.event && q.lastT && p.event.timeStamp - q.lastT > 80) this.vx = this.vy = 0;
    }
  }

  wheel(p, over, dx, dy) {
    if (!this.enabled) return;
    const factor = Math.exp(-dy * 0.0015);
    this.setZoom(this.cam.zoom * factor, p.x, p.y);
    clearTimeout(this.wheelTimer);
    this.wheelTimer = setTimeout(() => this.snapZoom(p.x, p.y), 180);
  }

  update(delta) {
    const cam = this.cam;
    if (this.pointers.size === 0 && (Math.abs(this.vx) > 0.001 || Math.abs(this.vy) > 0.001)) {
      cam.scrollX += this.vx * delta;
      cam.scrollY += this.vy * delta;
      const decay = Math.pow(0.992, delta);
      this.vx *= decay;
      this.vy *= decay;
    }
    if (this.following && this.follow && this.pointers.size === 0) {
      const tx = this.follow.x - cam.width / 2;
      const ty = this.follow.y - cam.height / 2;
      const k = 1 - Math.pow(0.9, delta / 16.67);
      cam.scrollX += (tx - cam.scrollX) * k;
      cam.scrollY += (ty - cam.scrollY) * k;
    }
  }
}
