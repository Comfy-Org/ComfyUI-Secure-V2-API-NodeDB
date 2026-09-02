import { comfy } from '/comfy/api/v2.js';

const colorShade = (col, amt) => {
	col = col.replace(/^#/, "");
	if (col.length === 3) col = col[0] + col[0] + col[1] + col[1] + col[2] + col[2];

	let [r, g, b] = col.match(/.{2}/g);
	[r, g, b] = [parseInt(r, 16) + amt, parseInt(g, 16) + amt, parseInt(b, 16) + amt];

	r = Math.max(Math.min(255, r), 0).toString(16);
	g = Math.max(Math.min(255, g), 0).toString(16);
	b = Math.max(Math.min(255, b), 0).toString(16);

	const rr = (r.length < 2 ? "0" : "") + r;
	const gg = (g.length < 2 ? "0" : "") + g;
	const bb = (b.length < 2 ? "0" : "") + b;

	return `#${rr}${gg}${bb}`;
};

let picker;

// Previously spliced this entry into the built-in colour submenu, by wrapping
// LGraphCanvas.onMenuNodeColors and then, a frame later, walking
// document.querySelectorAll(".litecontextmenu") for the menu whose first row read
// "No color" and appending a <div class="litemenu-entry submenu"> to it.
//
// REFUSED, not a pending gap: editing the host's rendered menu in the DOM.
// onMenuNodeColors is the renderer's, and the renderer is ours to replace; the
// class names and the "No color" text the search matched on are markup we rename
// freely, and a pack reading them back breaks on a rename it cannot see. Menu
// entries are contributed, not injected — which is also why two packs doing this
// no longer race over the same rendered element.
//
// LIMITATION: the entry is a top-level node menu item rather than the last row of
// core's colour submenu. Pack entries accumulate among each other; where they sit
// relative to core's own items is the host's to decide.
//
// DROPPED: colouring a GROUP. onMenuNodeColors served the group menu as well as
// the node one, which is why the original branched on LGraphGroup.
// GroupHandle.setColor() exists, but addMenuItem attaches to a node type and
// comfy.graph.selection() returns nodes, so nothing here can name the group the
// user right-clicked.
comfy.defs.extend(/./, (b) => {
	b.addMenuItem({
		label: "🎨 Custom",
		run(node) {
			if (!picker) {
				picker = document.createElement("input");
				picker.type = "color";
				picker.style.display = "none";
				document.body.appendChild(picker);
			}
			picker.onchange = () => {
				if (!picker.value) return;
				const fApplyColor = function (node) {
					node.setColor(colorShade(picker.value, 20));
					node.setBgColor(picker.value);
				};
				const selectedNodes = comfy.graph.selection();
				if (selectedNodes.length <= 1) {
					fApplyColor(node);
				} else {
					for (const selectedNode of selectedNodes) {
						fApplyColor(selectedNode);
					}
				}
			};
			picker.value = node.getBgColor() ?? "#000000";
			picker.click();
		},
	});
});
