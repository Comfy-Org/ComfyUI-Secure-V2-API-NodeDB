# APZmedia Naming Tools — Secure Nodes V2 (12 of 14 nodes)

Upstream: <https://github.com/APZmedia/ComfyUI-APZmedia-naming-tools> (the project
metadata URL `ComfyUI-APZmedia-cleanName-from-string` redirects there), pinned
commit `b4f59b4fee28769150da3137b07c20053eb10900`, release `xb4f59b4`. The 24
tracked original files are preserved byte for byte. They include the tracked
bytecode file `nodes/__pycache__/APZgeneratePathNode.cpython-311.pyc`. The selected
CPython 3.13 ignores that file because its cache tag does not match; it is kept
only as pristine data.

## Node scope

The upstream package registers 14 nodes. This conversion registers **12**. The
two remaining original nodes are unregistered and formally
**REFUSED_CURRENT_RELEASE** under MERVYN's 2026-10-20 release disposition.
The reasons below concern the inspected qualified SDK/Host path for this
release, not permanent impossibility or API absence in every repository.

| Node | Status | Finite purposes (cases; original errors) |
| --- | --- | --- |
| `CleanFileNameNode` | tested (original/default SDK) | 7: defaults, accented/CJK text with CRLF, empty replacement fallback, prefix + truncation, `.` replacement; 2 original `re.PatternError`s (`*` replacement, empty invalid set) |
| `APZmediaGenerateFilePath` | tested | 10: defaults, each toggle excluded, all excluded, forward absolute reset, backslash, `Auto` on the native platform |
| `APZmediaStandardFilenameBuilder` | tested | 8: defaults, Unicode fields, all excluded, empty delimiter, each toggle excluded |
| `APZmediaReadWidget` | tested | 2: default, multi-line Unicode literal |
| `APZmediaDictionaryReplace` | tested, scalar/JSON wildcard values only | 6: defaults, sequential overlapping counts, malformed lines and empty keys, escaped quotes, a number input, a JSON container input |
| `APZmediaTextToHash` | tested, scalar/JSON wildcard values only | 8: defaults, Unicode, number, container, zero/negative/over-length slices; 1 original `UnicodeEncodeError` (lone surrogate) |
| `APZmediaVFXFilename` | tested | 9: defaults, Unicode, all excluded, empty delimiter, each toggle excluded |
| `APZmediaAdFilename` | tested | 10: same families, six toggles |
| `APZmediaFashionEditorialFilename` | tested | 9: same families, five toggles |
| `APZmediaFashionEcomFilename` | tested | 9: same families, five toggles |
| `APZmediaEcomFilename` | tested | 9: same families, five toggles |
| `APZmediaStringStripper` | tested | 9: Simple and Regex modes, selected order, duplicate slots, mismatch/no-delimiter fallbacks, named and optional groups, invalid-regex fallback; 1 original `ValueError` (`²`.isdigit) |
| `APZmediaLoadImageWithFilename` | **REFUSED_CURRENT_RELEASE** (unregistered) | The full upload/catalogue/annotated-input membership contract has no implemented trusted schema binding in the inspected release path. Unregistered decode helpers do not establish the whole-node purpose. See the reopening contract below. |
| `APZmediaCycleInt` | **REFUSED_CURRENT_RELEASE** (unregistered) | The inspected release path has no implemented authenticated Core-node-generation scalar owner matching the original immediate mutation and cached-instance lifetime. See the reopening contract below. |

## Current-release purpose dispositions

Root owns these two dispositions. Their basis is the inspected qualified
SDK `f1a73e4f160e70862f51abdddbb9268e2ce94dd96e18455a79e42307a443f91c` and its
actual Host contracts. No new algorithm, decoder, Guest, catalogue, browser or
service test credit is assigned. Both original IDs remain unregistered; no
stub, replacement schema or implementation is added. A trusted implementation
can reopen either purpose under a separately reviewed contract.

### `APZmediaCycleInt` — REFUSED_CURRENT_RELEASE

**Purpose:** Advance an integer immediately on the same Core-cached node instance across executions, with native initialization, range changes, direction and wraparound semantics.

