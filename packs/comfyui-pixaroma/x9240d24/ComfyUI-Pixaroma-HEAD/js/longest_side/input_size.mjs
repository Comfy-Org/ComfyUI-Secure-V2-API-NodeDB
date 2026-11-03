// Longest Side Pixaroma - what size picture is arriving.
//
// The node used to need a run before it could show the exact output size, which
// is the wrong way round: ComfyUI's frontend ALREADY knows the incoming size.
// A Load Image node prints "720 x 1280" on its own face, and that comes from
// `node.imgs[0]`, a plain <img> whose naturalWidth/naturalHeight are readable
// the moment the picture loads. So we read it straight off the upstream node.
//
// Kept in its own module because it needs ComfyUI's `app`, and core.mjs must
// stay import-free - that is what lets the parity harness load core.mjs with
// plain node and diff it against Python.
//
// The UPSTREAM READ itself now lives in js/shared/upstream_image_size.mjs,
// because Image Resize needs the identical thing and the "do not trust these
// loaders" list must exist exactly once - a second copy would drift the moment
// a new loader is added. What stays here is this node's own policy: check the
// wire first, then fall back to the size the last run measured.

import { upstreamImageDims } from "../shared/upstream_image_size.mjs";

/**
 * The image size the node will actually receive, or null when it cannot be
 * known. `source` says where the answer came from, which the caller uses to
 * decide how confidently to show it.
 *
 *   "upstream" - read live off the node feeding us. No run needed, and it
 *                follows a swapped file straight away.
 *   "run"      - what the last execution reported. Exact for that run, and the
 *                fallback when the upstream draws no preview of its own.
 */
export function resolveInputSize(node) {
  // Nothing wired in means nothing is arriving, so there is no size to report.
  // Checking this FIRST matters: the run cache outlives the wire that filled
  // it, and without this an unplugged node kept showing a confident, precise,
  // undimmed size from whatever it was last connected to (measured: a node cut
  // loose still read "1024x256").
  if (!isInputConnected(node)) return null;

  const live = upstreamImageDims(node);
  if (live) return { ...live, source: "upstream" };
  const last = node?._pixLsLastIn;
  if (last?.w > 0 && last?.h > 0) return { w: last.w, h: last.h, source: "run" };
  return null;
}

/** Is the image input wired at all? */
export function isInputConnected(node) {
  const inp = (node?.inputs || [])[0];
  return !!inp && inp.link != null;
}

/** A cheap value that changes whenever the answer would change, for polling. */
export function inputSizeKey(node) {
  const d = resolveInputSize(node);
  return `${isInputConnected(node) ? 1 : 0}:${d ? `${d.w}x${d.h}:${d.source}` : "none"}`;
}
