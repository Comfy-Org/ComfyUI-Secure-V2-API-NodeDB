# WanVideo scheduler provenance

The Python modules in this directory are an exact copy of
`wanvideo/schedulers/` from:

- Project: `kijai/ComfyUI-WanVideoWrapper`
- Upstream URL: <https://github.com/kijai/ComfyUI-WanVideoWrapper>
- Commit: `aa9f4749587c0f8a5041a56bcc4e4a07ca76c4f0`
- Commit date: 2025-11-14
- License: Apache License 2.0 (included as `LICENSE`)

The only modification to the copied scheduler modules is in `__init__.py`:
the upstream `from ...utils import log` dependency was replaced by a standard
library logger so the module tree is self-contained inside this secure-node
guest. Scheduler calculations are otherwise unchanged.

The TripleKSampler wrapper additionally handles the upstream `multitalk`
schedule in its own pack code. At this pinned revision, `multitalk` appears in
the public scheduler list but is intentionally constructed inside
`WanVideoSampler`, not by `get_scheduler()`.
