# AI Project Context

## Purpose
`ComfyUI-LinkModeToggle` is a small ComfyUI frontend extension that adds hotkeys and a canvas toolbar control for cycling link render modes (Spline, Linear, Straight), with browser-side persistence.

## Architecture
- Pure frontend extension; no server-side behavior is required.
- Current compatibility targets modern ComfyUI frontend/LiteGraph while retaining graceful fallbacks for older internal APIs.
- Key UX features are the F8/Ctrl+K hotkeys, toolbar button/badge, and localStorage persistence.

## Working rules
- Read `README.md` before UI changes.
- Preserve zero-server-change behavior unless explicitly requested otherwise.
- Be conservative with private/internal ComfyUI APIs; retain compatibility fallbacks where practical.
- Do not add heavyweight dependencies for a small frontend utility.
- Verify the extension still loads cleanly after changes and update README for changed hotkeys, UI behavior, installation, or compatibility assumptions.
