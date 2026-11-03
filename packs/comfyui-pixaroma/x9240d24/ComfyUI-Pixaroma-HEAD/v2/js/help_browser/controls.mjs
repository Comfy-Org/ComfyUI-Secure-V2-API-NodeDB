// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Help browser - what each control does                ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Replaced the drawn wiring diagram (removed 2026-07-28). A picture of a node
// drawn from its definition could never show the thing people actually get
// stuck on - what a particular button or field is FOR - and it did not look
// enough like the real node to be worth the space.
//
// This lists the node's inputs, settings and outputs as a plain reference, and
// where the node's Python already carries a `tooltip` or an OUTPUT_TOOLTIPS
// entry, that text is used as the explanation. So it is exactly as good as the
// documentation the node already ships with, it never contradicts the node,
// and writing a tooltip improves BOTH the ComfyUI Info panel and this page at
// once. Nothing to keep in sync.
//
// What it deliberately does NOT try to cover: buttons that live in the node's
// JS (Load Image's Upload, the editors' Open buttons, Resolution's ratio
// chips). Those are not in the definition and cannot be read from it - they
// are documented by hand in the node's help def, which is the right place for
// prose about a custom face.

import { el } from "./window.mjs";

const PRIMITIVE = new Set(["INT", "FLOAT", "STRING", "BOOLEAN"]);

function typeOf(spec) {
  const t = Array.isArray(spec) ? spec[0] : spec;
  if (Array.isArray(t)) return "choice";
  return typeof t === "string" ? t : "?";
}

export function nodeDefFor(comfyClass) {
  try {
    return window.LiteGraph?.registered_node_types?.[comfyClass]?.nodeData || null;
  } catch {
    return null;
  }
}

