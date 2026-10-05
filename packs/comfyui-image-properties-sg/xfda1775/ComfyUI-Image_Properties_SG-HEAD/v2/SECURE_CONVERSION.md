# Secure Nodes V2 conversion

This conversion is pinned to upstream commit
`fda1775b8e182f7409a1ee392919b5f86356a141` (tree
`f2f2b485d89c97b2917fc12181f5cbf49af392f4`).

## Census and support

- 4 of 4 Python nodes are supported with their original node IDs, schemas,
  outputs, metadata display, and image-format controls.
- 4 of 4 frontend extensions are replaced by typed, mounted Nodes V2 UI.
- The pristine pack has no HTTP routes or settings.

Image reads use the bounded input-assets broker. Tensor inspection uses declared
raw-reference access. Durable image writes use the output broker, and BMP/TIFF
previews use the UI broker. The frontend reads only node-scoped execution
payloads, uses safe text nodes, and tears down widget subscriptions and pending
image loads with the node.

The legacy save node references an undefined `image_path`, so its displayed
post-save file size is always `0.00MB`; this published behavior is preserved.
There are no intentional conversion gaps.

## Verification

The conversion tests cover the exact census and schema, metadata extraction,
filename templates, RGBA mask loading, all format-option mappings, broker
permissions, isolated guest execution of every node, four concurrent frontend
instances, serialization/restoration, format-widget visibility, remount and
teardown, manifest freshness, and a byte-exact pristine-to-V2 patch round trip.

