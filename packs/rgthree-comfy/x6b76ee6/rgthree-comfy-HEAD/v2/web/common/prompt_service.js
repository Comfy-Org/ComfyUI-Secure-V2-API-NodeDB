// Tracks the state of every queued prompt — which node is running, how many nodes it
// has, which are cached, step progress within a node, and errors — and emits a
// "progress-update" event. It is the model behind the progress bar.
//
// REFUSED, not a pending gap: reading the built prompt. It wraps `api.queuePrompt` to
// take the prompt's *contents* at submit time — `promptExecution.setPrompt(prompt)`
// stores `prompt.output`, which is where `totalNodes`, every node's `class_type` and
// `_meta.title`, and the UltimateSDUpscale / IterativeImageUpscale pass counting all come
// from. Reading or editing the built prompt is the surface that made the old API
// impossible to retire, and it is deliberately not published; the same information is
// not obtainable after the fact either, for the same reason. This is a decision, not a
// queue.
//
// The consequence, stated plainly rather than left to be discovered: every counter in
// this file is made of the prompt's contents. `comfy.queue.onBeforeRun` / `onAfterRun`
// say that a run started and that one was submitted, and carry no payload, so a
// conversion built on them would report every prompt as zero nodes with no labels. That
// is a half-conversion wearing a port's clothes, and shipping it would leave a progress
// model that is always empty and a pack author wondering why.
//
// What the file needed *besides* the prompt's contents is published, and is recorded here
// so the next reader does not re-derive it. The event half is
// `comfy.backend.on("status" | "execution_start" | "executing" | "progress" |
// "execution_cached" | "executed" | "execution_error", detail => …)`, which is exactly
// what `api.addEventListener` was doing. Resolving the running node is
// `comfy.executingNode()` plus `comfy.onExecutingNodeChanged(fn)`, so neither the raw
// `executing` event nor `window.app.graph.getNodeById(...)` is needed for the label.
// Queue depth is `comfy.queue.pending()` with `comfy.queue.onPendingChanged`, and a
// cancelled run is `comfy.queue.onInterrupted`. A per-node progress readout built from
// those — this node, this step, this queue depth — is a smaller feature than the one
// here, and it is the pack author's call whether it is the one they want.
//
// INOPERABLE: the `progress_bar` feature (common/progress_bar.js, which this is the model
// for). No node type depends on it.

export {}
