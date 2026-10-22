# ControlNet Aux: review follow-ups candidate r3 + combined tier C (test c1)

Base: corpus main 3583e7bd (Aux rev 5 published, PR #68), from NED's own clone.
Authority: MERVYN m_46a5cedbd5, m_50addc89cd, m_1f34ae6ca4, m_9c3a1c4359 and m_c968452354. In short:
- L4 is code;
- MERVYN routes AMY's zip helper;
- Low-1, Low-3 and Low-4 are folded in;
- Low-2 is included;
- the Low-5 rows go into the test plan;
- one combined attempt at 8 GiB.
Nothing here has run. The static checks are in `STATIC_CHECKS.json`.

## Changes (7 files, `port.patch`)

| Item | File | Change |
| --- | --- | --- |
| M1 | `_uniformer/selection.py`, `_metric3d/selection.py` | `validate_selection` refuses an approved selection whose `resource.pickle_globals` is missing, empty, unsorted or duplicated. It runs before any vendor import, config evaluation or archive read. |
| L4 + Low-3 | the same two files | The selection pins `torch_runtime_version` (presence is checked in `validate_selection`). The new `require_selected_torch` compares it with the running build before the sealed read (`selected_archive`) and again at decode (`load_raw_checkpoint`). |
| L1–L3 (Low-1 for all callers) | `_restricted_globals.py` (AMY's zip helper; MERVYN routes it) | L1: the payload must start with `PK\x03\x04`, the only bytes for which torch takes the zip route. L2: `data.pkl` must be STORED, with compressed size equal to size, and at most 64 MiB. L3: any open, read or scan error is one clean refusal. `require_default_allowlisted` is unchanged. |
| Low-2 | `_restricted_legacy_globals.py` | Only the first 64 MiB is scanned, so the bound also holds inside a single pickle. A pickle that runs past it is a refusal. |
| Low-1 | `_diffusionedge/selection.py` | Before the dispatch: if the archive's first four bytes disagree with the pinned `archive_format`, the decode is refused (the reviewer's check). |
| Low-3 | the same | `require_selected_torch` runs at the start of `sealed_buffers`, before the 2.1 GB read and the model build, and again at each decode. |
| Low-4 | the same | `construction()` clears the buffers when it ends, after success, a refusal, or a refused nested construction. |
| nits | the same | The duplicate `import torch` and `record=` in `restricted_checkpoint` are removed. |
| L5 | `tests/test_uniformer_native_registered.py`, `tests/test_metric3d_native_registered.py` (NOT_RUN gates) | They assert the pinned torch build, the pinned default-allowlisted globals and `{raw, assets, models.download}`, instead of "no safe globals" and `{raw, assets}`. |

Unchanged:
- the published selections (approved:false);
- `secure-nodes.json`;
- the source-closure files (no record pins these files).
Every other top-level function in the changed files is unchanged (checked with an AST comparison).

## Refusal texts

New:
- UniFormer and Metric3D:
  - "<family> restricted decode torch runtime version is unselected";
  - "<family> restricted decode pinned pickle globals are unselected";
  - "<family> restricted decode torch runtime differs from the selected version".
- DiffusionEdge: "DiffusionEdge restricted decode archive format differs from the selected format".
- The zip helper:
  - "restricted torch archive data.pkl record is not stored or exceeds the scan bound";
  - "restricted decode could not scan data.pkl".

Kept: every existing text. The DiffusionEdge torch-mismatch text moves into `require_selected_torch`, unchanged.

## Compatibility (static; `ZIP_FACTS.json`, `LEGACY_FACTS.json`)

- The four real zip checkpoints start with `PK\x03\x04`. Each holds one STORED `archive/data.pkl` of 53–487 KB.
- The two legacy files start with `80 02`. Their five pickles end at 3,449 B (vgg16) and 1,361 B (lpips). The GLOBAL sets,
  from stdlib opcode decoding, equal the pinned lists.
- The pinned formats match the leading bytes for all four DiffusionEdge files.

## Combined tier C (one bounded attempt; launcher r4; 8 GiB = swap; gate 12 GiB; 900 s; tmpfs 1 GiB; CPU; one thread)

The entry `combined_driver.py` runs three phases, each in its own interpreter and one after the other, then prints one
result line. The status is PASS_COMBINED only if every phase passes.

Phase A runs UniFormer, SemSeg and Metric3D Depth/Normal, using the rev 4 harness on the candidate bytes:
- C: the pack as published refuses each node with its exact text.
- U/M: the original (its own interpreter), an ordinary guest and the registered node in process are exactly equal. The
  in-process run must reach the sealed read; this is the positive control for the read counter.
- D: the guest without `assets` is refused.
- FA1–FA3, per family, in process:
  - FA1: no `pickle_globals`;
  - FA2: no torch pin;
  - FA3: a wrong torch pin.
  Each must refuse with its exact text and make no sealed read. FA1 and FA2 must refuse before the vendor wrapper is
  imported.

Phase P runs DiffusionEdge, using the rev 5 harness on the candidate bytes:
- C, P (parity) and D as in rev 5. The in-process run makes exactly 4 sealed reads, and the buffers are empty after
  construction (Low-4).
- Refused at selection time, with no read:
  - F1: vgg16 without pickle_globals;
  - F7: no torch pin (Low-5c);
  - F8: archive_format 'tar' (Low-5c).
- Refused before any read (Low-3): F5, a wrong torch pin.
- Refused at decode, after the 4 reads, with the buffers emptied (Low-4):
  - F2: legacy vgg16 pinned as zip. This is now refused by the Low-1 format check.
  - F6: zip swin_b pinned as legacy (Low-5a).
  - F3: a wrong lpips list.
  - F4: an extra unpinned global (harness-built).
  - F9: a host-registered global, `numpy.dtype`, pinned exactly (Low-5b; harness-built). Its precondition is checked:
    ComfyUI registers the global, and torch's default allowlist does not contain it.
- U0 and U4 as in rev 5.

Phase U runs the helper unit rows, with no model forward:
- UZ0 and UL0: the six real archives are accepted with their pins.
- UZ1 (L1): the polyglot, a legacy lpips stream with a benign zip appended. Python's zipfile opens it and main's helper
  accepts it (recorded as evidence). The candidate refuses it.
- UZ2a (L2): a DEFLATED `data.pkl` is refused.
- UZ2b (L2): a STORED `data.pkl` over 64 MiB is refused.
- UZ3 (L3): a truncated `data.pkl` gives one clean refusal.
- UZ4 (Low-5b, zip) and UL2 (Low-5b, legacy): a host-registered global pinned exactly is refused.
- UL1 (Low-2, MERVYN's row): a synthetic legacy pickle over the 64 MiB cap is refused.
- UL3 (Low-5a): a zip payload given to the legacy helper is refused.

Expected time is about 400 s: rev 4 Tier A took 180 s and rev 5 Tier P 126 s. Expected peak is about 6.2 GB (rev 5 Tier P
reached 6.03 GB). Each phase's tmpfs copies are removed before the next phase starts.

Harness substitutions are as in rev 4 and rev 5 (hashes in `test-c/SELECTIONS.json`):
- the test-only approved selections. The rev 4 ones gain only `torch_runtime_version` "2.8.0+cu128". The rev 5 one is
  unchanged;
- the addict and yacs test roots;
- the albumentations stand-in on the original side, and the blocker on the converted side;
- an install_deps no-op on the DiffusionEdge original side.

The original-side scripts, the fixture, the stand-in and the blocker are byte copies of what ran in rev 4 and rev 5.

## Report notes for the staging (after a PASS)

- Revision 6 (review follow-ups): M1, L1–L5 and Low-1 to Low-5 are done. Nothing is open from either review.
- Out of scope, as MERVYN decided: the Metric3D NOT_RUN test still plans vit-large and vit-giant2, which exceed the 512 MiB
  read limit (the revision 4 limitation).
