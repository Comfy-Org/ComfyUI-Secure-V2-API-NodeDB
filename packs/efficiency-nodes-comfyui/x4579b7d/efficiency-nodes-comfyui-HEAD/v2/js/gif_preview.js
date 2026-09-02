import { comfy } from '/comfy/api/v2.js';

// The old file carried offsetDOMWidget(), hasWidgets() and cleanupNode(): a
// hand-rolled draw callback that positioned a document-level <img>/<video> over
// the node by re-deriving the canvas transform, plus the teardown that leak
// needed. A mounted widget is positioned and torn down by the host, so all of
// that is gone rather than ported.

const prefix = 'ad_gif_preview_'

comfy.defs.extend('KSampler (Efficient)', (b) => {

    b.onExecuted((node, result) => {
        for (const name of node.widgets.names()) {
            if (name.startsWith(`${prefix}_`)) {
                node.widgets.remove(name)
            }
        }

        const gifs = result.raw?.gifs
        if (gifs) {
            gifs.forEach((params, i) => {
                const previewUrl = comfy.backend.url(
                    '/view?' + new URLSearchParams(params).toString()
                )
                const [type] = (params.format || 'image/gif').split('/')

                node.widgets.mount({
                    name: `${prefix}_${i}`,
                    defaultValue: previewUrl,
                    render(container) {
                        const inputEl = document.createElement(type === 'video' ? 'video' : 'img')
                        inputEl.src = previewUrl
                        inputEl.style.width = '100%'
                        if (type === 'video') {
                            inputEl.setAttribute('type', 'video/webm');
                            inputEl.autoplay = true
                            inputEl.loop = true
                            inputEl.controls = false;
                        }
                        container.append(inputEl)
                    }
                })
            })
        }

        if (gifs && gifs.length > 0) {
            node.setSizeConstraints({ autoHeight: true });
        }
    })
})
