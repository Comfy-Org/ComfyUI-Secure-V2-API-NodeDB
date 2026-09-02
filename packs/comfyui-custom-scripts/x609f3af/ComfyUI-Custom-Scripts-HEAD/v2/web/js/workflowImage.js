// Previously exported the whole workflow as a PNG or SVG picture with the workflow
// JSON embedded in it (a tEXt chunk / a <desc> tag), and imported it back again —
// including reading an A1111 prompt out of a JPEG's EXIF UserComment.
//
// REFUSED, not a pending gap: driving the live canvas to take a picture of it.
// Export saved app.canvas.ds.scale and offset and the canvas element's width,
// height and transform, resized the element to the graph's bounding box, forced
// scale 1, called app.canvas.draw(true, true) to render the whole document into the
// element the user is looking at, read the pixels back, and put all of it back.
// That is the renderer borrowed as an offscreen buffer mid-session: anything that
// reads the viewport during the capture — core, another pack, a window resize —
// sees a canvas lying about its size and zoom, and a throw anywhere in the middle
// leaves the user's view wrong with nothing left to restore it.
//
// REFUSED, not a pending gap: substituting the renderer's drawing context. The SVG
// format assigned a canvas2svg mock over app.canvas.ctx so the editor would draw
// into an SVG document, then stubbed getBoundingClientRect, drawImage, getTransform
// and resetTransform on it because the real renderer called things the mock lacked.
// The renderer is ours to replace, and a pack holding its context has to track
// every drawing call we make.
//
// REFUSED, not a pending gap: replacing a core global. ComfyWidgets.STRING was
// reassigned outright, so every multiline text widget in the document — core's and
// every other pack's — was constructed by this file, purely so it could chain
// widget.draw and paint the textarea's contents into the capture. Multiline text is
// DOM and so invisible to a canvas capture; the answer to that is not to own
// everybody's text widget.
//
// REFUSED, not a pending gap: replacing the canvas menu builder and app.handleFile.
// The Import/Export entries were pushed onto
// LGraphCanvas.prototype.getCanvasMenuOptions, and import wrapped app.handleFile so
// this pack saw every file the user dropped before the host did.
//
// The IMPORT capability is not refused and is not lost: core ships it. Dropping a
// PNG, WEBP, FLAC or AVIF carrying a workflow opens it, and an A1111 prompt is read
// as well — src/scripts/pnginfo.ts exports getPngMetadata, getWebpMetadata,
// getFlacMetadata, getAvifMetadata and importA1111, which is the same set this file
// re-implemented before core had them.
//
// DROPPED: EXPORT as a picture. Comfy.ExportWorkflow writes JSON, not an image, so
// the PNG-with-workflow and the SVG are gone. Rendering the document into a buffer
// the caller supplies — offscreen, at a stated size, without touching the live view
// — is the missing capability, and it is the renderer's to offer rather than a
// pack's to take.
//
// assets/canvas2svg.js is third-party (Canvas2Svg v1.0.19, © 2014 Gliffy Inc., MIT)
// and is left exactly as shipped. Nothing loads it now.
//
// INOPERABLE: Workflow Image Export, both PNG and SVG. Import is core's.

export {}
