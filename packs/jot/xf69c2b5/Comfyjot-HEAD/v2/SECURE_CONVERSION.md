# Secure Nodes V2 conversion

Pinned upstream: `f69c2b561f2c98c3ee48339030e47da101435ee2`.

ComfyJot remains a frontend-only pack with zero Python nodes. Its drawing
surface runs in the opaque worker and is rendered by the host-owned graph
overlay. Pointer events arrive with graph coordinates, and the host leaves the
surface click-through until ink mode is enabled. Wheel gestures still reach the
graph while drawing.

The editable stroke document and its PNG snapshot continue to use
`workflow.extra.comfyjot`. Undo and redo remain local to ComfyJot's 60-entry
history. While ink mode owns focus, `Ctrl+Z`, `Ctrl+Y`, and `Ctrl+Shift+Z` are
handled inside that local history and do not also reach ComfyUI's global graph
history. The original sidebar launcher is represented by a host action-bar
button plus the original `Ctrl+Shift+J` canvas command; the drawing tools stay
in a bottom-centered viewport panel.

Required frontend capabilities:

- `ui.graph-overlay`
- `ui.viewport-panel`
- `workflow.extra`
