# Secure Nodes V2 conversion

Upstream is pinned at `3fbc963edc0eda54b9076a1d754610c9f322fd1b`.

## Census

- Python nodes: **1** (`ImageCompareNode`)
- Frontend extensions: **1** (`SBCODE.ImageCompareNode`)
- HTTP routes: **0**

The conversion preserves first-image selection from both input batches,
aspect-preserving A/B display, the draggable split slider, labels and source
dimensions, node resizing, and preview replacement after each execution.

The legacy backend encoded both images into chunked base64 strings and sent
them through the UI result. V2 selects each first image through its opaque ref
and publishes two bounded managed temporary previews. The frontend reads their
URLs from `NodeHandle.getOutputImages()`; it carries no image bytes or data
URLs over the extension channel.

The comparer is a mounted, pack-owned canvas. Its DOM, pointer capture, image
elements, and listeners belong only to the sandboxed mount and are released on
teardown. It uses no ambient host DOM, frontend permissions, backend routes,
filesystem, network, raw tensor access, or persistent storage.
