export const CANVAS_SIZE = 600;

export const UV_MAP = Object.freeze({
  head: [0, 0, 110, 170], neck: [120, 0, 52, 80], chest: [180, 0, 170, 170],
  abdomen: [360, 0, 150, 150], armL: [0, 180, 60, 180], armR: [70, 180, 60, 180],
  foreArmL: [140, 180, 52, 160], foreArmR: [200, 180, 52, 160],
  handClosedL: [260, 180, 52, 64], handClosedR: [320, 180, 52, 64],
  handOpenL: [380, 180, 68, 76], handOpenR: [456, 180, 68, 76],
  footL: [540, 180, 72, 90], footR: [620, 180, 72, 90],
  legL: [0, 370, 80, 220], legR: [90, 370, 80, 220],
  shinL: [180, 370, 68, 210], shinR: [258, 370, 68, 210],
  headBack: [0, 610, 110, 170], chestBack: [120, 610, 170, 170],
  abdomenBack: [300, 610, 150, 150],
});

const S = (name, parent, length, angle, uv, width, slide = false, min = 10, max = 100) =>
  ({ name, parent, length, angle, uv, width, slide, min, max });

export const BONE_SPECS = Object.freeze([
  S('Root', null, 0, 0, null, 0),
  S('Abdomen', 'Root', 65, -Math.PI / 2, 'abdomen', 80),
  S('Chest', 'Abdomen', 65, 0, 'chest', 90),
  S('Neck', 'Chest', 28, 0, 'neck', 26), S('Head', 'Neck', 58, 0, 'head', 55),
  S('LeftEyeBase', 'Neck', 28, -0.4, null, 0), S('RightEyeBase', 'Neck', 28, 0.4, null, 0),
  S('LeftEye', 'LeftEyeBase', 2, 0, null, 0, true, 0, 7),
  S('RightEye', 'RightEyeBase', 2, 0, null, 0, true, 0, 7),
  S('LeftShoulder', 'Chest', 35, -Math.PI / 2, null, 0, true, 15, 80),
  S('RightShoulder', 'Chest', 35, Math.PI / 2, null, 0, true, 15, 80),
  S('LeftArm', 'LeftShoulder', 55, -Math.PI / 2 + 0.3, 'armL', 30),
  S('LeftForeArm', 'LeftArm', 75, 0, 'foreArmL', 26),
  S('LeftHand', 'LeftForeArm', 28, 0, 'handClosedL', 28),
  S('RightArm', 'RightShoulder', 55, Math.PI / 2 - 0.3, 'armR', 30),
  S('RightForeArm', 'RightArm', 75, 0, 'foreArmR', 26),
  S('RightHand', 'RightForeArm', 28, 0, 'handClosedR', 28),
  S('LeftHip', 'Root', 25, Math.PI, null, 0, true, 10, 60),
  S('RightHip', 'Root', 25, 0, null, 0, true, 10, 60),
  S('LeftLeg', 'LeftHip', 72, -Math.PI / 2 + 0.1, 'legL', 40),
  S('LeftShin', 'LeftLeg', 103, 0, 'shinL', 34), S('LeftFoot', 'LeftShin', 30, Math.PI / 2, 'footL', 36),
  S('RightLeg', 'RightHip', 72, Math.PI / 2 - 0.1, 'legR', 40),
  S('RightShin', 'RightLeg', 103, 0, 'shinR', 34), S('RightFoot', 'RightShin', 30, Math.PI / 2, 'footR', 36),
]);

const clone = (value) => JSON.parse(JSON.stringify(value));

export class PoseModel {
  constructor() { this.reset(); }

  reset() {
    this.camera = { x: 0, y: 0, zoom: 1 };
    this.variants = { headBack: false, bodyBack: false, leftOpen: false, rightOpen: false };
    this.bones = BONE_SPECS.map((spec) => ({ ...spec, localAngle: spec.angle, gx: 0, gy: 0, endX: 0, endY: 0, gAngle: 0 }));
    this.update();
  }

  update() {
    const byName = new Map(this.bones.map((bone) => [bone.name, bone]));
    for (const bone of this.bones) {
      const parent = bone.parent ? byName.get(bone.parent) : undefined;
      bone.gx = parent ? parent.endX : CANVAS_SIZE / 2;
      bone.gy = parent ? parent.endY : CANVAS_SIZE * 0.533;
      bone.gAngle = (parent?.gAngle ?? 0) + bone.localAngle;
      bone.endX = bone.gx + Math.cos(bone.gAngle) * bone.length;
      bone.endY = bone.gy + Math.sin(bone.gAngle) * bone.length;
    }
  }

