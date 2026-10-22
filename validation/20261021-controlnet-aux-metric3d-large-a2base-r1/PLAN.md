# ControlNet Aux: Metric3D vit-large (candidate r1 + two attempts) on the Aux rev 6 bytes

Authority: MERVYN m_25dd8cc58a, m_7f071d64ca, m_23f574d041 and m_de9d0f771d.
- Option 2, run as (b): two attempts, Depth with a giant2 refusal row, then Normal.
- The weights: MERVYN's pinned fetch of `metric_depth_vit_large_800k.pth` from JUGGHM/Metric3D at 80d2d141 (1,647,972,663 B,
  sha256 15328ffc...; receipt 96ed7ccc...).
- giant2's real file facts come from the same HF tree metadata (no download).
- Nothing here has run.

Why: the Metric3D dropdown (both nodes; the manifest and upstream) offers vit-small, vit-large and vit-giant2. Only
vit-small passes the selection code's 512 MiB `MAX_BYTES`, so vit-large refuses even after approval. The rev 4 report
records this limitation.

## Candidate (1 file, `port.patch`, `STATIC_CHECKS.json`)

`_metric3d/selection.py` (rev 6 bytes 130c4bd7 -> 3b7b8f52), two counted edits:
- MAX_BYTES becomes a 2 GiB per-checkpoint budget for the archive bytes, the declared tensor bytes and the decoded total,
  as for DiffusionEdge. The archive is already read in bounded read_range chunks (`_sealed_asset_read`), so the guest's
  whole-read cap does not apply.
- MAX_PROOF_BYTES keeps the 512 MiB bound for the primitive metadata proof, which covers metadata only.
Only `validate_raw` changes (AST check), and every refusal text is the same. vit-giant2 (5,510,989,187 B) still refuses,
now at selection time, before any read.

## The two attempts (each: launcher r4; 8 GiB = swap; gate 12 GiB; 900 s; tmpfs 1 GiB; CPU; one thread)

Both use the code of `/aux-v2`: the rev 6 tree, a45522ff + the rev 6 stage, as pinned for the DiffusionEdge environments
attempt. `/port` overlays the candidate selection.py. Each attempt is self-contained, with two phases in separate
interpreters.
- MI (`inspect_m3d.py`) inspects vit-large:
  - pins;
  - zip format, and globals through the pack's helper, all default-allowlisted;
  - three identical decodes (BytesIO; after comfy.utils; the original's torch.load);
  - Metric3D's raw facts: keys, state kind and keys, tensor bytes, and the primitive metadata proof, computed exactly as
    the candidate's `validate_raw` re-checks it;
  - the 2 GiB budget.
  It derives the test-only selection: the rev 6 tier A Metric3D selection (51f16bd3: rev 4 plus the torch pin) with
  `resources['vit-large']` from these facts. The candidate's `validate_selection` must accept it. It also writes the
  giant2 variant: giant2's real file facts with vit-large's structure fields. The variant must refuse with "bounded
  archive count".
- MA (`parity_m3d.py`), for this attempt's node with backbone vit-large:
  - its selection's sha256 must equal MI's;
  - control: the pack as published refuses with its exact text;
  - the genuine original (`original_side_m.py`: the rev 4 original side, with the node and backbone as arguments; 4
    counted edits), an ordinary guest and the registered node in process are exactly equal on the rev 4 input (checker
    64x64, resolution 64, fx = fy = 1000);
  - the in-process run reaches the sealed read, and the original's checkpoint path equals the discriminator;
  - the guest without `assets` is refused.

| Attempt | Entry | Rows |
| --- | --- | --- |
| M1 | `m3d_attempt_depth.py` | MI; MA for Metric3D-DepthMapPreprocessor; G: vit-giant2 under the giant2 variant must refuse "Metric3D bounded archive count is unselected" at selection time, with 0 sealed reads and no vendor wrapper import |
| M2 | `m3d_attempt_normal.py` | MI; MA for Metric3D-NormalMapPreprocessor. The M2 intake checks that M2's derived selection hash equals M1's |

Status:
- PASS_M3D: both phases passed.
- FINDING_M3D: vit-large's facts were not clean. This is reported as a finding, and MA does not run.
- FAILED_M3D: anything else.

Expected: well under 900 s each. vit-small took 16-19 s a call in rev 4; I estimate 60-90 s a call for vit-large, with 3
calls per attempt and MI at about 30-40 s. The peak should be about 6 GB: a 1.65 GB sealed payload, plus the decoded
state, plus the model.

Mounts:
- engine, backend, python-env, `/aux-v2`, aux-orig and aux-site are re-hashed equal to PINS_E1;
- `/addict` equals PINS_C1;
- `/weights-m3d` equals MERVYN's receipt;
- `/port`, `/selections` and `/driver` come from the sealed zip.

## After PASS (both attempts)

Stage on top of rev 7. It carries the candidate selection.py (code) plus the report:
- vit-large is tested (scoped) for both nodes;
- the rev 4 limitation changes to "vit-giant2 (5.51 GB) exceeds the 2 GiB budget and refuses at selection time";
- the evidence.
Counts are unchanged: the same two nodes.
