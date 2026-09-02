import { comfy } from '/comfy/api/v2.js';

// Local stand-in for the DOM builder the old scripts/ui.js exported, which
// modelInfo.js and common/modelInfoDialog.js both build their markup with. Pure
// DOM, no coupling to the app.
export function $el(tag, propsOrChildren, children) {
	const [name, ...classes] = tag.split(".");
	const element = document.createElement(name);
	if (classes.length) element.classList.add(...classes);
	if (Array.isArray(propsOrChildren)) {
		element.append(...propsOrChildren);
		return element;
	}
	const { parent, $: cb, dataset, style, ...rest } = propsOrChildren ?? {};
	if (style) Object.assign(element.style, style);
	if (dataset) Object.assign(element.dataset, dataset);
	Object.assign(element, rest);
	if (children) element.append(...(Array.isArray(children) ? children : [children]));
	if (parent) parent.append(element);
	if (cb) cb(element);
	return element;
}

export function addStylesheet(url) {
	if (url.endsWith(".js")) {
		url = url.substr(0, url.length - 2) + "css";
	}
	const link = document.createElement("link");
	link.rel = "stylesheet";
	link.type = "text/css";
	link.href = url.startsWith("http") ? url : getUrl(url);
	document.head.append(link);
}

export function getUrl(path, baseUrl) {
	if (baseUrl) {
		return new URL(path, baseUrl).toString();
	} else {
		return new URL("../" + path, import.meta.url).toString();
	}
}

export async function loadImage(url) {
	return new Promise((res, rej) => {
		const img = new Image();
		img.onload = res;
		img.onerror = rej;
		img.src = url;
	});
}

// addMenuHandler() is gone: b.addMenuItem() adds an entry to a node type's menu
// directly, so nothing patches getExtraMenuOptions any more and each caller
// registers its own entry.

export function findWidgetByName(node, widgetName) {
    return node.widgets.get(widgetName);
}

// Utility functions
export function addNode(name, nextTo, options) {
    options = { select: true, shiftX: 0, shiftY: 0, before: false, ...(options || {}) };
    const pos = nextTo.getPosition();
    const node = comfy.graph.add(name, {
        position: { x: pos.x + options.shiftX, y: pos.y + options.shiftY }
    });
    if (options.select) {
        comfy.graph.select([node]);
    }
    return node;
}
