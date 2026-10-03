# Secure Nodes V2 conversion

Upstream is pinned at `2453383e1249054439d81bf53145edecc9ee79a7`.

## Census

- Python nodes: **1** (`ShowText`)
- Frontend extensions: **1** (`ShowText`)
- HTTP routes: **0**

The conversion preserves list-aware string input and output, output-node
execution, execution-result display, the upstream leading-empty-item behavior,
read-only multiline text, workflow restoration, and bounded automatic height.

The legacy implementation wrote display text into `extra_pnginfo` by locating
and mutating the workflow node. Secure V2 instead stores the display state in a
serialized mounted value that is explicitly excluded from prompt submission.
This preserves workflow restoration without hidden prompt/workflow authority or
graph mutation. The mounted view uses its supplied owner document, renders only
through text-area values, and removes its subscription and DOM on teardown.

The pack requires no SDK capability, frontend permission, route, storage,
network, filesystem access, ambient DOM, or renderer internals.
