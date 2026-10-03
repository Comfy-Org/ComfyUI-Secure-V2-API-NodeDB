# ComfyUI Workflow Vault — Secure Nodes V2

This conversion is pinned to upstream commit
`356c0130503e216fb24b859289b9a93f44129c3f`.

Workflow Vault remains a frontend storage application: it has no Python nodes.
The sidebar and dialogs save, search, version, duplicate, archive, import,
export, and reopen workflows through the typed Secure Nodes V2 API. Entries can
also keep bounded image, video, or audio examples.

The 41 legacy HTTP routes and arbitrary filesystem vault roots are replaced by
host-provided, pack- and user-isolated storage. Archives are explicitly chosen
and downloaded through the bounded file broker. Opening a saved workflow uses
`workflow.open()` with either `mode: "new"` or `mode: "replace"`.

## Legacy migration

Secure mode cannot crawl an old filesystem vault or reveal/open host folders.
Export the old vault while running the legacy extension, then import the JSON
archive from the secure Vault UI. Import rejects malformed, oversized, or
cross-profile data and never grants filesystem access.

Keyboard commands are canvas-scoped; navigation keys are handled only while a
host-owned Vault dialog has focus. The extension does not use the parent DOM,
ambient browser storage, raw network requests, CDN assets, or private backend
routes.
