# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/phazei/ComfyUI-Prompt-Stash`
- Full commit: `5c46906a932ac5b1b465cdf707beda961f93fc96`
- Git tree: `23aaa2dc66c43a62aae5e174caf715d923f6a81a`
- Release key: `x5c46906`

The pristine sibling contains the exact tracked source at that commit. The
compatibility corpus was read-only throughout conversion.

## Exact census and disposition

The pack registers exactly three backend nodes: `PromptStashSaver`,
`PromptStashPassthrough`, and `PromptStashManager`. All three are supported.
The source has exactly four frontend registrations: the Saver, Passthrough,
Manager, and their shared multi-button renderer. Their complete useful
behavior is supported through three V2 node extensions and host-native button
widgets; the shared renderer therefore needs no separate ambient registration.

The source registers ten HTTP routes. Eight library/list/import/export routes
are supported by one pack-scoped frontend storage value plus the bounded file
picker and download APIs. The two pause-control routes are supported by the
prompt-scoped `prompt-await` interaction. The class-global polling loop,
filesystem persistence, raw DOM/file-input construction, custom server events,
and global `graphToPrompt` monkeypatch are implementation mechanisms and do not
survive.

One non-node side effect is security-rejected: after execution the source asks
for the complete hidden API prompt and embedded workflow, traverses them, and
rewrites this node's serialized widget values. Giving a text utility the whole
graph merely to make future embedded metadata default to the returned text is
not proportionate. V2 preserves the actual output and updates the visible
prompt widget from the bounded node UI result, but never exposes or mutates
unrelated workflow data.

The Manager source also contains a twelve-button joke/demo row whose callbacks
only log, show joke alerts, or toggle one another. It is not Prompt Stash
behavior and is intentionally omitted; the real add/delete/import/export and
clear-paused controls are retained.

## Why D28 exists

Saver and Passthrough both keep an optional linked `text` input so a workflow
can switch between a handwritten prompt and an upstream text generator. When
`Use Input` is false, the pinned frontend deletes only that node's `text` entry
from the one API prompt being queued. This prevents the unused upstream branch
from executing or invalidating the cache while leaving the saved workflow link
intact. Its old implementation wrapped global `app.graphToPrompt` and walked
the entire graph.

V2 expresses the same behavior with the bounded D28 hook:

```js
builder.onPromptSerialize((node) => ({
  omitInputs:
    node.widgets.get('use_input_text')?.getValue() === true ? [] : ['text'],
}));
```

The host accepts only declared input names on the current node, unions multiple
pack projections, and rejects malformed or unknown names. The callback receives
the ordinary read-only node facade, not the prompt, input values, or another
node's state. Workflow serialization occurs separately and is unchanged.

## Authority

Saver and Manager declare no backend permission. Passthrough declares only
`ui.interact`. The guest receives strings and booleans, never paths, host
objects, graph data, model data, network authority, or arbitrary storage. The
frontend runs in the opaque Secure Nodes iframe/worker and uses only
`comfy.storage`, `comfy.files`, node/widget handles, the filtered interaction
event, and its bounded response route.

## Frozen API pair

- `comfy-api.pyi`: `9fa75d099086e25a456aad642306fd8d12a5d8f3d1a090b45393018a5b8258a8`
- `comfy-api.d.ts`: `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`

The TypeScript contract includes D28's `onPromptSerialize` declaration and
the plain-language safety rule above. Both files are exact copies of the
published V2 contracts at this release's final API freeze.
