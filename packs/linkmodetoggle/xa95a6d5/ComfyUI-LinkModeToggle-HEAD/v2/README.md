# LinkModeToggle — Secure Nodes V2

LinkModeToggle adds a small action-bar control and two keyboard shortcuts for
cycling ComfyUI's link rendering mode:

`Spline → Linear → Straight → Spline`

Use **F8**, **Ctrl+K**, or click the action-bar button. The button label and
tooltip always reflect the current core setting, including changes made in
ComfyUI's settings UI.

This Secure Nodes V2 conversion is based on upstream commit
`a95a6d50603495130c1182ba7c85e9eb587e5e33`. It keeps the original MIT license
and author attribution.

## Secure implementation

The extension uses the typed `/comfy/api/v2.js` surface. It does not access
ambient `window` or `document`, private canvas objects, browser storage,
network resources, or backend routes. ComfyUI owns the action-bar placement,
core-setting persistence, and canvas shortcut scoping.

See [SECURE_CONVERSION.md](SECURE_CONVERSION.md) for the census, behavioral
coverage, and migration details.
