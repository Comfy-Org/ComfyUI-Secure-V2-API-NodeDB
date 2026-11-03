// ╔═══════════════════════════════════════════════════════════════╗
// ║  Pixaroma Workflows - finding one                              ║
// ╚═══════════════════════════════════════════════════════════════╝
//
// Scores rather than filters, so the thing somebody half-remembers the name of
// comes first and the workflow that merely uses that model comes after.
//
// Matching the CONTENTS is the point: "which one used flux krea" and "the one
// with the red coat prompt" are the questions a filename cannot answer.

const FIELDS = [
  // [weight, how to read it off an entry]
  [100, (e) => e.name],
  [30, (e) => e.folder],
  [26, (e) => e._note || ""],
  [18, (e) => (e.models || []).join(" ")],
  [18, (e) => (e.loras || []).join(" ")],
  [8, (e) => (e.class_types || []).join(" ")],
  [6, (e) => e.text || ""],
];

/** Score one entry against already-lowercased terms. 0 means "not a match". */
function score(entry, terms) {
  let total = 0;
  for (const term of terms) {
    let best = 0;
    for (const [weight, read] of FIELDS) {
      const hay = (read(entry) || "").toLowerCase();
      if (!hay) continue;
      const at = hay.indexOf(term);
      if (at < 0) continue;
      // Exact beats "starts with" beats "contains somewhere", so typing a full
      // name does not put a longer name that merely contains it first.
      let s = weight;
      if (hay === term) s = weight * 3;
      else if (at === 0) s = weight * 2;
      else if (/\s|[-_/]/.test(hay[at - 1] || "")) s = Math.round(weight * 1.5);
      if (s > best) best = s;
    }
    // EVERY term has to hit something, or "krea lora" would return everything
    // that is merely a lora.
    if (!best) return 0;
    total += best;
  }
  return total;
}

/**
 * @param entries index entries, each optionally carrying `_note`
 * @param query   what the user typed
 * @returns the matching entries, best first; the input order when query is empty
 */
export function searchEntries(entries, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return entries;
  const terms = q.split(/\s+/).filter(Boolean);
  const hits = [];
  for (const e of entries) {
    const s = score(e, terms);
    if (s > 0) hits.push([s, e]);
  }
  // Ties break on most-recently-changed: between two equally good matches, the
  // one worked on last week is the one being looked for.
  hits.sort((a, b) => b[0] - a[0] || (b[1].modified || 0) - (a[1].modified || 0));
  return hits.map((h) => h[1]);
}
