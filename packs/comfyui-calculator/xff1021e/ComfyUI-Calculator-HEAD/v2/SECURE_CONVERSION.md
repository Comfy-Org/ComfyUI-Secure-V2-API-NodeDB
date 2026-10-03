# Secure Nodes V2 conversion

Upstream: `https://github.com/BobRandomNumber/ComfyUI-Calculator`

Pinned commit: `ff1021e6c817e352fcec8e499c74a5de78afd9b7`

Pinned tree: `ad187c9bd059979126391b3255235335abff4533`

The exact census is supported: one Python node (`Calculator`) and one
frontend extension. The node ID, display name, category, empty input/output
schema, and no-op execution are unchanged.

The frontend no longer imports the legacy application object, patches a node
prototype, appends an ambient DOM widget, or evaluates text as JavaScript. It
mounts the same calculator controls through the typed widget API and uses a
bounded deterministic parser for the intended digit, decimal, addition,
subtraction, multiplication, and division grammar. Each node owns its state
and listeners, and removal or remount releases them.

The screenshot in the pristine `assets` directory documents upstream and is
not needed at runtime.

There are no deliberate behavior gaps.