**Current contract reason (UNIMPLEMENTED_TRUSTED_NODE_INSTANCE_LIFETIME_CONTRACT):** The original initializes self._current on object creation, mutates it in get_value before returning and returns NaN from IS_CHANGED to force execution. A later node or prompt failure does not undo that mutation. The inspected qualified API has no implemented authenticated Core-node-generation scalar owner matching that lifetime and commit point.

**Rejected substitutions:**

- Guest class/module globals or process-global counters

- Persistent pack storage keyed by caller-supplied node/workflow strings

- Committing only the last successful node/prompt output

- Resetting the counter on each Guest dispatch


**Minimum reopening contract:** A trusted adapter binds actual cached Core node instance/generation, class/source/runtime and rights; a bounded per-node operation linearizes read/advance before return. Reset/retirement follows the actual selected Core object-cache policy. It must be separate from previous-success commit semantics and expose no caller-chosen owner selector.

**Qualification required after implementation:** Compare first/subsequent increment/decrement, swapped/range-changed bounds, step/wraparound, separate node instances, pre-return mutation surviving downstream failure and actual cache disposal; verify isolated callers cannot select another owner's state.

### `APZmediaLoadImageWithFilename` — REFUSED_CURRENT_RELEASE

**Purpose:** Preserve the original image-upload combo, refreshed top-level MIME-filtered input choices, annotated-input lookup/membership and filename outputs as well as image decoding.

**Current contract reason (UNIMPLEMENTED_MANAGED_INPUT_CATALOGUE_SCHEMA_BINDING):** INPUT_TYPES enumerates and MIME-filters the current Core input directory for its upload combo. Execution, fingerprint and validation use annotated input lookup. io.Combo.Input metadata and existing asset read/list APIs do not themselves supply an implemented admitted-pack/tenant catalogue-to-schema hydration and membership binding in the inspected path. An independently working decoder is insufficient for this full node contract.

**Rejected substitutions:**

- An empty or frozen guessed combo advertised as a live catalogue

- Replacing the image-upload combo with an unrelated STRING input

- Ambient host-directory access or an arbitrary authenticated remote URL

- Treating decoder comparisons as catalogue, upload or graph acceptance


**Minimum reopening contract:** A trusted definition/input adapter binds managed catalogue choices, upload/refresh and exact membership validation to the admitted pack and current caller, preserving the supported relative/annotated-input names and the original four output semantics. RemoteOptions alone does not authorize arbitrary backend fetches.

**Qualification required after implementation:** Exercise actual definition refresh/upload/membership plus valid managed PNG/JPEG/EXIF/multi-frame cases, filename outputs, fingerprints and original error behavior through real default SDK and required Guest. Unsupported annotated-path domains must retain explicit purpose-level reasons.

Unregistered public asset/decode helpers remain available for separately qualified managed-image purposes; no helper test or whole-node acceptance is inferred here.

These release decisions are documentation only. Canonical service status
remains with its owner; this report neither writes that status nor certifies
whole-pack runtime, dependency-profile admission or deployed adoption.

The full original package (all 14 nodes imported normally) and the 12 actual
registered default-SDK nodes ran **96 fixed cases**. **92 returned results and 4
reproduced the original errors exactly** (module, type and message). The
following were compared exactly for every case:

- typed values, including UTF-8 byte counts and hashes;
- console output and warnings;
- inputs left unmutated;
- the 94 declared fingerprints.

All 12 explicit schema records match: id, display name, category, input order,
every declared original attribute, normalized combo options, outputs, output
names and list/output-node flags. The checker made 791 checks, and all six
coherent wrong-data controls were detected. These purposes are not public
graph, Guest or browser execution.

## Conversion notes

- Each node's original algorithm module is copied byte for byte into
  `v2/algorithms/`. `v2/naming_nodes.py` adds only V2 schemas and `execute`, and
  `fingerprint_inputs` delegates to the original `IS_CHANGED`.
- The `*` wildcard inputs of DictionaryReplace and TextToHash use `io.AnyType`
  with the `raw` permission. Only scalar and JSON values are qualified.
  Tensors and opaque engine objects remain unqualified.
