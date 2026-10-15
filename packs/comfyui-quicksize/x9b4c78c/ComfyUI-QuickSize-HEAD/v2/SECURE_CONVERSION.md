# QuickSize V2 conversion

Upstream: https://github.com/rh6423/ComfyUI-QuickSize
Exact pin: 9b4c78c64726ababfc1d1b6c606f09b7120ad517, release x9b4c78c.
Registry release 0.0.1 archive SHA256
98d295e0771001fc07e6ebc4bcdd8148e31592c467028bfdb4051f0e39001c89.
All twelve complete retained distribution files match immutable Git blobs,
100644 modes and independently fetched commit-addressed codeload bytes.
Author Git contains one additional documentation image quicksize_nodes.png
absent from the registry release; it is recorded rather than silently captured
from a different source. The release's Qwen 2.0 choice remains, even though a
later author commit removes it. No latest-source substitution occurs.
Original LICENSE and declared GPL3 metadata are retained unchanged.

## Complete census and disposition

| Exact root ID | Bounded local disposition | Computation |
| --- | --- | --- |
| QuickSizeFluxNode | supported | Native megapixel/ratio tables and orientation. |
| QuickSizeQwenNode | supported | Native table fallback, including admitted 2.0 -> 1.0. |
| QuickSizeWanNode | supported | Native model-size/video-size table and 708 short side. |
| QuickSizeSD15Node | supported | Native 1.5x table and missing 9:16 -> square fallback. |
| QuickSizeSDXLNode | supported | Native 1.5x table and orientation. |

Five backend nodes, zero frontend extensions, JS-only nodes or routes. Source
module-local QuickSizeQwen/QuickSizeWan aliases are superseded by the original
root map and are not additional registered nodes. There are no weights,
learned operations, Internet, filesystem writes, process commands or mutable
state. The family names describe static size presets, not model inference.

## Pack algorithms and public boundary

All source files beneath src remain byte-exact in V2. The wrappers call the
native get_size methods directly, retaining every literal table, integer cast,
default, category, display name, width/height ordering and unknown-selector
fallback. Unknown orientation retains the native vertical branch. Literal
1.5x Boolean name remains rather than a renamed input. The V3 execute function
adapts the source callable while preserving all registered graph contracts.

SDK_REFS=True, no permissions, scalar inputs/outputs only. Every selector is
an admitted plain UTF-8 string of at most 64 bytes, and 1.5x is a plain Boolean.
Closed before-operation guards refuse oversized or opaque values; they do not
cast, normalize table entries or repair source fallback. Computation is a
constant-size table lookup and two integer results. No raw tensor, host model,
assets, storage, output or inspect API is called. Existing V2 schema and
NodeOutput APIs suffice; shared runtime/spec/generators are untouched.

## Runtime, persistence and evidence

No durable state, workflow-owned extra state or reusable cache is introduced.
The original Python >=3.10 requirement remains in pristine source; V2 selects
>=3.13,<3.14 as required by the current manifest runtime. Empty node
dependencies remain; local gates use the existing development interpreter. Inherited
core-bootstrap dependencies are sampled separately, not fabricated as a sealed
node dependency profile or a new install. No trained/GPU/Linux/Cloud deployment
or physical-runtime certification follows from these scalar controls.

The complete declared domain is 184 preset/tier/orientation/Boolean combinations.
Exact native controls exercise all combinations and each default/schema plus
unknown fallbacks and before-lookup refusal. Two fresh required Seatbelt guests
each execute all184 cases through the actual production outer executor with
zero grants, refusal and recovery. A separate actual CloudExecutionBackend
local guest executes all five defaults through trusted development source-root
selection; this is not a prepared-image deployment claim. Public manifest
proxies register exactly five IDs. Plain pair and ZIP reconstruct bytes/modes,
and wrong source preimages refuse.

Development gate:202PASS/1deselected before artifact generation; final whole
203-check unchanged-byte repeats and serial central intake are bound separately.
The initial generator rejected the source's unbounded >=3.10 minor range;
its consequent draft202PASS/1artifactFAIL is retained. V2 metadata alone now
selects a single minor range, with unchanged algorithm/schema tests.
The initial GitHub API rate-limit error is retained; provenance was closed
through verified native read-only Git transport and pinned codeload, not a
credential lookup, certificate bypass or unverified live-source replacement.
