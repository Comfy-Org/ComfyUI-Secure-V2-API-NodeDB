# Secure Nodes V2 conversion

Pinned upstream: `7c4c8f324afb0597d42c5e4bf5c0fc5d292df6af`.

This remains a frontend-only pack: zero Python nodes and one frontend extension.
Its three persisted setting IDs are retained. The four directional shortcuts are
represented by canvas-scoped host commands, with separate Shift bindings so the
configured acceleration remains exact.

V2's command dispatcher owns input, dialog, modal, and interactive-overlay focus.
That replaces the legacy extension's direct inspection of the parent document and
its user-supplied CSS-selector workaround. The compatibility setting is retained so
an existing user profile is not rewritten, but untrusted pack code no longer reads
or queries selectors in the host document.

Horizontal panning still stands down when a selected node exposes multiple output
images or multiple `image` widgets, preserving the host image carousel's arrow-key
ownership.

Shared API dependency:

- `comfy.graph.panBy({ x, y })`, where the delta is expressed in CSS viewport
  pixels and positive values move graph content right/down without changing zoom.
