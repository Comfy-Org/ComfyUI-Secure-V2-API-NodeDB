# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/sinfisum/comfyui-prompter`
- Full commit: `b690ff20ad4c0f686c15ed577b4b21eaaeec7aaf`
- Git tree: `62e00363e3c561e467716b690614b07608651d29`
- Release key: `xb690ff2`
- Commit date: `2026-07-08T11:30:14+03:00`

The pristine sibling is an exact materialization of all nine tracked files at
that commit. The compatibility source remained read-only during conversion.

## Census and retained behavior

Upstream registers exactly one backend node, `PromptSaverNode`, displayed as
`Prompt Saver & Loader` in `utils`. Its required inputs are the searchable
`selected_title` combo, `auto_save` boolean, `title_name` string, and multiline
`prompt_text` string. Its sole `prompt` STRING output is exactly the incoming
prompt text.

Upstream also registers exactly one frontend extension,
`ComfyUI.PromptSaver`. Its non-node implementation owns four private routes,
a JSON title index, individual prompt text files, default timestamp/workflow
titles, manual save, selection/load, a 60-second title refresh, and a
60-second debounced auto-save that adds `_auto_N` when a title already exists.
The remaining artifacts are one PNG, an empty initial index, and a ZIP that
contains only the upstream LICENSE and README.

V2 retains the pure backend pass-through and all prompt-library lifecycle
behavior. It preserves the upstream filename sanitization and collision rules
inside the storage index, keeps individual prompt bodies independently
addressable, cancels node-owned timers when a node is removed, and uses
graph-scoped node identities so equal node ids in subgraphs cannot share state.
The selected title remains in saved and embedded workflows, while prompt-only
serialization substitutes the schema's `[New Prompt]` sentinel: the backend
never consumes that field, and static combo validation therefore cannot depend
on a user's private frontend library.

## Authority and API result

The user's prompt library now uses the published per-user `comfy.storage`
authority instead of pack-directory filesystem writes and private HTTP routes.
The frontend uses published definition, widget, workflow-name, notification,
and storage facades, imports only `/comfy/api/v2.js`, and runs in the opaque
Secure Nodes frontend sandbox. The backend node declares no permissions: all
four inputs and the output are bounded scalar values.

There is no ambient host import, route, arbitrary network, filesystem,
subprocess, model, secret, raw-tensor, runtime-install, or shared mutable
authority in V2. No shared/core API change and no pack algorithm in core were
needed.

## Frozen API pair

This release is sealed against:

- Python stub SHA-256:
  `5c94bedf783e9e92971d0369fabc23b10d6f7169fc86fecdee64a3607d9f3142`
- TypeScript stub SHA-256:
  `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`
