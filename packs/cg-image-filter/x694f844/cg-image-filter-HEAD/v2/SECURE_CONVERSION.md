# Secure conversion status

Pinned upstream: `https://github.com/chrisgoringe/cg-image-filter` at
`694f8444e67f44d601861c5604bb3e55c35daf9d` (release `x694f844`).

Backend: 12 supported, 0 rejected, 0 pending.

Frontend: 1 supported, 0 rejected, 0 pending.

The three interactive filters use brokered, one-use interaction tokens. Their
selection, text-edit, timeout/reset, mask-painting, previous-mask, extras,
video-grouping, and cancellation behavior stays in this untrusted pack. The
frontend is an opaque-iframe-safe V2 extension and renders its modal editors
through the generic Remote-DOM dialog bridge. Edited masks are uploaded to the
confined temp catalogue and read back through managed asset identities.

The nine list, batch, string, numeric, and crop helpers remain pack-side
algorithms. They use opaque references or explicitly granted raw tensor access
according to each node's actual behavior.

One optional legacy subfeature is intentionally rejected: `audiofile` cannot
name an arbitrary local path or network URL. The three immutable bundled
sounds (`beep.mp3`, `ding.mp3`, and `honk.mp3`) remain supported. No backend
node or frontend registration is rejected because of that narrower authority.

The pristine sibling is byte-for-byte pinned independently of this `v2`
directory. The generated manifest is verified by the focused conversion test.
Public SDK stubs and the checked patch pair will be sealed and round-trip
verified after the shared V2 surface is frozen.

## 2026-10-29 independent review correction R2 - UNRUN-IN-GUEST

Two manifest fingerprint flags now match their existing inherited implementation. The proposed validator restoration was rejected by independent review: uppercase VALIDATE_INPUTS is ignored on original V3 classes. All three validator rows remain false, and the implementation file is byte-identical to production, preserving Core min/max/option checks.

Generator-defect workaround: the current discovery generator omits inherited hooks. Changed validation_inputs rows must be emitted by the real pinned packmanifest.encode_validation_inputs from genuine source classes in bounded isolated discovery, then match the inert gate and independent review. The bounded real-source encoder proof now passes: 43 declared validator rows across six packs, including the 16 changed signature rows, were emitted by pinned packmanifest4c6772a3 and all six resulting manifests are byte-identical. PROOF.json SHA256 ad7e5710761da87f89e0c2d45f1a317d383cff5462f28066ff27271ef734445e. Only this report was updated after that proof; node code and manifest bytes are unchanged. This is signature encoding, not full schema discovery or execution parity. Regenerate and byte-compare when the fixed canonical generator exists. Stubs pending canonical 0cd9adec pair; existing pyi/d.ts files are untouched. No new Guest, algorithm, graph, model or browser execution. Only Root publishes changed files, preserving Git modes; local replay bundle ZIPs are not publication artifacts.
