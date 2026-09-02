import { comfy } from '/comfy/api/v2.js';
import { lightbox } from "./common/lightbox.js";

// Local stand-in for the element helper the old scripts/ui.js exported.
function $el(tag, propsOrChildren, children) {
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

$el("style", {
	textContent: `
	.pysssss-image-feed {
		position: absolute;
		background: var(--comfy-menu-bg);
		color: var(--fg-color);
		z-index: 99;
		font-family: sans-serif;
		font-size: 12px;
		display: flex;
		flex-direction: column;
	}
	div > .pysssss-image-feed {
		position: static;
	}
	.pysssss-image-feed--top, .pysssss-image-feed--bottom {
		width: 100vw;
		min-height: 30px;
		max-height: calc(var(--max-size, 20) * 1vh);
	}
	.pysssss-image-feed--top {
		top: 0;
	}
	.pysssss-image-feed--bottom {
		bottom: 0;
		flex-direction: column-reverse;
		padding-top: 5px;
	}
	.pysssss-image-feed--left, .pysssss-image-feed--right {
		top: 0;
		height: 100vh;
		min-width: 200px;
		max-width: calc(var(--max-size, 10) * 1vw);
	}
	.comfyui-body-left .pysssss-image-feed--left, .comfyui-body-right .pysssss-image-feed--right {
		height: 100%;
	}
	.pysssss-image-feed--left {
		left: 0;
	}
	.pysssss-image-feed--right {
		right: 0;
	}

	.pysssss-image-feed--left .pysssss-image-feed-menu, .pysssss-image-feed--right .pysssss-image-feed-menu {
		flex-direction: column;
	}

	.pysssss-image-feed-menu {
		position: relative;
		flex: 0 1 min-content;
		display: flex;
		gap: 5px;
		padding: 5px;
		justify-content: space-between;
	}
	.pysssss-image-feed-btn-group {
		align-items: stretch;
		display: flex;
		gap: .5rem;
		flex: 0 1 fit-content;
		justify-content: flex-end;
	}
	.pysssss-image-feed-btn {
		background-color:var(--comfy-input-bg);
		border-radius:5px;
		border:2px solid var(--border-color);
		color: var(--fg-color);
		cursor:pointer;
		display:inline-block;
		flex: 0 1 fit-content;
		text-decoration:none;
	}
	.pysssss-image-feed-btn.sizing-btn:checked {
		filter: invert();
	}
	.pysssss-image-feed-btn.clear-btn {
		padding: 5px 20px;
	}
	.pysssss-image-feed-btn.hide-btn {
		padding: 5px;
		aspect-ratio: 1 / 1;
	}
	.pysssss-image-feed-btn:hover {
		filter: brightness(1.2);
	}
	.pysssss-image-feed-btn:active {
		position:relative;
		top:1px;
	}
	
	.pysssss-image-feed-menu section {
		border-radius: 5px;
		background: rgba(0,0,0,0.6);
		padding: 0 5px;
		display: flex;
		gap: 5px;
		align-items: center;
		position: relative;
	}
	.pysssss-image-feed-menu section span {
		white-space: nowrap;
	}
	.pysssss-image-feed-menu section input {
		flex: 1 1 100%;
		background: rgba(0,0,0,0.6);
		border-radius: 5px;
		overflow: hidden;
		z-index: 100;
	}

	.sizing-menu {
		position: relative;
	}

	.size-controls-flyout {
		position: absolute;
		transform: scaleX(0%);
		transition: 200ms ease-out;
		transition-delay: 500ms;
		z-index: 101;
		width: 300px;
	}

	.sizing-menu:hover .size-controls-flyout {
		transform: scale(1, 1);
		transition: 200ms linear;
		transition-delay: 0;
	}
	.pysssss-image-feed--bottom .size-controls-flyout  {
		transform: scale(1,0);
		transform-origin: bottom;
		bottom: 0;
		left: 0;
	}
	.pysssss-image-feed--top .size-controls-flyout  {
		transform: scale(1,0);
		transform-origin: top;
		top: 0;
		left: 0;
	}
	.pysssss-image-feed--left .size-controls-flyout  {
		transform: scale(0, 1);
		transform-origin: left;
		top: 0;
		left: 0;
	}
	.pysssss-image-feed--right .size-controls-flyout  {
		transform: scale(0, 1);
		transform-origin: right;
		top: 0;
		right: 0;
	}
	
	.pysssss-image-feed-menu > * {
		min-height: 24px;
	}
	.pysssss-image-feed-list {
		flex: 1 1 auto;
		overflow-y: auto;
		display: grid;
		align-items: center;
		justify-content: center;
		gap: 4px;
		grid-auto-rows: min-content;
		grid-template-columns: repeat(var(--img-sz, 3), 1fr);
		transition: 100ms linear;
		scrollbar-gutter: stable both-edges;
		padding: 5px;
		background: var(--comfy-input-bg);
		border-radius: 5px;
		margin: 5px;
		margin-top: 0px;
	}
	.pysssss-image-feed-list:empty {
		display: none;
	}
	.pysssss-image-feed-list div {
		height: 100%;
		text-align: center;
	}
	.pysssss-image-feed-list::-webkit-scrollbar {
		background: var(--comfy-input-bg);
		border-radius: 5px;
	}
	.pysssss-image-feed-list::-webkit-scrollbar-thumb {
		background:var(--comfy-menu-bg);
		border: 5px solid transparent;
		border-radius: 8px;
		background-clip: content-box;
	}
	.pysssss-image-feed-list::-webkit-scrollbar-thumb:hover {
		background: var(--border-color);
		background-clip: content-box;
	}
	.pysssss-image-feed-list img {
		object-fit: var(--img-fit, contain);
		max-width: 100%;
		max-height: calc(var(--max-size) * 1vh);
		border-radius: 4px;
	}
	.pysssss-image-feed-list img:hover {
		filter: brightness(1.2);
	}`,
	parent: document.body,
});

let visible = true;
const seenImages = new Map();
// The ComfyButton in app.menu.settingsGroup is an action bar contribution — see
// syncShowButton below. Its other half, a 🖼️ button grafted next to core's settings
// button by querySelector, is REFUSED rather than pending: contributions are
// declarative and a pack does not place elements in the host's chrome. The same
// action is a command too, so it has a keyboard home.

const getVal = (n, d) => {
	const v = localStorage.getItem("pysssss.ImageFeed." + n);
	if (v && !isNaN(+v)) {
		return v;
	}
	return d;
};

const saveVal = (n, v) => {
	localStorage.setItem("pysssss.ImageFeed." + n, v);
};

const imageFeed = $el("div.pysssss-image-feed");
const imageList = $el("div.pysssss-image-feed-list");

// REFUSED, not a pending gap: docking the feed inside the host's chrome. The old
// code re-parented itself into the menu element it found by querySelector; the feed
// always sits on document.body and places itself from its own class now — which is
// exactly what the old code did when that element was absent.
function updateMenuParent() {
	if (!imageFeed.parentElement) {
		document.body.append(imageFeed);
	}
}

function showFeed() {
	if (comfy.settings.get(FEED_LOCATION) === "hidden") return;
	updateMenuParent();
	imageFeed.style.display = "flex";

	saveVal("Visible", 1);
	visible = true;
	syncShowButton();
	window.dispatchEvent(new Event("resize"));
}

// The action bar entry that brings the feed back. Declarative, so there is no
// element to hide: it is added while the feed is away and removed once it is back,
// which is what the old `showMenuButton.element.style.display` toggling meant.
let showButton = null;
function syncShowButton() {
	const wanted = !visible && comfy.settings.get(FEED_LOCATION) !== "hidden";
	if (wanted && !showButton) {
		showButton = comfy.ui.addActionBarButton({
			id: "pysssss.imageFeed",
			icon: "pi-images",
			label: "Show Image Feed 🐍",
			tooltip: "Show Image Feed 🐍",
			run: showFeed,
		});
	} else if (!wanted && showButton) {
		showButton.remove();
		showButton = null;
	}
}

// Previously supplied `type: () => $el("tr", …)` for Location and Direction,
// building the settings panel's own table row and <select> so that picking a value
// applied it on the spot.
//
// REFUSED, not a pending gap: a pack rendering the settings panel's markup. Core's
// setting type does accept a function returning an element, and publishing it would
// put every pack in charge of a panel we then could not restyle. The capability is
// intact: a declared `combo` offers the same values and `onChange` applies them the
// moment one is picked, which is all the hand-built row did.
const FEED_LOCATION = "pysssss.ImageFeed.Location";
comfy.settings.declare({
	id: FEED_LOCATION,
	name: "🐍 Image Feed Location",
	defaultValue: "bottom",
	type: "combo",
	options: ["left", "top", "right", "bottom", "hidden"],
	onChange(value) {
		if (value === "hidden") {
			imageFeed.remove();
		} else {
			imageFeed.className = `pysssss-image-feed pysssss-image-feed--${value}`;
			imageFeed.style.display = visible ? "flex" : "none";
			updateMenuParent();
		}
		syncShowButton();
		window.dispatchEvent(new Event("resize"));
	},
});

const FEED_DIRECTION = "pysssss.ImageFeed.Direction";
comfy.settings.declare({
	id: FEED_DIRECTION,
	name: "🐍 Image Feed Direction",
	defaultValue: "newest first",
	type: "combo",
	options: ["newest first", "oldest first"],
	onChange(value, previous) {
		if (previous !== undefined && previous !== value) {
			imageList.replaceChildren(...[...imageList.childNodes].reverse());
		}
	},
});

const dedupeOptions = { disabled: 0, "enabled (slow)": 1, "enabled (performance)": 0.5, "enabled (max performance)": 0.25 };
const FEED_DEDUPLICATION = "pysssss.ImageFeed.Deduplication";
comfy.settings.declare({
	id: FEED_DEDUPLICATION,
	name: "🐍 Image Feed Deduplication",
	tooltip: `Ensures unique images in the image feed but at the cost of CPU-bound performance impact \
(from hundreds of milliseconds to seconds per image, depending on byte size). For workflows that produce duplicate images, turning this setting on may yield overall client-side performance improvements \
by reducing the number of images in the feed.

Recommended: "enabled (max performance)" uness images are erroneously deduplicated.`,
	defaultValue: 0,
	type: "combo",
	options: Object.entries(dedupeOptions).map(([label, value]) => ({ value, label })),
});

const FEED_MAX_IMAGES = "pysssss.ImageFeed.MaxImages";
comfy.settings.declare({
	id: FEED_MAX_IMAGES,
	name: "🐍 Image Feed Max Images",
	tooltip: `Limits the number of images in the feed to a maximum, removing the oldest images as new ones are added.`,
	defaultValue: 0,
	type: "number",
});

const FEED_SAVE_NODE_ONLY = "pysssss.ImageFeed.SaveNodeOnly";
comfy.settings.declare({
	id: FEED_SAVE_NODE_ONLY,
	name: "🐍 Image Feed Display 'SaveImage' Only",
	tooltip: `Only show images from 'SaveImage' nodes. This prevents 'PreviewImage' node outputs from appearing in the feed.`,
	defaultValue: false,
	type: "boolean",
});

const clearButton = $el("button.pysssss-image-feed-btn.clear-btn", {
	textContent: "Clear",
	onclick: () => {
		imageList.replaceChildren();
		window.dispatchEvent(new Event("resize"));
	},
});

const hideButton = $el("button.pysssss-image-feed-btn.hide-btn", {
	textContent: "❌",
	onclick: () => {
		imageFeed.style.display = "none";
		saveVal("Visible", 0);
		visible = false;
		syncShowButton();
		window.dispatchEvent(new Event("resize"));
	},
});

let columnInput;
function updateColumnCount(v) {
	columnInput.parentElement.title = `Controls the number of columns in the feed (${v} columns).\nClick label to set custom value.`;
	imageFeed.style.setProperty("--img-sz", v);
	saveVal("ImageSize", v);
	columnInput.max = Math.max(10, v, columnInput.max);
	columnInput.value = v;
	window.dispatchEvent(new Event("resize"));
}

function addImageToFeed(href) {
	const method = comfy.settings.get(FEED_DIRECTION) === "newest first" ? "prepend" : "append";

	const maxImages = comfy.settings.get(FEED_MAX_IMAGES);
	if (maxImages > 0 && imageList.children.length >= maxImages) {
		imageList.children[method === "prepend" ? imageList.children.length - 1 : 0].remove();
	}

	imageList[method](
		$el("div", [
			$el(
				"a",
				{
					target: "_blank",
					href,
					onclick: (e) => {
						const imgs = [...imageList.querySelectorAll("img")].map((img) => img.getAttribute("src"));
						lightbox.show(imgs, imgs.indexOf(href));
						e.preventDefault();
					},
				},
				[$el("img", { src: href })]
			),
		])
	);
	// If lightbox is open, update it with new image
	lightbox.updateWithNewImage(href, comfy.settings.get(FEED_DIRECTION));
}

imageFeed.append(
	$el("div.pysssss-image-feed-menu", [
		$el("section.sizing-menu", {}, [
			$el("label.size-control-handle", { textContent: "↹ Resize Feed" }),
			$el("div.size-controls-flyout", {}, [
				$el("section.size-control.feed-size-control", {}, [
					$el("span", {
						textContent: "Feed Size...",
					}),
					$el("input", {
						type: "range",
						min: 10,
						max: 80,
						oninput: (e) => {
							e.target.parentElement.title = `Controls the maximum size of the image feed panel (${e.target.value}vh)`;
							imageFeed.style.setProperty("--max-size", e.target.value);
							saveVal("FeedSize", e.target.value);
							window.dispatchEvent(new Event("resize"));
						},
						$: (el) => {
							requestAnimationFrame(() => {
								el.value = getVal("FeedSize", 25);
								el.oninput({ target: el });
							});
						},
					}),
				]),
				$el("section.size-control.image-size-control", {}, [
					$el("a", {
						textContent: "Column count...",
						style: {
							cursor: "pointer",
							textDecoration: "underline",
						},
						onclick: () => {
							const v = +prompt("Enter custom column count", 20);
							if (!isNaN(v)) {
								updateColumnCount(v);
							}
						},
					}),
					$el("input", {
						type: "range",
						min: 1,
						max: 10,
						step: 1,
						oninput: (e) => {
							updateColumnCount(e.target.value);
						},
						$: (el) => {
							columnInput = el;
							requestAnimationFrame(() => {
								updateColumnCount(getVal("ImageSize", 4));
							});
						},
					}),
				]),
			]),
		]),
		$el("div.pysssss-image-feed-btn-group", {}, [clearButton, hideButton]),
	]),
	imageList
);
comfy.commands.register({
	id: "pysssss.ImageFeed.Show",
	label: "🐍 Show Image Feed",
	run: showFeed,
});
window.dispatchEvent(new Event("resize"));

if (!+getVal("Visible", 1)) {
	hideButton.onclick();
}

comfy.backend.on("executed", (detail) => {
	if (visible && detail?.output?.images) {
		// Apply "Display Save Image Node Only" filter if setting is enabled
		const nodeName = detail.node?.split(":")?.[0];
		if (nodeName) {
			const node = comfy.graph.node(nodeName);

			// Ignore the wrapper of a nested graph, as the old getInnerNodes test did:
			// a node that places a subgraph carries that subgraph's id as its type.
			if (detail.node.includes(":") && node &&
				comfy.graph.subgraphs().some((sg) => sg.id === node.type)) return;

			if (comfy.settings.get(FEED_SAVE_NODE_ONLY) && node?.type !== "SaveImage") return;
		}

		for (const src of detail.output.images) {
			const href = comfy.backend.url(`/view?filename=${encodeURIComponent(src.filename)}&type=${src.type}&
			subfolder=${encodeURIComponent(src.subfolder)}&t=${+new Date()}`);

			// dedupeScale is the scaling factor used for image hashing, and is 0 when
			// deduplication is disabled
			const dedupeScale = comfy.settings.get(FEED_DEDUPLICATION) ?? 0;
			if (dedupeScale > 0) {
				// deduplicate by ignoring images with the same filename/type/subfolder
				const fingerprint = JSON.stringify({ filename: src.filename, type: src.type, subfolder: src.subfolder });
				if (seenImages.has(fingerprint)) {
					// NOOP: image is a duplicate
				} else {
					seenImages.set(fingerprint, true);
					let img = $el("img", { src: href });
					img.onerror = () => {
						// fall back to default behavior
						addImageToFeed(href);
					};
					img.onload = () => {
						// redraw the image onto a canvas to strip metadata (resize if performance mode)
						let imgCanvas = document.createElement("canvas");
						let imgScalar = dedupeScale;
						imgCanvas.width = imgScalar * img.width;
						imgCanvas.height = imgScalar * img.height;

						let imgContext = imgCanvas.getContext("2d");
						imgContext.drawImage(img, 0, 0, imgCanvas.width, imgCanvas.height);
						const data = imgContext.getImageData(0, 0, imgCanvas.width, imgCanvas.height);

						// calculate fast hash of the image data
						let hash = 0;
						for (const b of data.data) {
							hash = (hash << 5) - hash + b;
						}

						// add image to feed if we've never seen the hash before
						if (seenImages.has(hash)) {
							// NOOP: image is a duplicate
						} else {
							// if we got to here, then the image is unique--so add to feed
							seenImages.set(hash, true);
							addImageToFeed(href);
						}
					};
				}
			} else {
				addImageToFeed(href);
			}
		}
	}
});