// -> { inputs, settings, outputs } where each entry is {name, type, tip, dflt}
export function readControls(comfyClass) {
  const def = nodeDefFor(comfyClass);
  if (!def) return null;

  const inputs = [], settings = [];
  // `hidden` inputs carry our serialized state and never appear on the node,
  // so listing them would describe something the reader cannot see.
  for (const bucket of ["required", "optional"]) {
    const group = def.input?.[bucket];
    if (!group) continue;
    for (const [name, spec] of Object.entries(group)) {
      const type = typeOf(spec);
      const opts = Array.isArray(spec) ? spec[1] : null;
      const o = (opts && typeof opts === "object") ? opts : {};
      const forced = !!o.forceInput;
      // The same for the saved state of a node with its own editor (Note's and
      // Info's note_json, Label's label_json): declared as a text input so the
      // editor can store into it, but hidden on the node, and its default is a
      // block of JSON. Listed, it showed the raw JSON as a "setting" and the
      // user rightly asked what it meant. A JSON-object default is the mark.
      if (typeof o.default === "string" && /^\s*\{/.test(o.default)) continue;
      const entry = {
        name,
        type,
        tip: typeof o.tooltip === "string" ? o.tooltip : "",
        dflt: o.default,
        optional: bucket === "optional",
        choices: Array.isArray(spec) && Array.isArray(spec[0]) ? spec[0] : null,
      };
      // A primitive is a field you type in; anything else is a socket you wire.
      (PRIMITIVE.has(type) || type === "choice") && !forced
        ? settings.push(entry)
        : inputs.push(entry);
    }
  }

  const types = def.output || [];
  const names = def.output_name || [];
  const tips = def.output_tooltips || [];
  const outputs = types.map((t, i) => ({
    name: names[i] || (typeof t === "string" ? t.toLowerCase() : "out"),
    type: Array.isArray(t) ? "choice" : t,
    tip: typeof tips[i] === "string" ? tips[i] : "",
  }));

  return { inputs, settings, outputs, isOutput: !!def.output_node };
}

// The def's own token is written for code, not for a reader: BOOLEAN is a word
// that appears nowhere on the node itself, and the caps sat oddly beside the
// lowercase "choice" we derive.
//
// **These plain words are for the SETTINGS group ONLY.** The same tokens are
// also WIRE types the moment they appear as a forced input or as an output, and
// there the chip has to match the label printed beside the dot on the node:
// "What you wire in" and "What comes out" exist to answer what plugs into what,
// so `width_a` must read INT there, exactly as Switch WH shows it, and Seed's
// output must read INT, not "number". A field you type into has no dot to
// match, so it is free to be readable.
const TYPE_WORDS = {
  BOOLEAN: "on / off",
  INT: "number",
  FLOAT: "number",
  STRING: "text",
};
const typeWord = (t, plain) => (plain && TYPE_WORDS[t]) || t;

// "default false" is the same problem in the value column.
function defaultWord(item) {
  if (item.type === "BOOLEAN") return item.dflt ? "on" : "off";
  return String(item.dflt);
}

function row(item, showDefault, plainTypes) {
  const r = el("div", "pixhb-ctl");
  const head = el("div", "pixhb-ctl-h");
  head.appendChild(el("span", "pixhb-ctl-n", item.name));
  head.appendChild(el("span", "pixhb-ctl-t", typeWord(item.type, plainTypes)));
  if (item.optional) head.appendChild(el("span", "pixhb-ctl-opt", "optional"));
  // A false default has to survive this test, or every off-by-default switch
  // silently loses its default line.
  if (showDefault && item.dflt !== undefined && item.dflt !== "") {
    head.appendChild(el("span", "pixhb-ctl-d", "default " + defaultWord(item)));
  }
  r.appendChild(head);
  if (item.tip) r.appendChild(el("div", "pixhb-ctl-tip", item.tip));
  // A choice field is far clearer when you can see the options.
  if (item.choices && item.choices.length && item.choices.length <= 12) {
    const c = el("div", "pixhb-ctl-ch");
    item.choices.forEach((v) => c.appendChild(el("span", "pixhb-ctl-chv", String(v))));
    r.appendChild(c);
  }
  return r;
}

// A node with 16 numbered rows (Switch Source has a_1..a_16, b_1..b_16 and
// output_1..output_16) would otherwise print 48 near-identical entries, which
// buries everything else on the page. A run of three or more controls sharing a
// name prefix and differing only by a trailing number collapses to one entry,
// with the row number written as N so the sentence still reads correctly.
// Split "a_12" into ["a_", "12"], or null when the name does not end in digits.
function splitNumbered(name) {
  const m = /^(.*?)(\d+)$/.exec(name);
  return m ? { prefix: m[1], num: m[2] } : null;
}

function collapseNumbered(items) {
  const out = [];
  let i = 0;
  while (i < items.length) {
    const head = splitNumbered(items[i].name);
    if (!head) { out.push(items[i]); i += 1; continue; }
    // Walk the run of following controls sharing this prefix. Compared by
    // string, not by a built regex, so a prefix containing regex characters
    // cannot break the match.
    let j = i;
    while (j < items.length) {
      const p = splitNumbered(items[j].name);
      if (!p || p.prefix !== head.prefix) break;
      j += 1;
    }
    const run = items.slice(i, j);
    if (run.length >= 3) {
      const first = run[0], last = run[run.length - 1];
      // "row 1" -> "row N" and "output_1" -> "output_N", while leaving a number
      // that is part of something larger (16, 2048) alone.
      // Only replace the number when it stands alone. Splitting on the digits
      // and repairing afterwards mangled anything adjacent: with num "1",
      // "0.1" became "0.N" and "11" became "NN".
      const isDigit = (ch) => ch >= "0" && ch <= "9";
      const generalise = (s) => {
        const str = String(s || "");
        let out = "", i = 0;
        while (i < str.length) {
          if (str.startsWith(head.num, i)) {
            const end = i + head.num.length;
            const before = str[i - 1], after = str[end];
            // Part of a longer number, so leave it: an adjacent digit (11, 21),
            // or a decimal point with a digit on its far side (0.1, 1.0). A
            // full stop that ENDS a sentence is not a decimal, so "Row 1."
            // still becomes "Row N.".
            const partOfNumber =
              isDigit(before) || isDigit(after) ||
              (before === "." && isDigit(str[i - 2])) ||
              (after === "." && isDigit(str[end + 1]));
            if (!partOfNumber) { out += "N"; i = end; continue; }
          }
          out += str[i]; i += 1;
        }
        return out;
      };
      out.push({ ...first, name: `${first.name} to ${last.name}`,
                 tip: generalise(first.tip), choices: null, dflt: undefined });
    } else {
      out.push(...run);
    }
    i = j;
  }
  return out;
}

// `plainTypes` is true ONLY for the settings group. See TYPE_WORDS: the wired
// groups must keep the real type name so the chip matches the node's own dot.
function group(title, items, showDefault, plainTypes, note) {
  if (!items.length) return null;
  const sec = el("div", "pixhb-sect");
  sec.appendChild(el("p", "pixhb-h", title));
  if (note) sec.appendChild(el("p", "pixhb-ctl-note", note));
  const box = el("div", "pixhb-ctls");
  collapseNumbered(items).forEach((it) => box.appendChild(row(it, showDefault, plainTypes)));
  sec.appendChild(box);
  return sec;
}

// Returns an array of sections, or [] when the node has nothing to list.
// The help def may already have its own "Outputs" or "Inputs" section written
// by hand. Printing the generated one as well says the same thing twice on the
// same page, which reads as a mistake. `covered` names the roles to skip.
export function buildControls(comfyClass, covered = {}) {
  const c = readControls(comfyClass);
  if (!c) return [];
  const out = [];
  //                                                    showDefault, plainTypes
  const inputs = covered.inputs ? null : group("What you wire in", c.inputs, false, false);
  const settings = covered.settings ? null : group("The settings on the node", c.settings, true, true);
  const outputs = covered.outputs ? null : group("What comes out", c.outputs, false, false);
  if (inputs) out.push(inputs);
  if (settings) out.push(settings);
  if (outputs) out.push(outputs);
  else if (c.isOutput && !covered.outputs) {
    const sec = el("div", "pixhb-sect");
    sec.appendChild(el("p", "pixhb-h", "What comes out"));
    sec.appendChild(el("p", "pixhb-ctl-note", "Nothing. This is the end of a chain - it shows or saves what reaches it."));
    out.push(sec);
  }
  return out;
}
