z-image-power-nodes rev 3 (docs only): the six custom widget types cannot register on the live stack.

Source reading only. Nothing was run, and no code, manifest or test changed. The live sandbox (host-stack r3, guest `c6b97a15`, host-entry `63d9437e`) has no `comfy.defs.defineWidgetType`: the call goes through the generic RPC proxy, the `render` function cannot be structured-cloned, and the registration is rejected. By the published API (`comfy-api.d.ts`, `DefRegistry.defineWidgetType`), an unregistered input type becomes a socket and its value is dropped. Each affected node has required ZIPN inputs (`ZIPN_CENSUS.json`), so 18 of 31 nodes cannot be queued from the live UI: the 7 partly tested nodes and 11 tested (scoped) nodes, which are now labelled "backend only; live UI blocked". Counts are unchanged.

Files:
- `ZIPN_CENSUS.json`: every ZIPN input per node from `v2/secure-nodes.json`, with required/optional and the report class.
- `LIVE_SOURCE_FACTS_COMPACT.json`: file hashes and the checked line references (live guest and host, `v2/` sources, the frozen bridge draft).
- `ACCEPTANCE_SPEC.md`: the browser gate. Check 0 (each widget type registers rather than becoming a socket) is expected to fail on the live stack until the bridge ships. It doubles as the bridge's regression test.

The block lifts with the platform's `defineWidgetType` bridge (guest half and host bridge), which has been requested from the platform owners. Until then the backend-scoped evidence of the 24 tested nodes stands, but for the 11 affected ones it does not cover live UI use.