- Unidecode: the tests used the genuine PyPI wheel `Unidecode-1.4.0-py3-none-any.whl`
  (sha256 `c3c7606c27503ad8d501270406e345ddb480a7b5f38827eafe4fa82a137f0021`),
  plainly extracted into a separately owned 200-file private prefix. The
  qualified shared site was not changed.
  - `v2/pyproject.toml` declares `Unidecode==1.4.0` and Python `>=3.13,<3.14`.
  - `v2/requirements.txt` is unchanged.
  - Admitting that dependency profile to a deployment is a separate step.
- No production input-size caps were added; the original has none. The test
  harness only limited its own fixtures.

## Authority and bounds

All 12 nodes declare `SDK_REFS=False`. DictionaryReplace and TextToHash declare
`raw`; the other ten declare no permissions. There is no web directory, backend
route, model weight or validation method.

## Actual evidence and limitations

One selected native attempt, `m_622dd4704e`, ran on:

- Python 3.13.14 and `comfy_api` 0.42.0;
- Core `44564d0279c275eef52b11750a9d76349f4e7a88`;
- backend `59bd3e1acba6520bb32717ad03833f6ab2967ecc`;
- the private Unidecode prefix (receipt `d3614d63267af0d2f3a71981d4f74b46684dd6553183bccb927ca2b4988b4dc2`).

The run:

- There were three serial stages (original, converted, comparison), with no
  automatic retry and exit status 0.
- It took **4.406 s** under the driver and 4.47 s in the owner's real time. Peak
  owner RSS was **315,555,840 bytes**; this is an observation, not a quota.
- All six cleanup rows confirmed reaping and process-group absence. The three
  worker groups were also observed absent twice by an independent check.
- Every environment map was unchanged:
  - 84,917 installed-site files, 96 component files, 141 SDK files, 1,384 Core
    files and 83 backend files;
  - the 55-file packet;
  - the 200-file Unidecode prefix.

The first independent live observer ran only after the 4.4-second job had
ended. Owner and timing PIDs were therefore **not independently captured**.
Worker IDs come from the frozen driver's cleanup records. No broader live
cleanup claim is made.

Evidence and reviews:

- The evidence archive is 17,781,277 bytes, SHA-256
  `b6f20bf2a1cf2ed2f17264c74472c2c578ce8e6878154b1409a009e3ada95f65`.
- The independent receipt is `af1d8bf64d6b996ee7f57d4c61f7d204c9a46d23e9a0c2997ba736a8714ec477`.
- The independent data review re-derived 327 checks from the returned records
  without importing SDK, Core, APZ or Unidecode code.
- The archive review made 35 checks. The frozen packet and staged source were
  byte-identical, the argv bound every input, the maps were unchanged, and the
  prefix matched exactly.
- Compact records are in `validation/20261020-apz12-native-r1`; raw archives stay
  outside Git.

## Generation

The normal generated manifest is retained byte for byte:
`b962c4e3749b1ddf6be96fc1ddd804f0a04c3fc507b3f0290e08555f111fa17b`.

It was produced by the official generator under selection
`m_cc254da0da`:

- the generator is the accepted tool plus one APZ profile line;
- packpatch pair generate and bundle, plus pristine pair and ZIP replays, ran
  in five serial stages;
- the evidence archive is `7289ddc4e0004f8ed300d48981e44a5bcc6a86cc576a8944e7b35bc870d06a2e`;
- compact generation records are in `validation/20261020-apz12-generation-r1`,
  including one intake-reader check that was corrected data-only (no rerun).

After generation, only non-runtime files were added: this report and the API
declaration contracts `comfy-api.pyi` (`f2d067f0…`) and `comfy-api.d.ts`
(`bb40d8a1…`). The two declarations are the existing genuine contract for the
same qualified f1 profile, copied byte for byte from the verified RandomSeed
contract retained for Swap; no stub generator was run for this pack.
Canonical pair and bundle regeneration, plus both pristine file-only replays,
preserve all original and converted files and Unix modes.

**Whole-pack conversion (12 of 14), runtime and dependency-profile admission,
registry adoption, public graph execution, Guest/gVisor, browser UI and
deployed-service acceptance are not claimed.** Source proposals for the two
unconverted nodes exist outside this pack and are unimplemented.
