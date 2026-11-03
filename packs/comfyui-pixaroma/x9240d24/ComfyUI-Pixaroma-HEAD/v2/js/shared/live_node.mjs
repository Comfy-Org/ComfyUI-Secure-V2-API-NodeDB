// Is a node on a canvas the user actually has open?
//
// ComfyUI builds node objects that are never put on a canvas, and keeps others
// that have left it, and NEITHER kind ever gets onRemoved. So anything that keeps
// a module-level set of its instances (Run Timer's timers, Monitor's sampler) has
// to skip them where the set is USED, or they keep acting on every later run:
//   - A throwaway COPY. Ctrl+C, Alt-drag and right-click Clone all serialize a
//     clone(), and Convert to Subgraph a multiClone(): createNode + configure,
//     never added, so node.graph is null. (Copying a SUBGRAPH node puts its
//     inner nodes in a clone of the subgraph that is never registered, which the
//     registry test below catches.)
//   - The inner nodes of a subgraph once the workflow is REPLACED (a tab switch,
//     opening a file, Ctrl+Z). LGraph.clear() fires onRemoved for ROOT nodes
//     only and empties the subgraph map, so they keep a graph nothing can reach.
// MEASURED 2026-09-26: one Run Timer plus three Ctrl+C copies chimed 4 times, and
// a canvas with no timer on it still chimed and recorded the run; a Monitor copy
// kept the stats polling going (about 4 requests a second after a workflow switch
// with no Monitor left anywhere). CLAUDE.md Vue Compat #8 has the rule.
//
// app.graph is always the ROOT (also while you look inside a subgraph), and
// rootGraph.subgraphs holds every subgraph, nested ones included.
//
// The last test is "is it in its graph's node LIST", deliberately NOT an id
// lookup. A workflow can hold two nodes with the SAME id (hand-edited, or
// written by an old bug): LGraph.add renumbers the second, then configure writes
// its old id back, so getNodeById answers with the OTHER node. The first version
// used the id and judged a real, visible Run Timer "not on a canvas" - review
// finding, reproduced: it never started and never chimed. The list test still
// excludes a node removed from its graph, and the old root nodes after a
// workflow switch (app.graph is the SAME object in every tab, but its list is
// rebuilt).
//
// SKIP on this answer, never drop the node from your set: ComfyUI's asset
// browser creates a node, waits a tick and only then adds it, so "no graph yet"
// is not proof of a copy. Anything unexpected (an older frontend with no
// subgraphs) answers "live", so a real node is never silenced.
import { app } from "../../../scripts/app.js";

export function isLiveNode(node) {
  const g = node && node.graph;
  if (!g) return false;
  try {
    const root = app.graph;
    if (!root) return true;
    if (g !== root) {
      let known = false;
      for (const sg of root.subgraphs.values()) if (sg === g) { known = true; break; }
      if (!known) return false;
    }
    const list = g._nodes;
    return Array.isArray(list) ? list.includes(node) : true;
  } catch (_e) { return true; }
}
