# ControlNet Aux: DiffusionEdge packet r2 (port r2 + Tier P parity + fail-closed rows)

Base: corpus main d5228370, from NED's own clone. Authority: MERVYN m_39ab2acbd7 and m_55b4dfff83, after Tier I passed
(m_698147d79e; intake CLEAN, no findings). Source only; nothing in this packet has run.

## Port r2 = port r1 + the per-archive restricted-globals proof

| File | Change vs r1 |
| --- | --- |
| `_restricted_legacy_globals.py` (new, shared) | A legacy (non-zip) archive is decoded through BytesIO, so torch never takes the tar route; it loads exactly five pickles with the weights_only unpickler (magic, protocol, sys_info, object, storage keys). The module scans those five with torch's own `get_globals_in_pkl` and requires the found set to equal the pinned list, all in the default allowlist. It is fail-closed: zip payloads are refused, the scan is bounded to 64 MiB, and any error is one refusal. AMY's `_restricted_globals.py` (zip) stays byte-identical (55e55d89), so the tested UniFormer and Metric3D rows are unaffected. |
| `_diffusionedge/selection.py` | `validate_selection`, before any vendor import or asset read (the M1 lesson), now also requires: `torch_runtime_version`; and for every resource, `archive_format` (zip or legacy) and `pickle_globals` (sorted, unique, non-empty). `restricted_checkpoint` refuses a different torch build (the proofs use private torch APIs: L4), then runs the matching proof on the exact bytes, before `torch.load`. |

Unchanged from r1:
- data.py (the albumentations import dropped);
- source-closure.json (data.py's record);
- the chunked sealed reads;
- the single-decode release;
- secure-nodes.json (`assets`).

## Tier P (one bounded attempt; launcher r4, 8 GiB = swap, gate 12 GiB, 900 s, tmpfs 1 GiB, CPU, one thread)

Expected peak: about 5 GB. The converted guest holds the 2.1 GB of sealed bytes, then decodes the 1.19 GB main
checkpoint while the model is built. Tier I measured 2.9 GB for the inspection alone.

Rows:
- **C, control:** the pack as it would ship (published selection, approved:false) refuses in process with its exact text.
- **P, parity:** under the test-only approved selection, built from the Tier I facts (`test-p/SELECTIONS.json`). The input is
  the 64x64 fixture at resolution 320 (one slide window), patch_batch_size 4, environment indoor. The genuine original
  runs in its own interpreter, then an ordinary guest, then the registered node in process. All comparisons are exact.
  - Original side: the albumentations stand-in (option (a), approved) and the yacs test root (#25).
  - install_deps is a no-op: upstream pip-installs scikit-learn at run time, a refused technique, and sklearn is not used.
  - Weights come through upstream's own lookups. LPIPS vgg.pth is found relative to the working directory.
  - Nothing is downloaded, and the run checks that.
- **D, denial:** the guest repeated with only `raw` must be refused for assets. albumentations is blocked on the
  converted side, in the guest and in process.
- **F, fail closed** (exact refusal texts in `test-p/SELECTIONS.json`):
  - F1: vgg16 without pickle_globals. Refused in validate_selection, before any read or import.
  - F2: vgg16 pinned as zip. The zip proof refuses.
  - F3: a wrong lpips global list. The legacy proof refuses.
  - F4: built in the harness. A legacy copy of lpips plus one int64 tensor adds one unpinned global, torch.LongStorage.
    The legacy proof refuses before decode. U4 checks the same bytes through the helper directly, and U0 shows the
    helper accepting the real lpips.
  - F5: a wrong torch pin. Refused before the proof.

## Label (provisional; MERVYN to set)

tested (scoped) under a test-only approved selection and a test-env yacs 0.1.8 (harness; hashes recorded). Live needs:
- yacs in the Aux profile (#25);
- declarable URL and repo-file weights (vgg16, swin_b, lpips);
- an approved production selection.
