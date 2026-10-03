# Secure Nodes V2 conversion

Upstream is pinned at `fefc2cadf4d5239238f74d1c5fa2b01a19cd681e`.

## Census

- Python nodes: **1** (`PoseEditor2D`)
- Frontend extensions: **1** (`Comfy.2DPoseEditor`)
- HTTP routes: **0**

The conversion preserves the mounted articulated pose editor, pan/zoom and
joint manipulation, head/body/hand variants, texture and background loading,
direct image loading, pose capture, and Standard/Background/Custom output
sizing. Files are selected through the bounded V2 picker. Ctrl/Cmd+Z/Y is
local to the focused mounted editor and never installed globally.

The legacy extension replaced `app.graph.serialize` globally to remove the
large base64 `image_data` value from saved workflows. V2 uses the owning
widget's `beforeSerialize` projection instead: prompt serialization receives
the captured PNG, while workflow and embedded-workflow serialization receive
an empty string. No graph prototype or ambient page state is modified.

The backend uses only the typed raw image capability. Base64 payloads and
decoded dimensions are bounded, malformed data fails closed to the legacy
empty-pose result, and all file, network, process, and host filesystem access
is absent.
