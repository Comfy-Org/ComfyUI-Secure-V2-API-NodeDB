// Duration Pixaroma - the ready-made model recipes.
//
// These are STARTING POINTS you pick from, not a live link: choosing one COPIES
// its numbers onto the node. That is deliberate - two Duration nodes on one
// canvas can then be set up for two different models, and editing this list in a
// later release can never reach back and change a saved workflow.
//
// The frame rules were checked against model docs and node source, not memory
// (2026-08-03). The FRAME RULE is the reliable part; FPS varies by model
// version, which is exactly why fps stays an editable field on the node rather
// than being hidden inside the recipe.
//
//   MiniMax H3   17n + 5   24 fps    (matches the user's own working workflow)
//   Wan 2.x       4n + 1   16 fps
//   Hunyuan       4n + 1   24 fps
//   LTX           8n + 1   24 fps
//
// `step: 1` means no snapping at all, so "just seconds x fps" is a recipe like
// any other rather than a special mode.
//
// To add a model: append a row. Nothing else needs to change - the picker, the
// preview and the arrows all read this array.

export const RECIPES = [
  {
    name: "MiniMax H3",
    fps: 24, step: 17, plus: 5, minFrames: 5,
    hint: "every 17 frames, plus 5",
  },
  {
    name: "Wan 2.x",
    fps: 16, step: 4, plus: 1, minFrames: 1,
    hint: "every 4 frames, plus 1",
  },
  {
    name: "Hunyuan",
    fps: 24, step: 4, plus: 1, minFrames: 1,
    hint: "every 4 frames, plus 1",
  },
  {
    name: "LTX",
    fps: 24, step: 8, plus: 1, minFrames: 1,
    hint: "every 8 frames, plus 1",
  },
  {
    name: "Plain frames",
    fps: 24, step: 1, plus: 0, minFrames: 1,
    hint: "no rounding, seconds x fps",
  },
];

// The escape hatch lives in the SAME list, because only one of them can be
// active at a time and a separate toggle would let you set a recipe and a
// formula at once with no way to tell which is running.
export const CUSTOM_NAME = "Custom formula";

export function recipeByName(name) {
  return RECIPES.find((r) => r.name === name) || null;
}

/** Which recipe do these numbers correspond to, if any? */
export function matchRecipe(st) {
  if (st.mode === "custom") return CUSTOM_NAME;
  const hit = RECIPES.find((r) =>
    r.fps === st.fps && r.step === st.step && r.plus === st.plus && r.minFrames === st.minFrames);
  // No match is normal and fine - it means the numbers were hand-tuned, and the
  // picker says so rather than pretending one of the presets is selected.
  return hit ? hit.name : null;
}

/** The patch that selecting a recipe applies. */
export function recipePatch(name) {
  if (name === CUSTOM_NAME) return { mode: "custom", recipeName: CUSTOM_NAME };
  const r = recipeByName(name);
  if (!r) return null;
  return {
    mode: "recipe", recipeName: r.name,
    fps: r.fps, step: r.step, plus: r.plus, minFrames: r.minFrames,
  };
}
