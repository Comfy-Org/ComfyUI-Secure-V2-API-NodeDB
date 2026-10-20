# WAN sampler experimental/feta + batched_cfg r3 validation (publication r8)

Staged sampler runtime (`WanVideoSampler`, `WanVideoSamplerFromSettings`, `WanVideoSamplerv2` share it). The rows stay partial (staged):
- experimental/feta: closed by reviewed normalization, not passed;
- batched_cfg: "original defect: batched_cfg always raises TypeError; converted reproduces it" (original nodes_sampler.py:1657-1663; T2V half; error parity, not a computation pass).

One selected attempt (m_ee23614b11) of packet wan-feta-batched-slice-r3 (1fc9babe, CONFIG af727a38) ran as two sequential
bounded Linux containers on WSL CPU (image e48accf7, Python 3.13.7, torch 2.8.0+cu128). Each was uid/gid 1000 with no
capabilities, no network, a read-only root and memory = swap = 6 GiB. It compared the genuine original nodes against the
registered converted nodes on the default-SDK in-process route (SDK 0d6ec97e, Core 0.37.0). Both used the trained 1.3B T2V
bf16 checkpoint bcb3c10a. The packet and all six material trees were re-verified before each role.

COMPARISON 61ec2016 (comparator rev4, exact):
- experimental_feta: 116/118 checks true. The two false checks are x3b's exact-message checks: a hash-randomized set-literal
  order. They are equal under the reviewed normalization and remain recorded (REVIEWED_NORMALIZATION.json).
- batched_cfg: 35/35 (BATCHED_CFG_RECORD.json).

INTAKE_REVIEW.json recomputed all three comparison files byte-equal from comparator_inputs/. Attempt 1 (m_435e52ee89) stopped
at preflight and is kept (ATTEMPT1_PREFLIGHT_RECEIPT.json). The staged v2 tree equals the tested candidate tree byte for
byte, except the report. Only v2/wan_workflow_sampler_runtime.py (51b17ea9) and v2/SECURE_CONVERSION.md change in the corpus;
v2/secure-nodes.json is unchanged.

Not claimed: Guest, GPU, I2V/control conditioning, FromSettings/v2 runs with these inputs, full-size domains,
UI/registry, installed runtime, whole node, whole pack.
Counts are unchanged: 128 tested, 15 untested, 4 partial across 147 originals.
