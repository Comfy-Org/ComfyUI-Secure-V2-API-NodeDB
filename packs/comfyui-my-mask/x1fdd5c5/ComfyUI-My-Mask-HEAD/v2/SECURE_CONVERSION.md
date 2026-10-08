# My-Mask V2 conversion

Exact upstream 1fdd5c50bfe2e00164f2026871715e201a2eb684. Two registered
backend nodes, zero frontend extensions/routes. The misspelled Botton ID is
retained. All six files correspond to the complete pinned Git tree and
TLS-verified codeload archive. No LICENSE is supplied; local conversion tests
do not establish publication rights.

Both wrappers declare inspect/raw. Public MaskRef.describe gates rank2/rank3,
dimensions <=4096, <=1048576 logical elements and <=128MiB projected local
ownership before raw. The projection reserves worst16-byte tensor snapshots,
native contour/hierarchy/stack/hull arrays, casts, outputs and publication.
This is a conservative pack workload admission, not a measurement or physical
limit on all native OpenCV allocator activity. The original nodes.py is
byte-exact; both numerical algorithms stay in the pack.

No contours returns the original managed mask identity. Computed results
retain native shape/dtype/values: whole convex output float32, bottom-half
output retains input dtype/top half. Fractional mask values use the source
uint8 cast. Native small malformed rank/batch, unsupported BF16 .numpy(),
empty image and complex cast errors are not replaced with fallback output.
Raw transport supplies CPU owned snapshots and can lose original strides
and autograd state; tested contract covers plain CPU numerical masks without
gradient tracking and contiguous layout. Noncontiguous source views are tested
in-process separately; public raw snapshots normalize their strides and can
avoid a native OpenCV fillPoly layout error. Guest controls compare those
snapshots with the source called on the same contiguous buffer, not with the
original failing view. GPU/autograd/noncontiguous-layout parity is not claimed.

Python3.13 is the selected development runtime; exact inherited wheel versions
are declared. No dependency install, Internet grant, service authority, model
weights or toolchain compilation is needed. Required local Seatbelt guest and
production outer tests are source-root fixtures, not a sealed image or Cloud
deployment. No durable authored state or automatic cache is introduced.

| ID | Local disposition |
| --- | --- |
| MaskToBottonHalfConvexMask | supported within the bounded plain CPU mask profile |
| MaskToConvexMask | supported within the bounded plain CPU mask profile |
