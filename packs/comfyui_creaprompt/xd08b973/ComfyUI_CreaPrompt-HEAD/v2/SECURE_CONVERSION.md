# Secure Nodes V2 conversion ledger

## Source identity

- Upstream: `https://github.com/tritant/ComfyUI_CreaPrompt`
- Full commit: `d08b9730c1c30211379b2045e5c42b46450b4f87`
- Git tree: `355c69db75c29db2db9f71a7b0cdc97ae2ab17ed`
- Release key: `xd08b973`
- Commit date: `2026-07-22T19:08:00+02:00`

The pristine sibling is the complete 103-file upstream tree at that commit.
The compatibility corpus remained read-only during conversion.

## Exact census and retained behavior

Upstream registers exactly seven backend identities: `CreaPrompt_0`,
`CreaPrompt`, `CreaPrompt_1`, `CreaPrompt_2`, `CreaPrompt_3`, `CreaPrompt_4`,
and `CreaPrompt List`. V2 retains all seven. The first six build one or more
comma-separated prompts from the pinned CSV catalogues and return the source
seed unchanged; the last splits a multiline prompt into synchronized prompt
and seed lists. The weighted node retains the source's exact parenthesized
weight syntax, including its unusual treatment of a weighted `disabled`
selection. Collection mode, random catalogue selection, prefixes, suffixes,
list outputs, schemas, display names, and always-rerun declarations are kept.

Upstream registers exactly one frontend extension, `CreaPrompt_UI`. V2 keeps
the dynamic category combos, the hidden serialized `__csv_json` carrier, the
default eight-category layout, add/remove/remove-all controls, and named
category presets. The reviewed CSV data is compiled into a pack-local ES
module so the opaque iframe needs no private HTTP route or ambient fetch.
User-created presets live in the published per-user `comfy.storage` namespace
instead of mutating the installed pack directory. Host-owned menus and prompts
replace hand-built document overlays, global pointer tracking, `prompt`,
`confirm`, and `alert`.

The six legacy `/custom_nodes/creaprompt/*` routes are therefore represented
without registering a server route: two immutable CSV endpoints become the
sealed catalogue module, while preset list/read/save/delete become scoped
frontend storage operations. The pack's checked workflows, catalogues,
collections, presets, enhancer preset descriptions, license, and README remain
ordinary pack-local resources.

## Security disposition

The optional `CreaPrompt_0` Enhancer behavior is explicitly rejected on
security merits. At this pin it accepts an arbitrary Hugging Face repository
name, downloads an unpinned multi-file snapshot into the global model tree,
loads configuration and processor code with `trust_remote_code=True`, and
caches the resulting foreign model process-wide. Enabling it raises a named,
fail-closed error; it is not weakened into a fixed model, silently ignored, or
reported as supported. Ordinary prompt and collection generation on the same
node remains fully supported.

All seven backend nodes otherwise need no capability: they receive and return
bounded scalar values and read only reviewed files inside their own sealed
pack. Optional image handles are never resolved when Enhancer is disabled.
There is no host import, route, arbitrary network, filesystem mutation,
subprocess, secret, raw tensor, model weight, runtime installation, or shared
mutable state in V2. No shared/core API change and no pack algorithm in core
were required.

## Terminal ledger

- Backend identities: **7 supported / 0 rejected / 0 pending**.
- Frontend registrations: **1 supported / 0 rejected / 0 pending**.
- Non-node route intents: **6 represented / 0 pending**.
- Optional behavior rejection: Enhancer remote-code mode, as described above.

## Frozen API pair

- `comfy-api.pyi`: `9fa75d099086e25a456aad642306fd8d12a5d8f3d1a090b45393018a5b8258a8`
- `comfy-api.d.ts`: `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`

The focused conversion suite differentially executes all seven identities,
runs every identity successfully in one real `GuestSession` process distinct
from the host, proves the Enhancer rejection in that guest, and audits the
reachable Python and JavaScript authority surface. The frontend is tested both
in an isolated module realm and through the production opaque
`sandbox="allow-scripts"` host, including exact hidden-JSON serialization and
`loadGraphData` restoration. The checked patch pair is regenerated and applied
to a fresh pristine copy before release.
