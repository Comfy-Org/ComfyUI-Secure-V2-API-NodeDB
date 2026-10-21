# WAN I2V Step 1 r2 validation (publication r9)

Synthetic column for `WanVideoSampler`, `WanVideoSamplerFromSettings` and `WanVideoSamplerv2`: "I2V code path: synthetic code-path parity only; no real I2V model admitted". The rows stay partial
(staged), and the synthetic column does not count as tested.

One selected attempt (m_8b6d9c4119) of packet wan-i2v-step1-r2 (a9e4a4cc, CONFIG 5b205f5e) ran three sequential bounded Linux
containers on WSL CPU: fixture, original and converted. Image e48accf7, Python 3.13.7, torch 2.8.0+cu128. Each ran as uid/gid
1000 with no capabilities, no network, a read-only root and memory = swap = 6 GiB. An independent review of r1 came back
CLEAR_WITH_NOTES (REVIEW_R1_REF.json), and r2 addressed those notes (DELTA_NOTES_r2.md).

COMPARISON 6abc2815 (comparator rev6, exact): all 141 checks true, across five items.
- t2v_regression: the trained 1.3B T2V latent equals r8 and r3 (0302c148).
- i2v_dict_on_t2v_model (t1): a plain I2V dict with the trained 1.3B T2V raises the original's ValueError after load, on both
  sides. This is the user-reachable change.
- i2v_plain (synthetic column): plain I2V with clip (cfg 1 and 2) and without clip (cfg 2) is exact on a seeded synthetic i2v
  checkpoint (FIXTURE.json; built by the untouched original constructor).
- batched_cfg_i2v (synthetic column): original defect: batched_cfg always raises TypeError; converted reproduces it. This is the I2V half; BATCHED_CFG_RECORD.json has both halves.
- i2v_admission_seam: the published bytes refuse the synthetic digest (p0). The single in-process admission existed only in the
  harness, after p0 and t0. The tree and registry were unchanged.

INTAKE_REVIEW.json recomputed every comparison file byte-equal. HASH_BINDING.json binds this evidence to the three tested file
hashes, 23b1dd70 / 22b4dbc5 / f58bd270, which equal the staged files.

The fixture model (37 MB) and the fixture input bins are not committed. FIXTURE.json pins their digests, and the fixture can be
regenerated deterministically (FROZEN_FIXTURE_I2V.py.source).

Not claimed: real I2V weights, GPU, Guest, VAE/CLIP, extra I2V conditioning, LoRA/cache/context with I2V, the name-dependent
variant, the type checks inside the dict, UI/registry, installed runtime, whole node, whole pack.
Counts are unchanged: 128 tested, 15 untested, 4 partial across 147 originals.
