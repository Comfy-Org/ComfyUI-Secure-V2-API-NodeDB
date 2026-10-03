# Secure Nodes V2 conversion

This directory is the Secure Nodes V2 conversion of
`INuBq8/ComfyUI-PanelComposer` pinned at commit
`2adf5ad8dea4a7ad88c1f4c20d8eb8cb7616de31`.

## Supported surface

- All four original Python node IDs and their schemas are preserved:
  `PanelLayoutProvider`, `PanelCompositor`, `ListGetItem`, and `TupleUnpack`.
- The two `PanelLayoutProvider` frontend extensions are preserved as typed V2
  extensions: the mounted layout browser/preview and the panel drawing dialog.
- The drawing dialog keeps local undo/redo, polygon validation and repair,
  overlap warnings, vertex and panel editing, snapping, ordering, canvas shape,
  preset loading, and dialog-scoped keyboard shortcuts.
- Built-in layouts are sealed pack data. Per-user layout libraries use
  `comfy.storage`; no pack HTTP routes or shared writable server file remain.
- A selected custom layout is bounded, validated, and serialized into the
  existing `layout_preset` workflow input. Backend execution therefore does
  not depend on mutable user or server state.

The frontend requires no ambient permission. Python image nodes request only
the `raw` tensor capability used to materialize and return `ImageRef` values.

## Deliberate migration boundary

The legacy shared `web/layouts_user.json` file is not imported automatically.
Secure V2 has no authority to read an arbitrary historical pack file, and
silently copying one server-wide library into every user's private storage
would have incorrect ownership semantics. Existing layouts can be recreated
or imported by a future explicit, user-authorized migration facility.

## Verification

The conversion tests cover the exact census and schemas, all built-in layout
data, bounded custom-layout graph serialization, private storage and failure
semantics, polygon repair/overlap and isolated history, scoped frontend APIs,
real guest execution for image production/composition, manifest freshness,
and a byte-exact pristine-to-V2 patch round trip.
