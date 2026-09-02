import { comfy } from "/comfy/api/v2.js";

// 全局Seed
function globalSeedHandler(detail) {
	let nodes = comfy.graph.nodes();
	for(let i in nodes) {
	    let node = nodes[i];
	    if(node.type == 'easy globalSeed') {
		    const w = node.widgets.get('value');
		    const last_w = node.widgets.get('last_seed');
		    if(w && last_w) {
			    last_w.setValue(w.getValue());
			    w.setValue(detail.value);
	        }
	    }
        else{
                const w = node.widgets.get('seed_num') || node.widgets.get('seed') || node.widgets.get('noise_seed');
				if(w && detail.seed_map[node.id] != undefined) {
                   w.setValue(detail.seed_map[node.id]);
                }
		}
	}
}

comfy.backend.on("easyuse-global-seed", globalSeedHandler);

// REFUSED, not a pending gap: editing the built prompt. The file replaced
// `api.queuePrompt` with a wrapper that, on every queue, walked the live graph
// and wrote `workflow.seed_widgets = {nodeId: widgetIndex}` into the workflow
// object travelling with the prompt, so the Python side of `easy globalSeed`
// could read the map back out of what was submitted. Reading or editing the
// built prompt is unpublished by design and will not be published: a pack that
// can rewrite what is sent makes the queued graph disagree with the one the
// user is looking at, and core and every other pack would then be reasoning
// about a document that was never on screen. `comfy.queue.onBeforeRun` fires
// exactly where the wrapper ran and is the sanctioned place for a last write —
// but it writes to the GRAPH, which is the distinction being drawn, not to the
// payload.
//
// The capability does not survive elsewhere: nothing in core distributes a seed
// across nodes, so unlike a refusal core re-ships this one is a real loss. What
// would close it is not a published prompt editor but the pack moving the map
// into per-node state — `b.onSerialize((node) => ({ … }))` contributes a
// pack-owned key to each serialized node, which reaches the backend inside the
// embedded workflow and needs no access to the payload. That is a coordinated
// change to the pack's Python, so it is named here rather than guessed at.
//
// WIRE FORMAT: the queued prompt's workflow no longer carries the top-level
// `seed_widgets` key. A removal, not a re-shape. Safe in both directions: the
// key was only ever written on the way out to the backend and never persisted,
// so a workflow saved before this change and one saved after are byte-identical,
// and a prompt built without it is a prompt with one fewer key that no other
// reader consults.
//
// DROPPED: seeds are no longer distributed from `easy globalSeed` to the
// `seed` / `seed_num` / `noise_seed` widgets of other nodes. The backend still
// emits `easyuse-global-seed` and the handler above still applies whatever
// `seed_map` it carries, but with no `seed_widgets` in the submitted workflow
// the Python side has nothing to build that map from, so it arrives empty. The
// node's own `value` / `last_seed` readout still updates.
//
// INOPERABLE: easy globalSeed.
