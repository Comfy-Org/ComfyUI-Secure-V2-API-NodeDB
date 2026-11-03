// AI Prompt Pixaroma - the recipe file format.
//
// A formula on its own is HALF a recipe. The Krea 2 wording writes cleanly at
// temperature 0.3 and rambles, invents objects or refuses at 0.7 on the same
// model and the same words, so a file that carries only the prose hands
// somebody something that looks broken. This carries the settings too, and the
// model it was measured with.
//
// WHY A READABLE .txt AND NOT JSON. Three reasons, in order of how much they
// matter:
//   1. it can be pasted into a chat message and read by a person who does not
//      have this plugin - which is how these actually get shared;
//   2. the one number that matters most (temperature) is visible and editable
//      in Notepad, without knowing what JSON is;
//   3. it degrades: anything we cannot parse is still just text.
//
// BACKWARDS COMPATIBLE BY CONSTRUCTION. A file that does not begin with the
// header line is treated as a plain formula, exactly as Import did before this
// format existed. So every .txt already exported, and any old prompt file
// somebody has lying about, still imports as the wording. That is also why a
// header with no `---` keeps the WHOLE text as the formula rather than
// guessing: never lose the user's words to a parse.

import { DEFAULT_STATE, SETTING_KEYS } from "./core.mjs";

export const RECIPE_HEADER = "# Pixaroma AI Prompt recipe";
const SEP_LINE = "---";

// Derived from DEFAULT_STATE rather than listed again, so adding a boolean
// setting cannot leave this behind. Same reason SETTING_KEYS is imported and
// not copied.
const BOOL_KEYS = new Set(
  SETTING_KEYS.filter((key) => typeof DEFAULT_STATE[key] === "boolean"),
);

const TRUE_WORDS = ["yes", "true", "on", "1"];
const FALSE_WORDS = ["no", "false", "off", "0"];

// The settings that take a FRACTION. A comma decimal is rescued for these and
// only these: much of the world writes 0,3, and the whole point of a readable
// .txt is that people hand-edit it.
//
// The two integer settings are excluded because a comma there is far more
// likely a thousands separator, and reading "max_length: 1,024" as 1.024 would
// be a guess at what the writer meant. Be honest about what that buys, though:
// parseFloat("1,024") is 1 and readState truncates, so that file caps the
// answer at ONE TOKEN either way. Excluding them avoids GUESSING; it does not
// protect anybody. Rejecting a comma outright for integer keys would be the
// real improvement, and is deliberately left for its own change.
//
// Listed by hand rather than derived from DEFAULT_STATE because
// presence_penalty defaults to 0.0, which Number.isInteger calls an integer.
const FRACTION_KEYS = new Set([
  "temperature", "top_p", "min_p", "repetition_penalty", "presence_penalty",
]);

/** One line, no line breaks: a header value must not be able to end the header. */
function oneLine(value) {
  return String(value == null ? "" : value).replace(/[\r\n]+/g, " ").trim();
}

/**
 * A recipe as text: a small readable header, `---`, then the formula verbatim.
 *
 * Booleans are written yes/no rather than true/false because the file is meant
 * to be read by people, and parsing accepts either.
 */
export function formatRecipe(recipe) {
  const r = recipe || {};
  const lines = [RECIPE_HEADER];
  if (oneLine(r.name)) lines.push("name: " + oneLine(r.name));
  if (oneLine(r.model)) lines.push("model: " + oneLine(r.model));
  if (oneLine(r.note)) lines.push("note: " + oneLine(r.note));

  const settings = r.settings && typeof r.settings === "object" ? r.settings : {};
  for (const key of SETTING_KEYS) {
    const value = settings[key];
    if (value == null) continue;
    lines.push(key + ": " + (BOOL_KEYS.has(key) ? (value ? "yes" : "no") : String(value)));
  }

  lines.push(SEP_LINE);
  return lines.join("\n") + "\n" + String(r.formula == null ? "" : r.formula);
}

function coerce(key, value) {
  if (BOOL_KEYS.has(key)) {
    const word = value.toLowerCase();
    if (TRUE_WORDS.includes(word)) return true;
    if (FALSE_WORDS.includes(word)) return false;
    return null;
  }
  // parseFloat("0,3") is 0, which is FINITE, so it used to be accepted and
  // then clamped to the floor: a file reading 0,3 behaving as 0.01, the exact
  // "the formula looks broken" failure this format exists to prevent. Nothing
  // formatRecipe writes contains a comma, so this only ever rescues human
  // input. See FRACTION_KEYS for why it is scoped by key.
  const decimal = FRACTION_KEYS.has(key) && /^[+-]?\d+,\d+$/.test(value);
  const n = parseFloat(decimal ? value.replace(",", ".") : value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Text -> { name, note, model, settings, formula, hadHeader }.
 *
 * Never throws and never returns an empty formula for non-empty input: the
 * worst case is that the whole text becomes the formula, which is precisely
 * what a plain .txt should do.
 *
 * Values are NOT clamped here. Everything goes onto the node through
 * writeState, and readState clamps every field on the way back out, so a file
 * claiming `temperature: 900` cannot reach Python.
 */
export function parseRecipe(raw) {
  // \r\n from a Windows editor, and \r alone from an old one. Normalising here
  // means the header match, the separator match and the stored formula are all
  // free of stray carriage returns, which otherwise survive into the textarea.
  const text = String(raw == null ? "" : raw).replace(/\r\n?/g, "\n");
  const plain = {
    name: "", note: "", model: "", settings: {}, formula: text, hadHeader: false,
  };

  const lines = text.split("\n");
  let start = 0;
  while (start < lines.length && !lines[start].trim()) start += 1;
  if (start >= lines.length || lines[start].trim() !== RECIPE_HEADER) return plain;

  let sepAt = -1;
  for (let i = start + 1; i < lines.length; i += 1) {
    if (lines[i].trim() === SEP_LINE) { sepAt = i; break; }
  }
  // A header with no separator is a file somebody has broken by hand. There is
  // no way to tell where the formula starts, so keep everything as the formula.
  if (sepAt === -1) return plain;

  const out = {
    name: "", note: "", model: "", settings: {},
    // Only the FIRST separator splits, so a formula containing its own `---`
    // line survives a round trip untouched.
    formula: lines.slice(sepAt + 1).join("\n"),
    hadHeader: true,
  };

  for (let i = start + 1; i < sepAt; i += 1) {
    const line = lines[i];
    if (!line.trim()) continue;
    const at = line.indexOf(":");
    if (at < 0) continue;                       // a stray line is ignored, not fatal
    const key = line.slice(0, at).trim().toLowerCase();
    const value = line.slice(at + 1).trim();    // split on the FIRST colon, so a
    if (key === "name") out.name = value;       // name may contain one
    else if (key === "note") out.note = value;
    else if (key === "model") out.model = value;
    else if (SETTING_KEYS.includes(key)) {
      const coerced = coerce(key, value);
      if (coerced != null) out.settings[key] = coerced;
    }
  }
  return out;
}

/** A filename stem for a recipe: its name if it has one, else the node's. */
export function recipeFileStem(name, nodeTitle) {
  const raw = String(name || nodeTitle || "AI Prompt").trim() || "AI Prompt";
  const stem = raw
    .replace(/[^A-Za-z0-9 _-]+/g, "")
    .replace(/\s+/g, "-")
    // "Krea 2 - text to image" would otherwise become "Krea-2---text-to-image".
    // This is a file people send to each other, so it should not look sloppy.
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return stem || "ai-prompt-recipe";
}
