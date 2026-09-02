import { comfy } from '/comfy/api/v2.js';

const infoNodes = ["easy imageSize","easy imageSizeBySide","easy imageSizeByLongerSide", "easy imageSizeShow", "easy imageRatio", "easy imagePixelPerfect"];

// The mounted textarea, by node id. Handles hold no arbitrary properties, and
// the element is only reachable from the render callback that created it.
const infoInputs = new Map();

comfy.defs.extend(infoNodes, (b) => {

    b.onCreated((node) => {
			const inputEl = document.createElement("textarea");
			inputEl.className = "comfy-multiline-input";
			inputEl.readOnly = true

			node.widgets.mount({
				name: "info",
				render(container) {
					container.append(inputEl);
					infoInputs.set(node.id, inputEl);
				},
				destroy() {
					infoInputs.delete(node.id);
				}
			});
    });

			function populate(arr_text) {
				var text = '';
				for (let i = 0; i < arr_text.length; i++){
					text += arr_text[i];
				}
				const inputEl = infoInputs.get(this.id);
				if (inputEl) {
					inputEl.value = text;
				}
				requestAnimationFrame(() => {
					this.setSizeConstraints({ autoHeight: true });
				});
			}

			b.onExecuted((node, result) => {
				populate.call(node, result.text);
			});
})
