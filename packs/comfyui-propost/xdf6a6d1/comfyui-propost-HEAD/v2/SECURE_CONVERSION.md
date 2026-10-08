<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-propost

## Provenance

Upstream https://github.com/digitaljohn/comfyui-propost at exact commit
`df6a6d122498f57ad7195d58e07701a501c9dcb6` (2024-12-25), release
`xdf6a6d1`. All 25 tracked pristine blobs were captured and independently
compared with that Git commit; their SHA-256 inventory is tests/pristine-sha256.json.
MIT LICENSE and bundled examples are retained byte-identically. Selection:
historical August 4 registry download rank 101 / 155071 downloads; this is not a
current trending claim. HARVEY's frozen 193-pack attribution suggests 492
sole-attributed-blocker graphs / 133 structures conditionally; these are static
potential gains, not workflow execution results or an exhaustive source census.

## Backend node dispositions

Actual pristine import with a confined recording folder_paths facade discovers
exactly these five IDs. The facade supplies only temporary model/catalogue paths;
image processing, random generation, Pillow/OpenCV, Torch and colour algorithms
are real. No host ComfyUI import or pristine production installation is certified.

| Exact backend ID | Disposition | Registered in V2 | Behavior evidence |
| --- | --- | --- | --- |
| `ProPostVignette` | supported | yes | Pixel, batch, dtype, zero-intensity and channel comparisons; actual guest and outer IMAGE. |
| `ProPostFilmGrain` | supported | yes | All four stocks, grayscale/RGB, seed, scale and sharpen comparisons; fresh guests and outer IMAGE. |
| `ProPostRadialBlur` | supported | yes | Pinned radial mask and Gaussian blending; actual guest and outer IMAGE. |
| `ProPostDepthMapBlur` | supported | yes | Depth normalization/mask and blur; native float64 error preserved; actual guest and outer IMAGE+MASK. |
| `ProPostApplyLUT` | supported | yes | Real colour 1D/3D/domain/log/strength interpolation; bounded brokered cube reads; actual guest and outer IMAGE. |

These dispositions cover the bounded CPU behavior tested here. They do not
certify a deployed cloud runtime, all LiteGraph workflows, or GPU execution.

## Frontend and ancillary scope

No upstream WEB_DIRECTORY, frontend extensions, JavaScript graph nodes or routes.
The LUT schema retains the lut_name COMBO, refreshed through the trusted closed
catalogue /secure-nodes/assets/input?kind=lut. Ordinary schema input names/order,
numeric defaults/options, categories and declared IMAGE/MASK outputs are retained.

## Verification results

The repeatable focused command from the isolated pack-db worktree is:

```sh
COMFY_CORE_ROOT=/Users/ben/comfy/ComfyUI-secure-nodes PYTHONDONTWRITEBYTECODE=1 /tmp/many-oct6-propost-venv/bin/python -m pytest -p no:cacheprovider --confcutdir=packs/comfyui-propost/xdf6a6d1/comfyui-propost-HEAD/v2 --rootdir=packs/comfyui-propost/xdf6a6d1/comfyui-propost-HEAD/v2 -q packs/comfyui-propost/xdf6a6d1/comfyui-propost-HEAD/v2/tests/test_propost_secure_conversion.py
```

Existing observed preflight: 73 compute/resource/parser cases passed after
explicitly testing the pristine OpenCV CV_64F color-conversion failure as a
matching negative branch. The initial test incorrectly assumed all float64
depth inputs succeed; its failure is retained in
outputs/many-oct6-propost-compute-preflight.log. This was an oracle correction,
not a computation fix. The actual-guest/outer gate passed separately
(1 selected case, 74 deselected; 12.31s) in
outputs/many-oct6-propost-guest-preflight-4.log.

That guest gate exercises all five nodes in two separate processes with original
and recreated pack filesystems, raw denial for each, assets denial for the LUT,
logical traversal/absolute/backslash/missing-file denials, and production outer
execution of all IMAGE outputs plus the depth MASK. Trusted SDK providers are
in-process. This is actual subprocess guest execution, not gVisor or deployment
certification. No model or algorithm inference doubles exist in this pack.