  screenToWorld(x, y) {
    return {
      x: (x - CANVAS_SIZE / 2) / this.camera.zoom + CANVAS_SIZE / 2 - this.camera.x,
      y: (y - CANVAS_SIZE / 2) / this.camera.zoom + CANVAS_SIZE / 2 - this.camera.y,
    };
  }

  pan(dx, dy) { this.camera.x += dx / this.camera.zoom; this.camera.y += dy / this.camera.zoom; }
  zoom(delta) { this.camera.zoom = Math.max(0.2, Math.min(5, this.camera.zoom - delta * 0.001)); }

  nearest(worldX, worldY) {
    let selected;
    let distance = Infinity;
    for (const bone of [...this.bones].reverse()) {
      const d = Math.hypot(bone.endX - worldX, bone.endY - worldY);
      const hit = (bone.name.includes('Eye') ? 15 : 20) / this.camera.zoom;
      if (d < hit && d < distance) { selected = bone; distance = d; }
    }
    return selected;
  }

  drag(name, worldX, worldY) {
    const bone = this.bones.find((entry) => entry.name === name);
    if (!bone || name === 'Root') return false;
    const parent = bone.parent ? this.bones.find((entry) => entry.name === bone.parent) : undefined;
    bone.localAngle = Math.atan2(worldY - bone.gy, worldX - bone.gx) - (parent?.gAngle ?? 0);
    if (bone.slide) bone.length = Math.max(bone.min, Math.min(bone.max, Math.hypot(worldX - bone.gx, worldY - bone.gy)));
    this.update();
    return true;
  }

  toggle(part) {
    if (!(part in this.variants)) throw new Error(`Unknown pose variant: ${part}`);
    this.variants[part] = !this.variants[part];
    const find = (name) => this.bones.find((bone) => bone.name === name);
    if (part === 'headBack') find('Head').uv = this.variants[part] ? 'headBack' : 'head';
    if (part === 'bodyBack') {
      find('Chest').uv = this.variants[part] ? 'chestBack' : 'chest';
      find('Abdomen').uv = this.variants[part] ? 'abdomenBack' : 'abdomen';
    }
    const hand = part === 'leftOpen' ? find('RightHand') : part === 'rightOpen' ? find('LeftHand') : null;
    if (hand) {
      const side = part === 'leftOpen' ? 'R' : 'L';
      hand.uv = this.variants[part] ? `handOpen${side}` : `handClosed${side}`;
      hand.width = this.variants[part] ? 36 : 28;
      hand.length = this.variants[part] ? 34 : 28;
    }
    this.update();
    return this.variants[part];
  }

  snapshot() {
    return clone({ camera: this.camera, variants: this.variants, bones: this.bones.map(({ name, localAngle, length }) => ({ name, localAngle, length })) });
  }

  restore(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.bones) || snapshot.bones.length !== this.bones.length) throw new Error('Invalid pose snapshot');
    const prior = new PoseModel();
    this.bones = prior.bones;
    this.camera = clone(snapshot.camera);
    this.variants = clone(snapshot.variants);
    for (const saved of snapshot.bones) {
      const bone = this.bones.find((entry) => entry.name === saved.name);
      if (!bone || !Number.isFinite(saved.localAngle) || !Number.isFinite(saved.length)) throw new Error('Invalid pose snapshot');
      bone.localAngle = saved.localAngle; bone.length = saved.length;
    }
    for (const key of ['headBack', 'bodyBack', 'leftOpen', 'rightOpen']) {
      if (this.variants[key]) { this.variants[key] = false; this.toggle(key); }
    }
    this.update();
  }
}

export class PoseHistory {
  constructor(limit = 64) { this.limit = limit; this.undoStack = []; this.redoStack = []; }
  remember(snapshot) { this.undoStack.push(clone(snapshot)); if (this.undoStack.length > this.limit) this.undoStack.shift(); this.redoStack.length = 0; }
  undo(current) { if (!this.undoStack.length) return null; this.redoStack.push(clone(current)); return this.undoStack.pop(); }
  redo(current) { if (!this.redoStack.length) return null; this.undoStack.push(clone(current)); return this.redoStack.pop(); }
}

export function frameRect(mode, width, height, backgroundAspect, display = 384) {
  let aspect = mode === 'Custom' ? width / height : mode === 'Background' && backgroundAspect ? backgroundAspect : 1;
  let w = display; let h = display;
  if (aspect >= 1) h = Math.round(display / aspect); else w = Math.round(display * aspect);
  return { x: Math.round((display - w) / 2), y: Math.round((display - h) / 2), w, h };
}
