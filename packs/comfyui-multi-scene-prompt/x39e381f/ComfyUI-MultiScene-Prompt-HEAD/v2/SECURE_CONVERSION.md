# Secure Nodes V2 conversion

Pinned upstream: `39e381f1146c99b0aa0967d6e1229acb74751055`

## Census

- 1 Python node: `MultiScenePrompt`
- 1 frontend extension
- 0 backend routes
- 0 JS-only graph nodes

The backend remains a pure prompt-composition node with the same two string
inputs, hidden node id, and three outputs. The tabbed editor is now a node-local
mounted control. Its scene array is the serialized `scenes_json` input, so saved
workflows and API prompts retain the original wire format without graph mutation.

The mounted UI uses only the document belonging to its supplied container. It
does not access ambient DOM, storage, networking, backend routes, or global input
listeners. Scene count, per-scene text, and serialized input size are bounded;
malformed state fails closed or uses the pinned implementation's documented
malformed-JSON fallback. The pack requests no frontend or Python permissions.
