# Secure Nodes V2 conversion

This directory converts ComfyUI-LinkModeToggle at upstream commit
`a95a6d50603495130c1182ba7c85e9eb587e5e33`.

## Census

- Python nodes: **0**
- frontend extensions: **1**
- backend routes: **0**
- pack settings: **0**
- JS-only graph nodes: **0**

The pack is a frontend-only convenience control for the existing
`Comfy.LinkRenderMode` core setting.

## Preserved behavior

- F8 and Ctrl+K cycle Spline → Linear → Straight → Spline.
- Both shortcuts are canvas-scoped, so text inputs and other focused controls
  retain their keys.
- A host-owned action-bar button shows the current mode and cycles it on click.
- The core setting is the only persistence source. External setting changes
  update the button, and failed writes leave it synchronized with host state.
- Re-running the ready callback removes the prior button and setting observer
  before mounting replacements.

## Security changes

The original extension mutated LiteGraph internals, queried and observed the
ambient document, attached keyboard listeners to several global targets, and
stored a second copy of the setting in `localStorage`. The V2 conversion uses
only `/comfy/api/v2.js`: `comfy.settings`, `comfy.commands`,
`comfy.ui.addActionBarButton`, and `comfy.onReady`.

No frontend permission and no backend authority are required.

## Deliberate differences

- The button is placed by the host rather than by querying private toolbar
  markup or floating over the page.
- The current core setting replaces the stale shadow value that the original
  stored in `localStorage`.

There is no remaining pack-specific behavior gap.
