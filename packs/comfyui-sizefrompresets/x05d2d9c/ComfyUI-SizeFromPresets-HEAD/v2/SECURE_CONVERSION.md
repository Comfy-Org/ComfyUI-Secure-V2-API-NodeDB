# SizeFromPresets conversion and observed validation

Source: `nkchocoai/ComfyUI-SizeFromPresets`, commit
`05d2d9cd430c64e303a2561b0d9b6e49fec1bbea`, canonical identity
`cnr:comfyui-sizefrompresets`. All thirteen original files, the upstream GPL
license, existing project name/version1.0.0 and publisher are retained.

The ten original node IDs, categories, display names, CSV choices, defaults,
integer limits and output names are preserved. Preset CSVs remain pack-local
files, read once at import. Seed selection uses the actual original NumPy RNG.
Reported dimensions retain their original values, including716x403 and403x716;
latent dimensions retain floor division by8. The original batch maximum4096
is preserved in schemas and is not a tested allocation size.

The existing public SDK supplies `io.ComfyNode`, schemas, `io.NodeOutput`,
`sdk.ImageRef` and `sdk.LatentRef`. Six nodes declare SDK_REFS, including the
image-inspection scalar node. Only the five latent producers request `raw`.
The other five nodes request no permissions. No models, routes, network,
custom frontend, private SDK methods or runtime installs are introduced.
Latent allocation is explicitly CPU. Adoption in a different engine profile
requires its own CPU-intermediate selection evidence; non-CPU parity is not
claimed. The only project metadata addition is requires-python>=3.13,<3.14
in the isolated converted copy; other original project metadata is preserved.

## Actual evidence from2026-10-19

The actual Mac differential used the recorded installed SDK0.42.0,
Python3.13.14, Core44564d0, NumPy2.4.6 and Torch2.13.0. It passed120 cases:
ten schemas,109 execution comparisons and one import-time CSV snapshot check.
It covered all fourteen preset choices, repeated seeds0/1/max64, batch1/2,
float32/float64 defaults and first-row tie selection. All four negative controls
were detected: swapped dimensions, rounded reported dimensions, wrong seed
stream and reversed first-row tie. This was an in-process local CPU fixture.

The real approved generator and canonical tooling then generated the ten-node
normal manifest, official pair and ZIP, and replayed both. All five commands
passed; generated and replayed fifteen-file converted trees matched bytes and
Git modes, with all thirteen pristine files unchanged. API141/Core1384,
scientific-source4/backend83 and frozen-candidate14 aftermaps matched their
selected inputs. The normal manifest SHA256 is
`397ea4fdd91b8f7783294196a9a83b9f9b7d916c1f2494c2fa48b09fc5ea01d8`.

Actual service5175 gVisor TEST `18145b11892f37130676764b16edde5e`
executed all ten nodes and produced ten PNG outputs. Their dimensions and every
pixel were independently checked. All five latent consumers returned actual
shape, batch1, CPU, float32 and nonzero-count0 facts, including the odd-size
403x716 latent shape[1,4,89,50]. A deliberate wrong-width expectation in
TEST `8679016a84c8530a60b794dc8daffa19` failed at the expected execution
assertion and returned no successful output. The actual service used its
selected Python3.13.7/Torch2.8.0+cu128 environment and a captured--cpu worker;
it is a distinct environment from the Mac comparison.

The first service attempt failed because a TEST-only helper awaited a method
object. That real failure is retained. The helper was corrected to
`await latent.value()`; production code and its normal manifest were unchanged.
Helper metadata came from the genuine selected encoder. All helpers and their
two additive declarations are outside the canonical pack. Exact CSV/license/
binary bytes were seeded into only a private editor fixture because the editor
text API excludes those files; no CSV was renamed. That fixture was closed,
and matching TEST workers were absent after completion. The actual service
policy was model-test; these workflows requested no models.

Validation records, the preserved failure, helper correction, actual outputs
and exact source/profile limits accompany the corpus handoff under
`validation/20261019-sizefrompresets/`. The successful corrected ephemeral ZIP
was retired before copying; only the preserved first snapshot plus the exact
corrected-request delta is claimed. These notes were added after the observed
tests. The final notes-only pair and both replays are regenerated separately
on genuine POSIX0644 files; no production algorithm or normal-manifest byte
changes and no additional SDK/service tests are required for that file delta.

No non-CPU path, service batch above1, real allocation at4096, general target
engine/managed-runtime adoption or registry admission is certified here.
