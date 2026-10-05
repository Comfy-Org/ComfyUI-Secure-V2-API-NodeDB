import assert from "node:assert/strict";

import {
  createResizeController,
  handleCenters,
  hitTestHandles,
  resizeFromCorner,
} from "../web/geometry.js";

const position = { x: 10, y: 20 };
const size = { width: 100, height: 80 };
const minimum = { width: 40, height: 30 };
const cases = [
  ["tl", { x: 15, y: 15 }, { x: 25, y: 35 }, { width: 85, height: 65 }],
  ["tr", { x: 15, y: 15 }, { x: 10, y: 35 }, { width: 115, height: 65 }],
  ["bl", { x: 15, y: 15 }, { x: 25, y: 20 }, { width: 85, height: 95 }],
  ["br", { x: 15, y: 15 }, { x: 10, y: 20 }, { width: 115, height: 95 }],
];
for (const [corner, delta, nextPosition, nextSize] of cases) {
  const resized = resizeFromCorner(position, size, corner, delta, minimum);
  assert.deepEqual(resized.position, nextPosition);
  assert.deepEqual(resized.size, nextSize);
  const opposite = {
    x: corner.includes("l")
      ? resized.position.x + resized.size.width
      : resized.position.x,
    y: corner.includes("t")
      ? resized.position.y + resized.size.height
      : resized.position.y,
  };
  assert.deepEqual(opposite, {
    x: corner.includes("l") ? 110 : 10,
    y: corner.includes("t") ? 100 : 20,
  });
}

assert.deepEqual(handleCenters({ x: 1, y: 2, width: 3, height: 4 }), [
  { corner: "tl", x: 1, y: 2 },
  { corner: "tr", x: 4, y: 2 },
  { corner: "bl", x: 1, y: 6 },
  { corner: "br", x: 4, y: 6 },
]);
assert.equal(hitTestHandles(
  { x: 19, y: 0 },
  [{ corner: "tl", x: 0, y: 0 }, { corner: "tr", x: 20, y: 0 }],
  20,
), "tr");
assert.equal(hitTestHandles({ x: 21, y: 0 }, [{ corner: "tl", x: 0, y: 0 }], 20), undefined);

assert.deepEqual(
  resizeFromCorner(position, size, "tl", { x: 200, y: 200 }, {
    width: Number.NaN, height: Number.POSITIVE_INFINITY,
  }),
  { position: { x: 110, y: 100 }, size: { width: 0, height: 0 } },
);

const controller = createResizeController();
const target = {
  id: "node:n1",
  bounds: { x: 10, y: -10, width: 100, height: 110 },
  position,
  size,
  minimum,
};
assert.equal(controller.onPointerDown({ pointerId: 1, x: 60, y: 60 }, target, 18), undefined);
assert.deepEqual(
  controller.onPointerDown({ pointerId: 1, x: 10, y: -10 }, target, 18),
  { type: "grab", targetId: "node:n1", corner: "tl" },
);
assert.equal(controller.onPointerMove({ pointerId: 2, x: 40, y: 40 }), undefined);
assert.equal(controller.onPointerEnd(2), undefined);
assert.equal(controller.locked, true);
assert.deepEqual(controller.reset(), { type: "release", targetId: "node:n1" });
assert.equal(controller.locked, false);

console.log("touch resize geometry: PASS");
