import { comfy } from '/comfy/api/v2.js';

// The "Hide info Widget" / "Hide for all of this node-type" pair moves to the
// NODE's context menu (below). It used to be a hand-built <ul> dropdown, with
// its own keyboard handling and outside-click dismissal, positioned from
// `widget.inputEl.getBoundingClientRect()` and appended to document.body — 130
// lines of menu, raised from a contextmenu AND a plain click listener on the
// textarea. Both entries act on the widget's owning NODE, and
// `defineWidgetType`'s render callback is handed a container, a value accessor
// and the input name but deliberately no node handle: widgets are built before
// the node has joined a graph, so a handle resolved there would already be dead.
// `b.addMenuItem` has the node and needs no dropdown of the pack's own.
//
// LIMITATION: the gesture changes. It is now right-click on the NODE rather
// than right-click (or plain click) on the info box itself.

var styleElement = document.createElement("style");
const cssCode = `
.easy-info_widget {
	background-color: var(--comfy-input-bg);
	color: var(--input-text);
	overflow: hidden;
	padding: 2px;
	resize: none;
	border: none;
	box-sizing: border-box;
	font-size: 10px;
	border-radius: 7px;
	text-align: center;
	text-wrap: balance;
}
`
styleElement.innerHTML = cssCode
document.head.appendChild(styleElement);


// WIDGETS
comfy.defs.defineWidgetType("INFO", {
	height: 50,
	// COSMETIC: the info box no longer shows the `placeholder` text its Python
	// side may declare, which was visible only while the box was empty — i.e.
	// before the node had run. `render` is handed the input's NAME but not its
	// declaration dict, and the name alone does not say which node type is being
	// rendered, so the dict cannot be looked back up. `default` still arrives, as
	// the initial value.
	render(container, value) {
		const inputEl = document.createElement("textarea");
		inputEl.className = "easy-info_widget";
		inputEl.value = value.get();
		inputEl.readOnly = true;
		container.append(inputEl);

		const stop = value.onChange((v) => { inputEl.value = v; });
		return () => { stop(); inputEl.remove(); };
	}
});

// The guard the old hook opened with was "does this node have an info widget",
// which is a shape rather than a name — the one case a predicate selector is for.
comfy.defs.extend((def) => def.inputs.some((i) => i.type === "INFO"), (b) => {
	const hiddenNodeTypes = JSON.parse(localStorage.getItem('hiddenWidgetNodeTypes') || "[]");

	function hideInfoWidgets(node) {
		for (const w of node.widgets) {
			if (w.widgetType === "INFO") w.setHidden(true);
		}
	}

	b.onCreated((node) => {
		if (node.getProperty('infoWidgetHidden') === undefined) {
			node.setProperty('infoWidgetHidden', false);
		}
		if (hiddenNodeTypes.includes(node.type)) {
			node.setProperty('infoWidgetHidden', true);
		}
	});

	b.onConfigured((node) => {
		if (node.getProperty('infoWidgetHidden')) {
			hideInfoWidgets(node);
		}
	});

	b.addMenuItem({
		label: 'Hide info Widget',
		when: (node) => !node.getProperty('infoWidgetHidden'),
		run: (node) => {
			node.setProperty('infoWidgetHidden', true);
			hideInfoWidgets(node);
		}
	});

	b.addMenuItem({
		label: 'Hide for all of this node-type',
		when: (node) => !hiddenNodeTypes.includes(node.type),
		run: (node) => {
			node.setProperty('infoWidgetHidden', true);
			hideInfoWidgets(node);
			if (!hiddenNodeTypes.includes(node.type)) {
				hiddenNodeTypes.push(node.type);
			}
			localStorage.setItem('hiddenWidgetNodeTypes', JSON.stringify(hiddenNodeTypes));
		}
	});
});
