# ControlNet Aux addict-4: Tier A test plan (r1)

Nodes: UniFormer-SemSegPreprocessor, SemSegPreprocessor, Metric3D-DepthMapPreprocessor and Metric3D-NormalMapPreprocessor.
Port r1 over corpus main b6d0482f. One bounded run, which you select and run: launcher r4 with 4 GiB memory = swap, the gate
at cap + 4 GiB, 2 CPUs, no network, uid 1000, read-only mounts, deadline 720 s.

## What runs (`test/tier_a_driver.py`)

1. **Control rows (no stand-in).** The converted pack exactly as it would ship (published v2 + port, approved:false
   selections) runs each of the 4 nodes in process. Each must raise the exact refusal:
   - UniFormer / SemSeg: "UniFormer raw checkpoint metadata/config/vendor/device selection pending";
   - Metric3D: "Metric3D raw checkpoint/config/vendor/device/state-cache selection pending".
   This is the live behaviour until request #21.
2. **Parity rows**, per family, with these steps in order:
   - the genuine pristine upstream (0cd2904) in its own clean interpreter (`test/original_side.py`): the wrapper module's
     own `os.environ` lines and node class, plus `utils.common_annotator_call`, lifted verbatim, and weights read through
     upstream's `custom_hf_download` from the read-only mount;
   - each node through an ordinary GuestSession (sandbox off), with the declared permissions;
   - each node registered in process.

   Input: a 64x64 checker image. UniFormer runs at resolution 64; Metric3D runs with vit-small, fx = fy = 1000 and
   resolution 64. The outputs must be exactly equal (dtype, shape, values) on every route, and the input must be unchanged.
   For Metric3D, depth must differ from normal, and upstream's checkpoint path must equal the selection's discriminator.
3. **Denial rows.** Each guest run is repeated with only ('raw',) and must be refused for assets.

Every parity row carries the label: "tested (scoped) under a test-only approved selection (harness; hash recorded); on live
it refuses ('selection pending') until the selection is approved (request #21)".

## Harness substitutions (test only; never in the pack or v2; hashes in the result)

- **Test pack.** The published v2 + port, with the two test-only approved selections copied over a tmpfs copy
  (`test/selections/`). The checkpoint facts come from AMY's 2026-10-15 restricted inspections, and the node re-checks
  each of them against the real bytes. Each evidence field points to a short document. Pre-flight: the port's own guards
  accept the overlays, and the published selections give the exact control refusals.
- **addict 2.4.0.** Unpacked from a wheel whose hash is verified against the PyPI digest; it is not in profile f65ac4fe.
- **Profile f65ac4fe** (lock b6074c82, 40 wheels). Copied read-only by MERVYN from the live store, verified against the lock,
  and unpacked read-only. The guest gets this site and addict on its PYTHONPATH, standing in for the worker's pack
  dependency root.

## Mounts (all read-only and pinned)

| Mount | Contents |
| --- | --- |
| /runtime/engine | core a2 d1a9259 |
| /overlay/backend | backend a1 894ead3 |
| /python-env | readable venv copy |
| /aux-v2 | published v2 at b6d0482f |
| /port | port r1 |
| /selections | test-only overlays |
| /aux-orig | pristine src/, node_wrappers/, utils.py |
| /aux-site | the unpacked profile |
| /addict | addict 2.4.0 |
| /weights | the 2 checkpoints, copied by MERVYN |
| /driver | the driver files |

## Memory and time

- **Order:** the original side, then the guests, then in-process, so the controller grows last.
- **Peak memory:** AMY's inspections peaked at 1.4-1.6 GB, so I expect a peak of about 2.5-3 GB.
- **Time:** CPU with one thread, for exactness across routes.
  - UniFormer: about 1-2 minutes.
  - Metric3D: upstream runs a fixed-crop ViT-S forward six times, about 2-5 minutes.
  - Hence the 720 s deadline.

## Pass

`PASS_TIER_A` needs all of these:
- 4/4 controls refused exactly;
- 4/4 nodes exact on both routes;
- in-process equals guest;
- 4/4 denials mention assets;
- the input unchanged;
- Metric3D depth differs from normal;
- the discriminator equal.

Anything else gives `FAILED_TIER_A`, and the result records each failure.
