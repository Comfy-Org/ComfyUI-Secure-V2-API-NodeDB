# ComfyUI Live Preview

A ComfyUI node that displays a large floating overlay window showing live denoising step previews as your image generates — similar to the live preview in A1111 and Forge.

## Features

- **Full-size live preview** — watch the image form step by step in a large resizable window instead of the tiny built-in thumbnail
- **Draggable and resizable** — drag by the header, resize from the bottom-right grip, position it anywhere on screen
- **Remembers where you put it** — position and size persist across page reloads, and the window is always kept fully inside the browser viewport so it can't be dragged out of reach
- **Step counter and FPS display** — shows current step and preview frames per second in the header
- **Status indicator** — green dot while generating, purple when done
- **⚡ Toggle button** — persistent floating button in the bottom-right corner of the ComfyUI page to show/hide the window at any time
- **Zero overhead** — hooks into ComfyUI's existing websocket preview stream, no extra processing

<img width="248" height="163" alt="Screenshot 2026-05-29 143825" src="https://github.com/user-attachments/assets/2d617bbe-5308-4fee-8f5d-27a397f4d277" />

<img width="1065" height="681" alt="Screenshot 2026-05-29 144904" src="https://github.com/user-attachments/assets/9188f642-9f30-4424-8c9a-6a1d34c76da4" />

## Installation

**Option 1 — Clone into custom_nodes:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/TechnoWarrior2/comfyui-live-preview
```

**Option 2 — Manual download:**

Download the repo as a ZIP, extract it, and place the folder inside `ComfyUI/custom_nodes/`.

Then restart ComfyUI.

## Usage

Find the node by searching **Live Preview (Large)** in the node menu under the `image` category.

The node is a simple pass-through — connect IMAGE in and IMAGE out like any other image node, or leave it floating unconnected anywhere in your workflow. Either way the preview window will activate the moment generation starts.

| Input | Output |
|-------|--------|
| `images` (IMAGE) | `images` (IMAGE) — unchanged pass-through |

The **⚡ button** in the bottom-right corner of the ComfyUI page toggles the preview window independently of generation — useful for checking the last generation after it finishes.

## Notes

- The preview window only activates when a Live Preview node is present somewhere in the workflow graph
- ComfyUI must have previews enabled (`--preview-method auto` or similar) for frames to broadcast — if you're getting no preview frames, check your launch arguments

## Updating

```bash
cd ComfyUI/custom_nodes/comfyui-live-preview
git pull
```

Then restart ComfyUI.

## Upgrading from 1.0

**1.1.0 renamed the node's internal id** to `LivePreview`. Workflows saved with 1.0 will load with a red **missing node type: AlexLivePreview** box where the node used to be.

To fix a workflow: delete the red node, search for **Live Preview (Large)** to add it again, reconnect it if it was wired into an image chain, and re-save. Nothing else in the workflow is affected — the node is a pass-through, so it has no settings to carry over.

The overlay's saved position also resets once on first load after updating; it will stick again from there.
