<p align="center">
  <img src="assets/comfyjot-readme-banner.svg" alt="Comfy Jot banner" width="100%" />
</p>

<p align="center">
  Frontend-only canvas notes for ComfyUI.
  Draw reminders, arrows, and quick workflow callouts directly on the graph, then save them with the workflow.
</p>

## Overview

ComfyJot adds a drawing layer above the ComfyUI canvas so you can annotate workflows without dropping extra note nodes everywhere. It is built as a `WEB_DIRECTORY` frontend extension, which means there are no backend nodes to manage and no separate storage layer outside the workflow itself.

The current UI is designed to feel native to ComfyUI:

- Bottom-centered floating tool dock inside the graph canvas
- Sidebar doodle icon that toggles the overlay on and off
- Brush and eraser tools with a compact inline size control
- Color picker plus quick swatches
- Undo, redo, clear, and note visibility controls
- Zoom support while ink mode is active

## Highlights

- Workflow-bound notes
  Strokes are saved to `workflow.extra.comfyjot`, and ComfyJot also stores a cropped transparent canvas snapshot alongside them so annotations travel with the workflow JSON in both editable and baked form.

- Fast graph markup
  Sketch arrows, circle areas, write visual reminders, or block out rough planning notes without leaving the canvas.

- Native-feeling controls
  The dock uses ComfyUI theme variables and sits above the graph instead of opening a separate editor.

- Frontend-only architecture
  No inference nodes, no custom execution path, and no server routes are required.

## Requirements

- ComfyUI `>= 0.16.0`
- Python `>= 3.10`

## Installation

### Manual install

1. Place this folder inside your ComfyUI `custom_nodes` directory.
2. Make sure the folder name is `Comfyjot`.
3. Restart ComfyUI.

Example path:

```text
ComfyUI/custom_nodes/Comfyjot
```

## How To Use

1. Click the ComfyJot doodle icon in the left sidebar, or use `Ctrl+Shift+J`.
2. The overlay opens with `Ink Off` by default so normal graph interaction stays safe.
3. Turn `Ink` on when you want to draw.
4. Adjust brush size, pick a color, and annotate directly over the canvas.
5. Turn `Ink` off to go back to normal node interaction while keeping notes visible.

## Notes And Persistence

ComfyJot stores its annotation payload in:

```text
extra.comfyjot
```

That payload now includes editable stroke data plus a cropped PNG snapshot of the note canvas. It gives you a few useful properties:

- Notes save with the workflow file
- Notes reload with the workflow file
- Notes are not tied to browser-local storage
- Shared workflows can carry their visual annotations with them

## Commands And Settings

### Commands

- `Comfy Jot: Toggle Overlay`
- `Comfy Jot: Toggle Ink Mode`
- `Comfy Jot: Undo Stroke`
- `Comfy Jot: Redo Stroke`
- `Comfy Jot: Clear Notes`

### Default keybinding

- `Ctrl+Shift+J` toggles the overlay

### Settings

- `Default brush size`
- `Auto-show saved notes on workflow load`

## Project Layout

```text
Comfyjot/
├── assets/
│   └── comfyjot-readme-banner.svg
├── locales/
│   └── en/
│       ├── commands.json
│       └── settings.json
├── web/
│   ├── icons/
│   │   └── doodle.svg
│   ├── jot/
│   │   ├── constants.js
│   │   ├── graph-store.js
│   │   ├── overlay.js
│   │   └── styles.js
│   └── comfyjot_extension.js
├── __init__.py
├── pyproject.toml
└── README.md
```

## Development Notes

- `__init__.py` exposes the frontend through `WEB_DIRECTORY`
- `web/comfyjot_extension.js` registers the extension, commands, settings, and sidebar launcher
- `web/jot/overlay.js` owns the dock UI, drawing behavior, history, and canvas interaction
- `web/jot/graph-store.js` reads and writes stroke data into workflow `extra`

## Verification

- JavaScript modules validate with `node --check`
- Python package entrypoint validates with `python3 -m py_compile`

## License

MIT
