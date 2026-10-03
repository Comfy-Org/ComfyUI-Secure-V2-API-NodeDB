# Secure Nodes V2 conversion

Upstream: `https://github.com/Cordux/ComfyUI-ImagePreviewPause`

Pinned commit: `450407917c79ea03c80e5ae030d2fcedfa87b501`

The single Python node and single frontend extension are supported. The V2
node preserves the `ImagePreviewPause` ID, wire schema, output-node flag,
batch preview, continue passthrough, and cancel-interrupt behavior.

The legacy implementation wrote tensors to arbitrary temp paths, emitted
server events, stored execution state in a process-global dictionary, polled
with blocking sleeps, and exposed two custom routes. The conversion delegates
preview creation to `ctx.ui.preview_images` and waiting to
`ctx.interact.request`. The host interaction broker supplies invocation-scoped,
one-use response tokens. Cancellation uses the explicit
`ctx.execution.interrupt` capability.

The frontend is a mounted canvas plus typed buttons. It loads only managed
preview identities, keeps concurrent node executions isolated, queues repeated
executions of one node, and drops duplicate or late responses. Removal cancels
that node's outstanding interactions and releases loaded image bitmaps.

There are no deliberate behavior gaps.
