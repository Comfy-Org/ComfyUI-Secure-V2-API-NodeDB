// REFUSED, not a gap: restart-from-here. The rest of image_chooser/ converted;
// this file did not, and it is the only thing the directory lost.
//
// What it did: `restart_from_here(id)` took `app.graphToPrompt()`, walked the
// serialized workflow to find every node downstream of the chooser plus
// everything feeding those, severed the chooser's own upstream links, filtered
// `p.output` down to the survivors, then replaced `app.graphToPrompt` with a
// one-shot function returning that hand-built prompt and called
// `app.queuePrompt(0)` so the host submitted it. `all_v_nodes` is the same walk,
// exported and unused.
//
// Why it is refused rather than pending: reading and editing the built prompt is
// the surface that made the old API impossible to retire, and it is deliberately
// unpublished — `comfy.queue` says so in as many words. `comfy.queue.run({nodes})`
// is native partial execution and does not substitute: it recomputes the
// upstream cone of the nodes it is given, which re-runs the sampler whose output
// the user is standing there choosing between. Skipping nodes a *previous* run
// already produced is a backend caching question, not a frontend one.
//
// Behaviour lost: pressing Progress after a run has already finished no longer
// re-queues the graph from the chooser onwards. Progressing a run that is still
// paused at the chooser — the feature's main path — is unaffected.

export {}
