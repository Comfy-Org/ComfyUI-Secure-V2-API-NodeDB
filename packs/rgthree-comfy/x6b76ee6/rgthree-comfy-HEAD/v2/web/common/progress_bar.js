import { comfy } from '/comfy/api/v2.js';

// PUNTED IN FULL — 179 lines removed, nothing converted.
//
// `<rgthree-progress-bar>` — the thin two-tier bar rgthree puts at the top (or
// bottom) of the window showing overall node progress and the current node's step
// progress, with the running node's title and the queue depth.
//
// The element itself is a plain custom element and needs nothing from the API. It
// is punted because its only data source is common/prompt_service.js, which is
// punted:
//
// API-GAP: (31) no node execution progress. `progress-update` carries
//   `{queue, prompt: {totalNodes, executedNodeIds, currentlyExecuting: {nodeId,
//   nodeLabel, step, maxSteps, pass, maxPasses}}}`, built by reading the prompt
//   out of an intercepted `api.queuePrompt` — a refusal, not a gap; see
//   common/prompt_service.js.
// REFUSED, not a gap: how it is mounted. rgthree.js inserts the element into
//   `.comfyui-body-top` / `.comfyui-body-bottom` by query selector. The chrome
//   surface is declarative — `comfy.ui.addTopBarBadge({id, text, variant, tooltip})`
//   then `badge.update({text})` on each tick — and takes no element, class or style.
//   A pack-drawn two-tier bar spanning the window has no published form and is not
//   waiting on one. `update()` rather than a closure, because the host renders on
//   reactive change and cannot see a plain function.
//
// `currentNodeId` — which the bar exposes so rgthree.js can centre the canvas on the
// running node when clicked — is no longer a gap: it is `comfy.executingNode()`,
// with `comfy.onExecutingNodeChanged(fn)` to drive the redraw, and the centring half
// is `comfy.graph.centerOn(node)`. The queue depth beside it is
// `comfy.queue.pending()` / `onPendingChanged`. Only the per-node *step* progress
// above has nothing behind it.
