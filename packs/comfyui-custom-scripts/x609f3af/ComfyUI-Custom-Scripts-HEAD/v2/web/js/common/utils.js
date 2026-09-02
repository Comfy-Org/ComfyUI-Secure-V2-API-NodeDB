// The pack's own stand-in for the element helper scripts/ui.js exported. Nothing
// published replaces it because nothing needs to: it is plain DOM, and it lives
// here so the three files that used core's copy share one rather than each
// carrying its own.
export function $el(tag, propsOrChildren, children) {
	const [name, ...classes] = tag.split(".");
	const element = document.createElement(name);
	if (classes.length) element.classList.add(...classes);
	if (Array.isArray(propsOrChildren)) {
		element.append(...propsOrChildren);
		return element;
	}
	const { parent, $: cb, dataset, style, ...rest } = propsOrChildren ?? {};
	Object.assign(element, rest);
	if (style) Object.assign(element.style, style);
	if (dataset) Object.assign(element.dataset, dataset);
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
