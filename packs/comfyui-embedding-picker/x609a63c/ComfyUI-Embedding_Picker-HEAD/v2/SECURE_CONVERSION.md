# Secure Nodes V2 conversion

Upstream is pinned at `609a63c8457c92cc83126e594d7c95b6be363863`.

## Census

- Python nodes: **1** (`EmbeddingPicker`)
- Frontend extensions: **1** (`trop.EP.QuickNodes`)
- HTTP routes: **0**

The conversion preserves the embedding-name picker, 0.05-step emphasis from
0.0 through 3.0, append/prepend formatting, prompt passthrough below 0.05, and
the context-menu action that creates, positions, colours, connects and selects
a new picker beside either CLIP Text Encode or another picker.

Logical embedding names come from `comfy.models.list('embeddings')`; no model
path is exposed. The target text widget is converted to a typed input through
published widget and slot handles, so the workflow retains the same prompt and
connection semantics without LiteGraph or renderer internals.

The upstream package import deletes a legacy extension file from ComfyUI's web
tree. Secure V2 deliberately removes that host-filesystem mutation. This pack
requires no frontend permission, SDK capability, backend route, arbitrary
filesystem access, storage, network, raw tensor access, or model loading.
