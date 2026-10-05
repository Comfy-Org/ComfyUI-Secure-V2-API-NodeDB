# Workflow Prettier — Secure Nodes V2

This is the Secure Nodes V2 conversion of
[ComfyUI Workflow Prettier](https://github.com/deepme987/ComfyUI-workflow-prettier),
pinned at `dbfef86c7c5f2f38c3b49e55acdbc02e7859433b`.

It preserves the four layouts, group-aware arrangement, three flow directions,
spacing controls, selection alignment/distribution, and the pack's 10-step
local undo. The Python node remains a no-op configuration surface; graph edits
run through typed frontend handles in one host undo transaction.

The old prototype-patched canvas menu is represented by host commands and a
Prettify action-bar button. Alignment remains available from node context menus
when two or more workflow nodes are selected.

See [usage](doc/usage.md) and [conversion notes](SECURE_CONVERSION.md).
