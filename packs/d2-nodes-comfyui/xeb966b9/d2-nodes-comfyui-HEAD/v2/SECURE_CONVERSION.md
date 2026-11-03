# Secure conversion

Status: converted 21 of 70 declared backend nodes; 3 additional nodes are partial;
46 remain registered with explicit validation refusals. Frontend integration is
HELD. This is a backend recovery candidate for independent review.

Original node IDs, names, categories, input order, defaults, static choices,
output slots and hidden declarations are retained. CONVERSION-STATUS.json gives
the full census and refusal reasons. Unconverted implementation modules are not
imported in guests. The mirror retains upstream frontend files as data but does
not declare a web directory or register the original server routes.

The subset contains three refiner-step nodes, four size nodes (Image Resize is
partial), ten text nodes, and seven XY list/prompt/seed nodes (both seed nodes
are partial). Pure algorithms
remain unchanged or are extracted textually from modules whose unrelated
imports require the host. The two already-pure text helpers remain
byte-identical to the source.

## Evidence

The gate suite compares original source classes/functions against the mirror:
All 403 original finite inputs are retained: 380 differential cases are exact
and 23 host-global-RNG cases are named validation/execution refusals. They cover
defaults, every static COMBO choice, selected numeric bounds, errors and generated
IMAGE/MASK fixtures. The original RNG cases demonstrably advance source state;
their converted refusals leave RNG state unchanged. Local reseeding from the
earlier suite does not qualify randomness across independent processes.
Tensor comparisons include dtype, shape and bytes; floats
use their exact hexadecimal representation. Error type and message are exact.
An output-perturbation control must fail the same comparator.

Separate actual GuestSession checks cover all 24 backend implementations in
36 differential cases, plus 46 whole-node refusal validations and two
remote/partial validators. Fourteen additional RNG inputs each check both
validation and execution refusal, with exact host and guest RNG state unchanged.
A test-only observer records the guest's state around its stock adapter call.
The zero-count randomize branch, malformed seed parsing and Multi Output SEED
literal -1 also have actual Guest controls. They
check hidden prompt reads, exact UI JSON, errors, list output flags, MASK/IMAGE/
LATENT wire kinds and None paths. The guest selects base 0cd9adec and retains a
common-lock-derived import seal throughout execution, including cached imports.

Four more actual guest cases compare Core's seeded synthetic AutoencoderKL
normal/tiled encoding for RGB/RGBA. Host input bytes, dtype, shape and stride,
encoder kwargs and final latent bytes match. RGBA channel slicing occurs through
the existing host ImageRef.rgb() operation so the original stride is preserved.
The MASK output uses the existing typed LatentRef.noise_mask() operation.

Evidence runs on gate Core 6257422b, B13 sources 38f28c98 (native overlay
6f58bcec/e4d93d0d; engine SDK 038019fa), and guest base 0cd9adec. These are gate
results, not B13 deployment results. The separate guest runs inside the bounded,
networkless gate container; the gate has no inner kernel sandbox backend.
Production kernel isolation and GPU fidelity are not established here.

## Dependencies and SDK

Minimum base: 0cd9adec (comfy_api 0.37.0). Reachable backend code requires only
sealed common dependencies: torch, NumPy, Pillow and the standard library.
There is no private dependency profile and no runtime download.
SDK-CHECK.json records every SDK symbol/keyword against both lane bases.
The selected-base-only symbols are ImageRef.from_value and public
GraphDomain.execution_metadata. Filename Template/2 declares graph.metadata
and reads its owning prompt through that existing operation.

The copied public contracts are byte-identical to the lane's published copies.
That frozen Python stub omits GraphDomain.execution_metadata, although the
selected base's public protocol defines it. The discrepancy is recorded for
coordinator review; no contract or engine API was added or edited.

The manifest contains all 70 complete schemas and is about 434 KB, mainly from
the many input/output declarations and the real encoder's full attribute rows.
Static choices were preserved. Model catalogues use remote schema declarations;
input-file refresh and custom frontend widgets/routes remain held.

## Known differences and holds

- Every refused node fails validation with
  "d2-nodes-comfyui/<node id> is not yet converted to Secure Nodes V2".
  Its execution refusal additionally explains the specific blocker where known.
- Image Resize supports the original Pillow resize/rotate and tested VAE paths.
  A non-None upscale model is a named validation/execution refusal. VAE input
  with fewer than three channels is a named refusal.
- XY Seed refuses a reached line whose int() value is -1. XY Seed2 refuses
  int(initial_number)==-1 for every count/mode, including count=0, and refuses
  mode=randomize with count>0. Their real upstream defaults remain in the schema
  and explicitly refuse. Nonnegative initial/count=0/randomize returns the
  original empty output. Malformed deterministic inputs retain their original
  errors; Multi Output SEED literal -1 remains ordinary integer data.
- Filename formatting of opaque host objects is a named refusal. It does not
  materialize live MODEL/CLIP/VAE resources or replace dataclasses with dicts.
- Snapshot size/template presets are frozen from the two shipped sample YAML
  files. Ambient user YAML overrides are not read. The original duplicate Ceil
  branch in rounding is deliberately retained.
- Persistent queues, cross-execution tensor accumulation, live-object pipes,
  absolute host-path outputs, local Eagle calls and unpinned tokenizer loading
  remain explicit refusals. No engine operation specific to this pack is used.
- Original frontend routes/widgets are not activated. Dynamic widgets, custom
  HTTP routes, their refresh behavior and complete interactive-node fidelity
  remain held separately from this backend stage.
- The unused bundled font is withheld from the publication stage pending its
  own licence evidence. Upstream media/demo workflows and bundled model files
  are omitted from both stage siblings under the lane omission policy.
