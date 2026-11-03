// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Help browser - search                               ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Searches the WHOLE help text, not just node names. Every help def already
// contains the sentences people would actually type - bodies, bullets, term
// lists, table cells - so indexing all of it means "seam" finds Inpaint Stitch
// and "the buttons are missing" finds the cache guide.
//
// Three things make it forgiving, which is the difference between finding
// something and giving up:
//   - an optional `keywords` string per help def, for words the docs would
//     never use ("upscale", "enlarge", "make it bigger" -> Image Resize);
//   - ranking, so an exact name beats a passing mention in a paragraph;
//   - a subsequence pass, so "watermak" still finds Watermark.

const norm = (s) => String(s == null ? "" : s).toLowerCase();

// Flatten one help def into a single searchable blob.
function textOf(help) {
  const bits = [help.title, help.tagline, help.keywords, help.footer];
  for (const s of (Array.isArray(help.sections) ? help.sections : []).filter((x) => x && typeof x === "object")) {
    bits.push(s.heading, s.body);
    if (Array.isArray(s.bullets)) bits.push(...s.bullets);
    if (Array.isArray(s.defs)) for (const d of s.defs) bits.push(...(Array.isArray(d) ? d : [d]));
    // Only the LABEL, never the address: indexing urls would make a search for
    // "com" or "http" match half the pages.
    if (Array.isArray(s.links)) for (const l of s.links) bits.push(Array.isArray(l) ? l[0] : l);
    if (s.table) {
      if (Array.isArray(s.table.headers)) bits.push(...s.table.headers);
      if (Array.isArray(s.table.rows)) for (const r of s.table.rows) bits.push(...(Array.isArray(r) ? r : [r]));
    }
  }
  return norm(bits.filter(Boolean).join(" "));
}

// Built once per index (which is rebuilt on every open), then reused for each
// keystroke. Cheap enough that nothing needs debouncing.
export function buildSearchIndex(index) {
  return index.map((e) => {
    // `aliases` are the search-only words from keywords.mjs, merged by the
    // index builder with anything the help def carries itself.
    const kw = norm([e.aliases, e.help?.keywords].filter(Boolean).join(" "));
    return {
      entry: e,
      name: norm(e.title),
      tag: norm(e.tagline),
      kw,
      all: textOf(e.help || {}) + " " + norm(e.title) + " " + kw,
    };
  });
}

// Is every letter of `needle` present in `hay`, in order? Cheap typo tolerance:
// "watermak" is a subsequence of "text watermark pixaroma".
function subsequence(hay, needle) {
  let i = 0;
  for (let k = 0; k < hay.length && i < needle.length; k++) {
    if (hay[k] === needle[i]) i++;
  }
  return i === needle.length;
}

function scoreOne(rec, q) {
  if (rec.name.startsWith(q)) return 100;
  if (rec.name.includes(q)) return 85;
  if (rec.kw.split(/\s+/).some((w) => w && w.startsWith(q))) return 70;
  if (rec.kw.includes(q)) return 62;
  if (rec.tag.includes(q)) return 48;
  if (rec.all.includes(q)) return 30;
  // Typo tolerance last, and only for a query long enough that a loose match
  // is not just noise.
  if (q.length >= 4 && (subsequence(rec.name, q) || subsequence(rec.kw, q))) return 12;
  return 0;
}

export function searchIndex(records, query, limit) {
  const q = norm(query).trim();
  if (!q) return [];
  const hits = [];
  for (const rec of records) {
    const s = scoreOne(rec, q);
    if (s > 0) hits.push({ entry: rec.entry, score: s });
  }
  hits.sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title));
  return limit ? hits.slice(0, limit) : hits;
}

// Escape, then wrap the matched run in <mark>. Returns HTML.
export function highlight(text, query) {
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const q = norm(query).trim();
  if (!q) return esc(text);
  const i = norm(text).indexOf(q);
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length)) + "</mark>" + esc(text.slice(i + q.length));
}
