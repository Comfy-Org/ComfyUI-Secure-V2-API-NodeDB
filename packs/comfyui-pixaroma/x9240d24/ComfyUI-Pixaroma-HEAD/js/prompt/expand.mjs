// Prompt Pixaroma - @tag -> snippet-text expansion, *category -> random-tag
// wildcards, and #list -> one random LINE of a tag (one level, no nesting).
//
// Used by BOTH the node body (live "Show expanded" preview + coloured highlighting)
// and the app.graphToPrompt hook (the real swap at queue time). Keep it pure so the
// two never disagree. The RANDOMNESS does NOT live here - the caller passes
// resolveWild() / resolveList() callbacks (a random pick at run time, a stable
// placeholder in the preview), so expand.mjs stays deterministic + testable.

import { getTags } from "./library.mjs";

// @name = a saved tag; *name = a random-from-category wildcard; #name = a random
// LINE from that tag's text. name = letters / digits / _ / - .
const TOKEN_RE = /([@*#])([a-zA-Z0-9_\-]+)/g;
const KIND_BY_SYM = { "@": "tag", "*": "wild", "#": "list" };

// Left-to-right scan for @tag, *wild and #list tokens. A token counts when it's at
// the very start, after a NON-word char (space, comma, ...), OR immediately after a
// SAME-KIND token (a chain like @a@b / #a#b). This lets adjacent tokens work while
// leaving an email's "user@name" (and arithmetic like "2*2") alone - their symbol
// sits after a word char with no preceding token. Returns
// [{kind:'tag'|'wild'|'list', sym, name, start, end, raw}]. Shared by scanTags /
// scanWilds / scanLists / expandAll AND the node's highlight backdrop so all of them
// agree on exactly which tokens count.
// The character before index `at` as a whole CODE POINT. `text[at-1]` alone is a UTF-16
// code UNIT, so for a supplementary-plane character (CJK Extension B, math letters, ...)
// it hands back a lone low surrogate - general category Cs, which \p{L}/\p{N}/\p{M}
// never match - and a tag glued to such a letter would wrongly expand ("𠀀@tag").
export function prevCodePoint(text, at) {
  if (!(at > 0)) return "";
  const c = text[at - 1];
  if (at >= 2 && c >= "\uDC00" && c <= "\uDFFF") {
    const hi = text[at - 2];
    if (hi >= "\uD800" && hi <= "\uDBFF") return hi + c;   // rejoin the pair
  }
  return c;
}

export function scanTokens(text) {
  const out = [];
  if (typeof text !== "string" || !/[@*#]/.test(text)) return out;
  TOKEN_RE.lastIndex = 0;
  let m, lastEnd = -1, lastKind = null;
  while ((m = TOKEN_RE.exec(text))) {
    const at = m.index;
    const kind = KIND_BY_SYM[m[1]];
    const prev = prevCodePoint(text, at);
    // Unicode-aware: a letter/number/combining-mark/_ before the symbol (incl.
    // accented / CJK, precomposed OR decomposed) means it's an email local part or
    // arithmetic, not a token - UNLESS it chains off a SAME-KIND token immediately
    // before it (@a@b, *a*b, #a#b). Cross-kind is deliberately NOT chained: an unknown
    // *wildcard must never promote a following @tag into expanding (or vice-versa) -
    // that would silently rewrite the prompt. Adjacency like @tag*Cat just needs a space.
    const chains = at === lastEnd && kind === lastKind;
    const isTok = !prev || !/[\p{L}\p{N}\p{M}_]/u.test(prev) || chains;
    if (isTok) {
      out.push({ kind, sym: m[1], name: m[2], start: at, end: at + m[0].length, raw: m[0] });
      lastEnd = at + m[0].length; // a following SAME-KIND token can chain off this one
      lastKind = kind;
    }
    // a non-token @/* does NOT update lastEnd/lastKind, so it can't start a chain
  }
  return out;
}

// @tags only (back-compat: same shape the highlight/preview/run used before).
export function scanTags(text) { return scanTokens(text).filter((t) => t.kind === "tag"); }
// *wildcards only.
export function scanWilds(text) { return scanTokens(text).filter((t) => t.kind === "wild"); }
// #lists only.
export function scanLists(text) { return scanTokens(text).filter((t) => t.kind === "list"); }

// Expand @tags AND resolve *wildcards / #lists. `resolveWild(name)` and
// `resolveList(name)` return the replacement string, or null/undefined to leave that
// token literal (unknown name, empty category, no usable lines); omit them to leave
// every random token literal (pure @tag expansion). The caller owns the randomness.
// Returns { out, knownTags, unknownTags, knownWilds, unknownWilds, knownLists, unknownLists }.
export function expandAll(text, opts = {}) {
  const { tags, resolveWild, resolveList } = opts;
  if (typeof text !== "string" || !/[@*#]/.test(text)) {
    return {
      out: typeof text === "string" ? text : "",
      // `spans` must be present on EVERY return, not just the one that fills it, or a
      // caller reading r.spans.length on a prompt with no tokens gets undefined.
      spans: [],
      knownTags: [], unknownTags: [], knownWilds: [], unknownWilds: [], knownLists: [], unknownLists: [],
    };
  }
  const list = tags || getTags();
  const map = new Map();
  for (const t of list) map.set(t.name.toLowerCase(), t.text);
  const toks = scanTokens(text);
  const knownTags = [], unknownTags = [], knownWilds = [], unknownWilds = [], knownLists = [], unknownLists = [];
  // Where each token's replacement ENDED UP in `out`, so a reader can colour the
  // expanded text one run per tag and see where one stops and the next starts. Purely
  // additive - `out` is byte-identical with or without this - and the caller is free
  // to ignore it. `known` is false for a token left literal (unknown name), which is
  // not tag text and so is not coloured.
  const spans = [];
  let out = "";
  let i = 0;
  for (const h of toks) {
    out += text.slice(i, h.start);
    const at = out.length;
    let known = false;
    if (h.kind === "tag") {
      const v = map.get(h.name.toLowerCase());
      if (v != null) { out += v; knownTags.push(h.name); known = true; }
      else { out += h.raw; unknownTags.push(h.name); } // unknown tag left literal
    } else if (h.kind === "wild") {
      const rep = typeof resolveWild === "function" ? resolveWild(h.name) : null;
      if (rep != null) { out += rep; knownWilds.push(h.name); known = true; }
      else { out += h.raw; unknownWilds.push(h.name); } // unknown / empty category left literal
    } else {
      const rep = typeof resolveList === "function" ? resolveList(h.name) : null;
      if (rep != null) { out += rep; knownLists.push(h.name); known = true; }
      else { out += h.raw; unknownLists.push(h.name); } // unknown tag / no usable lines left literal
    }
    spans.push({ start: at, end: out.length, kind: h.kind, name: h.name, known });
    i = h.end;
  }
  out += text.slice(i);
  return { out, spans, knownTags, unknownTags, knownWilds, unknownWilds, knownLists, unknownLists };
}

// Expand @tags only (deterministic). Kept as the single @-only path; delegates to
// expandAll with no wildcard resolver. Returns { out, unknown, known }.
export function expandTags(text, tags) {
  const r = expandAll(text, { tags, resolveWild: null, resolveList: null });
  return { out: r.out, unknown: r.unknownTags, known: r.knownTags };
}

// Does this text reference at least one @tag (known or not)?
export function hasTags(text) {
  if (typeof text !== "string" || text.indexOf("@") === -1) return false;
  return scanTags(text).length > 0;
}
// Does this text reference at least one *wildcard?
export function hasWilds(text) {
  if (typeof text !== "string" || text.indexOf("*") === -1) return false;
  return scanWilds(text).length > 0;
}
// Does this text reference at least one #list?
export function hasLists(text) {
  if (typeof text !== "string" || text.indexOf("#") === -1) return false;
  return scanLists(text).length > 0;
}
