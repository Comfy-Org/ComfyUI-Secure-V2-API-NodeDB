# Secure Nodes V2 conversion

- Upstream: `https://github.com/DRuggeri/ComfyUI-Dropdown-Switch`
- Commit: `7f49efee32569cfd2ebca0637fba3767fd76894e`
- Source tree: `dc70ef653275e4d25c13c7848a19a75df3659bc0`
- Release key: `x7f49efe`
- Frozen Python stub SHA-256: `5c94bedf783e9e92971d0369fabc23b10d6f7169fc86fecdee64a3607d9f3142`
- Frozen TypeScript stub SHA-256: `5c94bedf783e9e92971d0369fabc23b10d6f7169fc86fecdee64a3607d9f3142`

The pinned pack has no backend node IDs. Its exact census is one frontend
registration and one frontend-only virtual node intent, `DropdownSwitch`.

## Ledger

| Kind | Identity | Status | V2 behavior |
| --- | --- | --- | --- |
| Frontend registration | `DropdownSwitch.Extension` | supported | Replaced by one `/comfy/api/v2.js` module registration. |
| Frontend-only node intent | `DropdownSwitch` | supported | Declarative frontend node with serialized labels, dynamic input management, a Primitive-compatible combo, literal label output, and selected-input forwarding. |

Supported: 2/2 exact census items. Rejected: 0. Pending: 0.

The original temporarily rewrote graph links and replaced `graphToPrompt` to
exclude unselected branches. V2 expresses the same execution result as a pure
`defs.define({ execution: "frontend", resolve })` answer: output 0 is the
selected label literal and output 1 forwards only the selected input. The host
prompt resolver owns traversal, so unselected inputs are never reached and the
saved workflow remains untouched.

Dynamic add, remove, rename, insert, and reorder behavior is retained through
host slot handles. The choice socket publishes a combo widget configuration,
so a connected Primitive receives the current label list without discovering
or writing private Symbols. Labels are preserved through `onSerialize` and
restored through `onConfigured` without replacing linked slot objects.
The pinned remove-last behavior, automatic-label collision rules, explicit
rename semantics, selected-label preservation, and connected-choice widget
disablement are also retained.

The slot-specific legacy context-menu entries are grouped into named submenus
because the V2 menu callback does not expose renderer hit-test coordinates.
All operations remain reachable and preserve their graph/link behavior; only
menu placement changes. The original fixed colors and initial size are retained.

No network, filesystem, backend route, ambient DOM, `window`, LiteGraph,
prototype mutation, or prompt monkeypatch authority is requested. No
shared/core API change was required.

The production harness uses the real ComfyUI node registry, graph, prompt
builder, Secure Nodes iframe/worker, and frontend resolver. It proves that both
widget-selected and Primitive-selected branches emit the selected label and
forward only the selected upstream reference; the unselected source and both
frontend-only selector nodes are absent from the backend prompt. The same run
exercises the installed add, insert, move-up, move-down, and remove menu
trampolines, verifies serialized labels and Primitive combo values, and reports
an empty pack-error ledger. The isolated harness additionally exercises rename,
remove-last, and in-place configure/serialization behavior.