The first complete artifact/behavior gate observed **75 passed in 17.12s**,
including manifest, exact reconstruction and pinned-file inventory. Its log is
outputs/many-oct6-propost-final-1.log. This report then records that observation;
the regenerated final bytes are gated twice and frozen in the coordinator handoff.
Final complete gate results and final hashes are recorded in the coordinator
handoff after generating the report/manifest/pair. Do not equate case count with
distinct certified workflows or nodes. Initial scratch dependency failures
(packaging, torch, torchgen missing from the nested isolated environment) are
preserved in guest-preflight.log and guest-preflight-{2,3}.log; dependencies were provisioned only in the
owned scratch environment. Existing development environments were not changed.

## Authority and resource bounds

SDK_REFS=False; raw capability for bounded CPU tensor computation, and assets
additionally for LUT. No ambient host ComfyUI modules, filesystem paths, network,
downloads, subprocesses, runtime installs or global RNG mutation.

BHWC floating inputs: at most 64 batch, 4096 per axis, four channels and 8388608
elements; finite input required. Projected workspace at most 512 MiB before
algorithms, including blur arrays and scaled/fine-grain intermediate buffers.
Blur steps at most 32, kernel at most 256, mask kernel 127, sharpen iterations 10.
Seed remains a 64-bit integer; projected scale buffers are checked before PIL
allocation. Invalid native algorithm inputs can still raise pinned native errors.

Cube input is a confined logical .cube name, broker size/read_range at most 8 MiB;
no physical path leaves the broker. Table bounds: 1D up to 65536 entries, 3D up to
65 per axis, finite RGB/domain and exact bounded table layout. Malformed unsafe
tables fail before colour processing. Data-only cube interpretation executes no
file-supplied code. Dependency colour-science 0.4.6 is used for the original LUT
objects/interpolation, not a recording replacement.

## Persistence and deliberate differences

Image/control state travels through workflow inputs. LUTs are user-managed input
artifacts, not mutable pack-local files. Existing legacy models/luts cube files
must be provisioned into the managed input catalogue with their logical names;
this conversion does not silently copy an unrestricted host library or claim
cloud storage migration/durability/isolation. Input artifact tenancy and retention
remain the deployment's managed-asset contract; no cloud backing was observed.

The film grain mask cache contains entirely reproducible seed-derived scratch
data. It is recomputed per call instead of reading/writing host temporary files;
pixel comparisons and recreated guests verify equivalence. It is not a reusable
authored library and does not require durable KV. Seeded Random instances preserve
the original draw sequence without reseeding shared process RNG. The zero-intensity
Vignette's unwrapped upstream tensor is normalized into its declared single-output
container; its pixels remain unchanged.

## Release integrity and runtime dependencies

Canonical stubs come from central KJ V2:
d.ts SHA 4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3;
pyi SHA 50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78.
Python >=3.13,<3.14 is explicit. The manifest seals all five nodes, raw/assets
permissions and schemas; complete pristine-to-V2 reconstruction is checked.

Requires the coordinator's backend closed-catalogue schema hydration and LUT kind:
packdb.py calls remote_catalogue_options on known local selector routes;
webassets.py uses the same confined live listing as selector refresh. Unknown
remote routes/static dropdowns retain their static validation. There is no
unrestricted URL fetch or validation bypass. The coordinator's admission gate
passed 36 checks twice, including real Crystools manifest proxies through the
entire core validate_inputs function, live removal, traversal/symlink escapes and
ordinary dropdown negatives; separate 29-node guest and confined-file regression
passed. These are local function/provider checks, not a new live HTTP workflow pass.

All source tests disable bytecode/cache writes. License and unchanged processing
helper bytes are preserved. No shared SDK stub, source pin or original node
declaration was changed. No commit or push.
