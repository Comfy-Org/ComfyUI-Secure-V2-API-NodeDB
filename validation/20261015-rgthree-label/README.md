# rgthree Label conversion gap

**Status: incomplete.** At corpus commit
`8af0f472e1c43b744324ee3806277e28cde7a1a4`, the V2 implementation of
`Label (rgthree)` is a stub and does not register the node.

The checked-in [V2 JavaScript](../../packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/comfyui/label.js)
contains comments followed by `export {}`. Line 46 explicitly marks the node
`INOPERABLE`. Its bytes match the V2 SHA-256 in the deployable patch manifest,
so the omission is present in the conversion artifact as well as the review
tree.

The [original JavaScript](../../packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/web/comfyui/label.js)
defines `Label` and calls `Label.setUp()` from `registerCustomNodes`. The V2
TypeScript file is an unchanged copy of the original TypeScript; its presence
does not supply the missing deployed JavaScript implementation. Label is a
frontend node, so a backend node count cannot establish its functionality.

This audit verifies source and manifest identities. It does not validate the
historical comments' claims about the current public API, execute a browser
workflow, or certify the rest of rgthree. The pack remains incomplete until
Label is implemented through the supported API, its behavior is tested against
the original, and the materialized tree and patch pair are updated together.

Exact identities and observations are recorded in [AUDIT.json](AUDIT.json).
This finding concerns inherited corpus content; it does not change the three
newly accepted packs recorded in `20261013/` and `20261014-placeholder/`.

## Repository inventory

The accompanying [corpus inventory](CORPUS_INVENTORY.json) reconciles the
repository branches at the recorded revisions. `main` has 171 catalogued packs.
Another 72 are committed on `codex/oct8-conversion-set` and absent from `main`,
giving 243 unique catalogued packs across the branches. The
`codex/v2-author-story-pipeline` catalogue adds no distinct pack IDs to that
union. An additional `comfyui_smznodes` V2 folder is present but omitted from
the catalogue, giving 244 distinct V2 pack folders across the branches.

These are source inventory counts. They do not establish that 244 packs have
passed full functional validation, and do not substantiate the earlier
approximate total of 250 completed packs. The inventory includes the names of
all 72 catalogued packs that are committed but have not reached `main`.
