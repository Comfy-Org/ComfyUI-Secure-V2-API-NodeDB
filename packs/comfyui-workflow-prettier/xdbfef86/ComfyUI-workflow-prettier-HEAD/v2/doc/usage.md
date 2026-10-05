# Usage

Add **Workflow Prettifier** from `utils`, choose a layout, direction, group
policy, and spacing, then press **Prettify!**. **Equalize Spacing** normalizes an
existing arrangement, and **Undo** restores the latest local layout snapshot.

The same quick layouts are available from the host command palette. The action
bar **Prettify** button applies the default layered layout. When two or more
ordinary nodes are selected, their node context menu exposes alignment,
centering, and distribution commands.

Local undo is isolated per open workflow and visible graph. It does not cross
between documents or subgraphs, and closing a document discards its snapshots.
