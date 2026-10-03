# Secure Nodes V2 conversion

Upstream: `https://github.com/wul7chaos/Comfyui-nixie-timer`

Pinned commit: `61d10e850a2706ce0be4a070f34b2295624c22bd`

Pinned tree: `dee06327341a23143b0b50b374bf2b6a6f34ef8f`

The exact census is supported: one Python node (`NixieTimer`) and one frontend
extension. The node ID, display name, category, seven-value color combo,
default, no-output schema, and no-op execution are unchanged.

The frontend no longer patches `app.queuePrompt`, consumes raw application
objects, or appends CSS and widgets to the ambient document. It mounts the
clock inside its node with the typed widget API, observes the typed queue and
core locale setting, and listens only to the host execution-error event.
Multiple mounted nodes deliberately share one run timer. When the last mount
is removed, all queue/settings/backend subscriptions, interval work, and
pending animation frames are released.

The bundled upstream `node.zip` is retained only in the pristine snapshot. It
is a distribution archive and is not loaded by the converted runtime.

There are no deliberate behavior gaps.
