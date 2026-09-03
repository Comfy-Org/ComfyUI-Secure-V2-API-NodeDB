# Secure Nodes V2 conversion ledger (terminal)

## Source identity and exact census

- Pack: `audio-general-comfyui`
- Upstream: `https://github.com/niknah/audio-general-ComfyUI`
- Full commit: `0a1d63a157a200a4161de3a10d210b6a66a4bf31`
- Git tree: `338dd650dc528c2a7b4c1110c50b7ee3d1584689`
- Release key: `x0a1d63a`
- Pristine-tree digest:
  `526fe9762194410351a09cca7d7f5d7851a1477eb8e4e9dea34f90d6dd6f7415`

The pin registers exactly nine backend IDs: `AudioInfo`, `AudioSampleRate`,
`AudioPitch`, `AudioMix`, `AudioConcat`, `AudioTrimSilenceVAD`,
`AudioTrimSilenceRosa`, `AudioBassTreble`, and `AudioSpeed`. It also registers
exactly two frontend behaviors, `AudioGeneral.AudioMix` and
`AudioGeneral.AudioConcat`.

Supported: 11/11 exact census items. Rejected: 0. Pending: 0. All 9 backend
implementations and both frontend implementations are behavior-complete. The
release contains the frozen `comfy-api.pyi`/`comfy-api.d.ts` contracts and a
checked patch pair. Catalog registration is intentionally coordinator-owned
and is not part of this release tree.

## Retained behavior

All audio algorithms remain in this isolated pack. AUDIO values cross the
host boundary only through typed `AudioRef` values; the implementation neither
receives host audio objects nor uses paths, network access, subprocesses,
runtime installation, routes, or host-global mutation. Exact pristine
differentials with shared deterministic dependency substitutes exercise all
nine IDs, both bass/treble branches, both valid AudioSpeed choices,
AudioSpeed's unreachable-by-schema default branch, list inputs, resampling,
offsets, trimming, and output metadata. A full object-info differential also
checks every schema field and preserves whitespace in published descriptions
and tooltips.

Pinned quirks are deliberate:

- `AudioInfo` retains its lowercase custom `int` output type.
- Every other node's broken `IS_CHANGED` raises in legacy ComfyUI and is
  treated as always changed; V2 returns `NaN` directly.
- `AudioMix` retains whole-node list inputs. Consequently `[False]` is truthy
  and selects the constant-volume division branch.
- The `AudioSpeed` schema offers `torch-time-stretch` and `TDHS`, while its
  implementation checks `torch-time-shift`. Both valid UI values therefore
  use AudioStretchy; only omission at direct invocation reaches
  `torch-time-stretch`. The node returns only the last input-list result.
- `AudioTrimSilenceRosa` retains the computed numpy value, normalizing its
  scalar to a Python float only because the FLOAT wire boundary is JSON.

The frontend runs through `/comfy/api/v2.js` in the Secure Nodes sandbox. It
retains the unusual upstream rule that only the final AUDIO slot determines
whether another slot is added, never removes slots, adds the first missing
contiguous `audioN`, and creates paired volume/start widgets for AudioMix.
Both an isolated worker-shaped harness and the production iframe/host bridge
exercise dynamic slots, dynamic widget values, serialization, and extension
queuing before the pinned backend-shaped definitions are registered. A stable
node-id restore barrier ignores half-configured connection callbacks while
`NodeCreatedEvent.restored` or `loading` is set, then reconciles the complete
snapshot in `onConfigured`. The production proof serializes and reloads the
graph and asserts exact unique `audio1,audio2,audio3` slots plus restored
dynamic widget values.

## Managed dependency proof and distribution

The pinned pack directly declares `torchaudio`, `audiostretchy`,
`torch-time-stretch`, and `librosa`; V2 declares the same four requirements.
The manifest binds external profile
`0efe9730e960e77448c0bf7500a8fc24a98f572e5ddde629fc43cd21f92957de`.
Its Python 3.13 / `macosx-11.0-arm64` target binds the exact 26-wheel lock
`40bc18f0bf4c986fc1c9b6abec7c2506c054fc236f04591e6666d35f24112e3c`.
Test-only deterministic doubles retain a fast source/V2 branch differential,
but they are explicitly not release evidence for the dependency closure.

The substitutes intentionally do not claim numerical parity with the real
libraries. On the current fixtures, the terminal proof must reproduce 18,435
int16 samples from `audiostretchy==1.3.5`, 17,998 samples from
`torch-time-stretch==1.0.3`, and an 18,432-sample float32 Rosa result from
`librosa==1.0.0`; the temporary substitutes instead produce 24,000, 12,000,
and 23,998 samples respectively. The managed-runtime proof cannot install or
invoke those substitutes.

The generic private dependency path is coordinator-verified, and no
shared/core API change was required. The terminal proof provisions the bound
profile through the real draft/install path, executes all nine nodes in a
fresh managed `GuestSession`, and asserts the three real-package output
lengths and dtypes above. It has no `sys.modules` injection path. The final
runtime-security suites passed 148/148 and 306/306 twice before this release
was sealed.

License material must travel with that managed layer. The direct packages
declare BSD-3-Clause (`audiostretchy`), MIT in the wheel license
(`torch-time-stretch`, despite UNKNOWN package metadata), and ISC (`librosa`).
`librosa` pulls `soxr`, whose wheel includes its LGPL-2.1-or-later and bundled
component notices, and `soundfile`, whose wheel includes libsndfile and bundled
codec source/license compliance notes. All 25 non-primePy wheels contain their
license/notice payloads, whose exact archive paths are audited against the
content-addressed lock. `primePy==1.3` alone omits its license from the wheel;
`third-party-notices/primePy-1.3-LICENSE.txt` retains the exact upstream MIT
text from untagged commit
`ee9cc1666bdd6e1e2984ad10d307213e481c937b`, with SHA-256
`1a06a1576544095ade4508462bc6c795c874a499e2abe12d21557e85a3741d9e`.
The installed layer and its distribution must continue to preserve all wheel
notices and applicable source-offer/source-distribution requirements.

The frozen contract hashes are:

- Python stub SHA-256:
  `5c94bedf783e9e92971d0369fabc23b10d6f7169fc86fecdee64a3607d9f3142`
- TypeScript stub SHA-256:
  `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`
