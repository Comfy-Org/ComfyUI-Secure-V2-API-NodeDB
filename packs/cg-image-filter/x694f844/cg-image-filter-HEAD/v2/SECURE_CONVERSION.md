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
