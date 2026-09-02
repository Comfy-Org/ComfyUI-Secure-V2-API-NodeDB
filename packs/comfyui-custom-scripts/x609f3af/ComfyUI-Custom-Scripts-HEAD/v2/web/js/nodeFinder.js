import { comfy } from '/comfy/api/v2.js';

// Previously added three canvas menu entries: follow the executing node, jump to
// the executing node, and a "Go to node" tree grouped by node type.
//
// The first two are position-independent actions, so they are commands. The
// executing node comes from comfy.executingNode()/onExecutingNodeChanged rather
// than app.runningNodeId and the raw "executing" message.
//
// LIMITATION: "Go to node" moved off the empty-canvas right-click, which is the
// host's menu and not published, onto an action bar button. The menu it raises is
// the same two-level tree — comfy.ui.showMenu nests submenus to any depth — and the
// button's click supplies the event that positions it, which a command cannot. A
// user who reaches for the canvas menu no longer finds it there, and the button
// carries an icon the text entry did not have.

let followExecution = false;

function centerOnExecuting() {
	const node = comfy.executingNode();
	if (node) comfy.graph.centerOn(node);
}

comfy.onExecutingNodeChanged((node) => {
	if (followExecution && node) comfy.graph.centerOn(node);
});

// A function label, which is what the old entry's `followExecution ? … : …`
// content was: the command relabels itself instead of carrying an active flag.
comfy.commands.register({
	id: "pysssss.NodeFinder.FollowExecution",
	label: () => (followExecution ? "Stop following execution" : "Follow execution"),
	run: () => {
		followExecution = !followExecution;
		if (followExecution) centerOnExecuting();
	},
});

comfy.commands.register({
	id: "pysssss.NodeFinder.ShowExecutingNode",
	label: "Show executing node",
	run: centerOnExecuting,
});

comfy.ui.addActionBarButton({
	id: "pysssss.NodeFinder.GoToNode",
	icon: "icon-[lucide--crosshair]",
	tooltip: "Go to node",
	run(event) {
		const nodes = comfy.graph.nodes();
		const types = nodes.reduce((p, n) => {
			if (n.type in p) {
				p[n.type].push(n);
			} else {
				p[n.type] = [n];
			}
			return p;
		}, {});
		comfy.ui.showMenu({
			title: "Go to node",
			event,
			items: Object.keys(types)
				.sort()
				.map((t) => ({
					label: t,
					submenu: types[t]
						.sort((a, b) => {
							return a.getPosition().x - b.getPosition().x;
						})
						.map((n) => ({
							label: `${n.getTitle()} - #${n.id} (${n.getPosition().x}, ${n.getPosition().y})`,
							run: () => {
								comfy.graph.centerOn(n);
							},
						})),
				})),
		});
	},
});
