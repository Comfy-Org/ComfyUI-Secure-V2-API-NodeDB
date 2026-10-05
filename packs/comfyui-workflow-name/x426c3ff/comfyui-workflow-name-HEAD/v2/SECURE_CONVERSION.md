# Workflow Name — Secure Nodes V2 conversion

- Upstream: <https://github.com/MichinariNukazawa/comfyui-workflow-name>
- Pinned commit: `426c3ff09e24485b06b3df2565ca7380e100aa56`
- Release key: `x426c3ff`
- Census: one Python node, one frontend extension, one legacy route.

The legacy frontend read an internal active-workflow object, monkey-patched the
global queue method, walked the graph's private node array, and called a custom
route whose only job was filename sanitization. The V2 conversion reads the
active document's bounded display name, updates every WorkflowName node in the
document (including subgraph definitions), and performs the final synchronous
write through `queue.onBeforeRun`. Sanitization remains pack-side and pure.
There is no backend route, filesystem access, network access, or ambient host
authority.
