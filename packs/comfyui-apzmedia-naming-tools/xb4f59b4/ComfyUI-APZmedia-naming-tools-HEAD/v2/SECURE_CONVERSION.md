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
two remaining original nodes are **not converted**. Each needs a host contract
that the published SDK does not have yet.

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
| `APZmediaLoadImageWithFilename` | **not converted** | Needs a host-managed image catalogue: the original lists the input folder's top-level images (by Core MIME type) every time Core asks for the node definition, and a V2 schema is sealed. Pixel/mask/frame decode helpers exist in `image_decode.py` and `image_assets.py` but are unregistered. |
| `APZmediaCycleInt` | **not converted** | Needs host-owned per-node-instance integer state that commits immediately. The original advances `self._current` on Core's cached node object; static, global or persistent storage would not be equivalent. |

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
