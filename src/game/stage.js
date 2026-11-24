// Location and finale scenes draw a fixed 384x576 stage: the 192x288
// background art at 2x (ART_SCALE) so the ~96 px characters keep their faces.
// The stage is shown at the largest whole-number zoom that fits.
export const ART_SCALE = 2;
export const STAGE_W = 192 * ART_SCALE;
export const STAGE_H = 288 * ART_SCALE;

export function fitStage(scene, { reserveTop = 0, reserveBottom = 0 } = {}) {
  const cam = scene.cameras.main;
  cam.setBackgroundColor('#3b2f3f');
  const apply = () => {
    const { width, height } = scene.scale;
    const availH = Math.max(1, height - reserveTop - reserveBottom);
    const z = Math.max(1, Math.floor(Math.min(width / STAGE_W, availH / STAGE_H)));
    cam.setZoom(z);
    // Centre horizontally; sit the stage just below the HUD strip vertically.
    const usedH = STAGE_H * z;
    const top = reserveTop + Math.max(0, Math.floor((availH - usedH) / 2));
    cam.centerOn(STAGE_W / 2, STAGE_H / 2 + (height / 2 - (top + usedH / 2)) / z);
    cam.scrollX = Math.round(cam.scrollX * z) / z;
    cam.scrollY = Math.round(cam.scrollY * z) / z;
  };
  apply();
  scene.scale.on('resize', apply);
  scene.events.once('shutdown', () => scene.scale.off('resize', apply));
  return apply;
}

// Screen position (CSS px) of a stage point, for DOM bubbles.
export function stageToScreen(scene, x, y) {
  const cam = scene.cameras.main;
  return { x: (x - cam.worldView.x) * cam.zoom, y: (y - cam.worldView.y) * cam.zoom };
}
