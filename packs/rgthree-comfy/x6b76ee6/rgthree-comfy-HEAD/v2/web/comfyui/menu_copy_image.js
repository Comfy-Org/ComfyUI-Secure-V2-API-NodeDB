import { comfy } from '/comfy/api/v2.js';
// Adds "Copy Image (rgthree)" to the right-click menu of any node whose type name
// contains "image", copying its output image to the clipboard.
//
// COSMETIC: (8) an entry cannot be positioned among core's own items. The original
//   spliced itself in right after "Open Image"; `b.addMenuItem` appends after every
//   core entry, so the entry is present and sits lower.
//
// DROPPED: the entry suppressed itself when the menu already carried a "Copy Image",
//   which it cannot do now — core's items are not readable from a pack. Worth knowing
//   what that costs: core ships Copy Image for any node holding images, in both
//   renderers — `useImageMenuOptions.copyImage` for Nodes 2.0 and
//   `litegraphService.addNodeContextMenuHandler`'s `getCopyImageOption` for the legacy
//   canvas — and both gate on `ClipboardItem` exactly as the probe below does. So the
//   condition the suppression tested for is now always true, and this entry is always a
//   second way to do what the entry above it already does. The capability is not at
//   risk; the duplicate is the cost, and it is the pack author's call whether to keep
//   the entry at all.
let clipboardSupported = false;
void (async () => {
    try {
        const result = await navigator.permissions.query({ name: "clipboard-write" });
        clipboardSupported = result.state === "granted";
        return;
    }
    catch (e) {
        try {
            if (!navigator.clipboard.write) {
                throw new Error();
            }
            new ClipboardItem({ "image/png": new Blob([], { type: "image/png" }) });
            clipboardSupported = true;
        }
        catch (e) {
            clipboardSupported = false;
        }
    }
})();
async function copyImageUrlToClipboard(url) {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve));
    if (!blob) {
        throw new Error(`[rgthree.CopyImageToClipboard] could not encode ${url}.`);
    }
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}
comfy.defs.extend(/image/i, (b) => {
    b.addMenuItem({
        label: "Copy Image (rgthree)",
        when: (node) => clipboardSupported && node.getOutputImages().length > 0,
        run: (node) => {
            const images = node.getOutputImages();
            // `imgs[imageIndex || 0] || imgs[overIndex || 0] || imgs[0]` — the
            // original fell back to the first image when the user had picked none.
            const url = images[node.getDisplayedImageIndex() ?? 0] ?? images[0];
            if (!url) {
                return;
            }
            copyImageUrlToClipboard(url).catch((e) => console.error(e));
        },
    });
});
