# ControlNet Aux: DiffusionEdge urban and natrual (inspection + parity, one attempt) on the Aux rev 6 bytes

Authority: MERVYN m_25dd8cc58a and m_7a89f9234f.
- The work: inspect both environments, add a parity row for each, run it as one 8 GiB attempt, and stage it on top of
  rev 6.
- The weights: MERVYN fetched both checkpoints, one pinned attempt each, sha256 and size verified against Hugging Face's
  tree metadata for hr16/Diffusion-Edge at 401c6cd4. Receipt: inputs/COPIED_SHA256.txt (94e1d1b9...).
- Nothing here has run.

Why: the node's environment dropdown offers indoor, urban and natrual. Only indoor was inspected and tested (rev 5 and
rev 6), so urban and natrual refuse even after approval. The rev 6 report lists this as a residual: whether they fit the
2 GiB budget was unknown.

| Environment | File | Bytes | sha256 | Budget (main + 905,095,377 B of auxiliaries <= 2 GiB) |
| --- | --- | --- | --- | --- |
| urban | `diffusion_edge_urban.pt` | 1,192,128,970 | 9b0dc9df... | 2,097,224,347 B: fits |
| natrual | `diffusion_edge_natrual.pt` | 1,192,112,522 | ad544682... | 2,097,207,899 B: fits |

## The attempt (launcher r4; 8 GiB = swap; gate 12 GiB; 900 s; tmpfs 1 GiB; CPU; one thread)

The code is the Aux rev 6 bytes: `/aux-v2` is corpus main a45522ff v2 with the rev 6 stage (d9a586aa) applied. No pack code
changes; this attempt only adds evidence. The entry `env_driver.py` runs these phases, each in its own interpreter:

- EI (`inspect_envs.py`) inspects each main checkpoint with the indoor Tier I steps:
  - pins: bytes and sha256 against the sealed `RESOURCE_PINS.json`;
  - format from the leading bytes;
  - globals through the pack's own helper for that format, all in torch's default allowlist;
  - three decodes, each giving raw_structure, tensor bytes and a tensor digest, which must be identical: the restricted
    BytesIO decode before any host import, the same after comfy.utils registers its safe globals, and the original's own
    `torch.load(path)`;
  - the 2 GiB budget.
  For each clean environment, EI derives the test-only approved selection: the rev 5 indoor test-only selection
  (`selections/approved`, dd2c68e4...) plus `environments.<env>`. Its main comes from these facts, with two short
  evidence documents (sha256 recorded). The three auxiliaries are copied from indoor, since they are the same pinned
  files. The pack's own `validate_selection` must accept it. Its sha256 and env entries are in the result.
- EP (`parity_env.py ENV SHA`) runs for urban, then natrual:
  - it uses the selection only if its sha256 equals EI's;
  - control: the pack as published refuses with its exact text;
  - the genuine original (`original_side_e.py`, the rev 5 original side with the environment as an argument; 4 counted
    edits), an ordinary guest and the registered node in process: exactly equal on the rev 5 input (the 64x64 fixture at
    resolution 320, one window, patch_batch_size 4);
  - the in-process run makes exactly 4 sealed reads, and the buffers are empty after the construction;
  - the guest without `assets` is refused.

Status:
- PASS_ENVS: EI passed and both environments passed.
- FINDING_ENVS: an environment's facts were not clean (a finding about that checkpoint, not a harness failure).
- FAILED_ENVS: anything else.

Expected: about 300 s and a peak of about 6 GB (rev 5 and rev 6 Tier P: 6.03 and 6.07 GB).

Mounts:
- engine, backend, python-env, aux-orig, aux-site, yacs and `/weights-p` are re-hashed against the rev 6 PINS_C1;
- `/aux-v2` is new (the rev 6 tree);
- `/weights-env` holds MERVYN's two files;
- `/selections` and `/driver` come from the sealed zip.

## After a PASS

Stage Aux rev 7 on top of rev 6. DiffusionEdge becomes tested for all three environments, and the rev 6 residual
("urban and natrual not inspected") closes. The evidence includes the derived selection's environment facts. The
published selection stays approved:false (#21), and the live note is unchanged. Counts are unchanged: it is the same node.
