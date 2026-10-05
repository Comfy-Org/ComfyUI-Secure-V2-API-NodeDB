# ComfyUI Connection Helper — Secure Nodes V2

This conversion preserves the three graph-wiring operations from the pinned
upstream release:

- connect each first empty input type from the nearest compatible node on the left;
- copy input links from the nearest node; and
- copy both input and output links from the nearest node when the target is disconnected.

Open a node's context menu and choose **Connection Helper**. The legacy pack
painted the same three actions directly into the shared canvas title bar. V2
uses the host-owned node menu so it works in both renderers and never patches
node prototypes or touches the ambient canvas.

The extension has no backend nodes, routes, storage, network access, or
frontend permissions.
