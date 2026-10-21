# WAN Bindweave direct half r2 validation (publication r14)

Row: WanVideoAddBindweaveEmbeds -> tested (scoped). Label: direct (in-process) half of the reviewed new207 contract, on SDK207 Core 708e6c01 with the frozen e48accf7 image's older pinned deps; comfy-kitchen 0.2.39 test-only root; other new207 pins not installed; Guest half parked.

One selected attempt (m_9548a201ed) of packet wan-bindweave-direct-r2 (5db2e281, CONFIG 6b9b9aed) ran two sequential bounded Linux
containers on WSL CPU (image e48accf7, one thread, uid/gid 1000, no capabilities, no network, read-only root, memory = swap = 6 GiB).
Both roles ran on SDK207 Core 708e6c01 (environment/CORE207_PROVENANCE.json) with comfy-kitchen 0.2.39 as a read-only test-only root
first on sys.path (environment/WHEEL_FETCH_RECEIPT.json, TEST_SITE_MANIFEST.json, R2_ENV_NEEDS.json).

COMPARISON c6fd38a5 (exact): direct 50/50. INTAKE_REVIEW.json (33 checks) recomputed every comparison file byte-equal and checked that the
original loaded comfy_kitchen 0.2.39 from /test-site. HASH_BINDING.json binds the evidence to the staged bytes. r1_attempt/ keeps the
first attempt (m_e89b106958), which stopped at the image's comfy-kitchen 0.2.36.

Live: needs SDK207 (Core 708e6c01); fails on the deployed 0d6ec97e engine.
