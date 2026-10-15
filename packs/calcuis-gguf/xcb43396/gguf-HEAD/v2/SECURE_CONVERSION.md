> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 13 of 13 upstream converted; 2 tested (scoped), 1 converted but untested/partly tested,
> 10 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — calcuis GGUF (`calcuis-gguf`)

The 10 "partial" nodes are registered with their original IDs and schemas but fail closed with an
explicit message until the host capability they need exists (see *Pending capabilities*).

## Provenance

Upstream https://github.com/calcuis/gguf at commit `cb433968a4d42c59fc344d659ad94200b6c16689`
(key `xcb43396`). The pristine tree beside `v2/` is byte-exact at that commit (89 tracked files).
Their SHA-256 values are pinned in `v2/tests/pristine_sha256.json`. This is a different pack from City96 `comfyui-gguf`;
City96 code is never substituted for Calcuis behaviour.

## Node dispositions

Node IDs, display names and categories are the original's (mirror mode).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| `TENSORBoost` | TENSOR Booster | tested (scoped) | Output tensor bytes/dtypes equal the original native files (real Torch 2.8 + SafeTensors); real guest subprocesses ran it through installed SDK assets and managed output. A 2.13 GB SD1.5 checkpoint (1145 tensors) was verified under a 12 GiB fixture. The r5 helpers pass in actual gVisor. |
| `GGUFUndo` | GGUF Convertor (Reverse) | tested (scoped) | Real guest subprocesses passed native dtypes/bytes, reverse metadata, empty outputs, collision-free counters, and raw/assets/output permission denials. |
| `TENSORCut` | TENSOR Cutter (Beta) | converted, partly tested | The r3 fixture verified real CUDA math and exact native saved bytes, including the native empty-input error. The production guest output path on a CUDA worker is not qualified. |
| `GGUFSave` | GGUF Convertor (Alpha) | pending capability | Alpha writer bytes equal the native writer across float32, float16, bfloat16 and float8_e4m3fn (actual gVisor). Publishing the `.gguf` output needs bounded binary output, so the node fails closed. |
| `GGUFRun` | GGUF Convertor (Zero) | pending capability | Zero writer: same evidence and the same missing capability as GGUFSave. |
| `LoaderGGUF` | GGUF Loader | pending capability | Needs an opaque `ModelRef` constructor that selects the retained Calcuis implementation (`calcuis-diffusion`). |
| `LoaderGGUFAdvanced` | GGUF Loader (Advanced) | pending capability | `calcuis-diffusion`, including the dequant/patch dtype and `patch_on_device` semantics. |
| `ClipLoaderGGUF` | GGUF CLIP Loader | pending capability | The GGUF branch needs Calcuis `ClipRef` construction (`calcuis-text`). The single-SafeTensors branch uses the existing typed service but has no trained-model evidence. |
| `DualClipLoaderGGUF` | GGUF DualCLIP Loader | pending capability | `calcuis-text` (ordered assets, native device and type handling). |
| `TripleClipLoaderGGUF` | GGUF TripleCLIP Loader | pending capability | `calcuis-text`. |
| `QuadrupleClipLoaderGGUF` | GGUF QuadrupleCLIP Loader | pending capability | `calcuis-text`. |
| `VaeGGUF` | GGUF VAE Loader | pending capability | The native GGUF VAE needs an opaque `VaeRef` constructor with Calcuis decoding (`calcuis-native-vae`). The ordinary VAE branch uses the existing `load_vae` but is untested with trained models. |
| `AudioEncoderLoaderGGUF` | GGUF AudioEncoder Loader | pending capability | Needs a typed `AudioEncoderRef` constructor (`calcuis-audio`). |

## Refused techniques (never-do) and their public replacements

No user-visible node or feature is refused. Only these techniques are:

1. **Reading model files by absolute host path.** Upstream does this with `folder_paths.get_full_path` in `pig.py` lines 571–1129. It
   exposes the host's layout and allows unconfined reads. *Replacement:* logical asset names read
   through published, confined asset ranges (TENSORBoost, TENSORCut, GGUFUndo, GGUFSave and GGUFRun).
   Loaders: not yet, pending the typed model constructors below.
2. **Writing outputs straight into the host output directory.** Upstream combines `get_output_directory()` with `save_file` or
   `GGUFWriter` in `pig.py` lines 827–1004. This bypasses ownership, conflict and quota rules. *Replacement:*
   managed output publication for SafeTensors. GGUF bytes: not yet, pending bounded binary output.
3. **Network downloads and file writes from the bundled CLI tools.** In `gguf_connector`, b1.py and b2.py call
   `huggingface_hub.snapshot_download`; d.py, d2.py and e.py write into the working directory; data.json holds model URLs.
   This is unaudited network access plus arbitrary host writes. *Replacement:* the tools stay pristine-only (v2 never imports them),
   and models come from the managed catalogue.
4. **Installing packages at runtime** (upstream README: `pip install gguf-node`). This mutates a shared environment.
   *Replacement:* the locked runtime base (Python >=3.13,<3.14) and declared dependencies.

## Pending capabilities (not yet supported — nodes fail closed)

- `calcuis-diffusion` — LoaderGGUF, LoaderGGUFAdvanced: an opaque `ModelRef` selecting the Calcuis loader.
- `calcuis-text` — ClipLoaderGGUF, DualClipLoaderGGUF, TripleClipLoaderGGUF, QuadrupleClipLoaderGGUF.
- `calcuis-native-vae` — VaeGGUF.
- `calcuis-audio` — AudioEncoderLoaderGGUF.
- `gguf-binary-output` — GGUFSave, GGUFRun: bounded managed binary output with an opaque receipt,
  never host paths.

## Open test gates

- A model-capable normal-renderer TEST route with real GGUF assets, for loader and inference parity.
- TENSORCut's production guest output on a CUDA worker.
- Managed binary publication for GGUFSave and GGUFRun, once that capability exists.
- Big-endian GGUF, plus the BF16 and one-dimensional state-transport limits recorded in the notes below.
- Whole-pack acceptance review and registry admission.

## Authority and permissions

- Loaders (8 nodes): `models`.
- Converters and tensor tools (5 nodes): `raw`, `assets`, `output`.
- No network, host filesystem paths or subprocesses. Runtime: Python >=3.13,<3.14.

## Assets and weights

No weights are committed. Users supply GGUF/SafeTensors models through the managed model catalogue
(`unet`, `clip`, `vae`/`vae_gguf`, `audio_encoders`/`encoder_gguf`, `select_safetensors`, `select_gguf`).
Upstream points to example models at https://huggingface.co/calcuis; they are not bundled.

## Conversion notes (retained r5 report)

### Calcuis GGUF pack correction r5

Pin: cb433968a4d42c59fc344d659ad94200b6c16689.
This is a pack source successor to the sealed r1 asset-range draft. All13
registrations and node bodies are retained; this is not whole-pack acceptance.
The r2 SDK/runtime experiment is excluded and unapplied.

SafeTensors input now validates the complete header, exact shape/dtype spans,
metadata, contiguous coverage and absence of overlap before reading payloads.
Each tensor is decoded separately by the installed SafeTensors decoder. Stored
BF16, scalar and empty shapes stay exact. Header and payload reads are64KiB.
The header format limit is the installed native parser's100,000,000 bytes;
the SDK's16MiB per-request ceiling does not cap the complete header.
Removed conversion-invented1GiB state/output and aggregate element limits,
and the arbitrary state/SafeTensors rank8 cap. Resource admission remains the
host's responsibility. Empty states and keys, long keys, more than65,536
tensors and writer rank9 are accepted. Parser bounds derive from file spans
instead of arbitrary string, count, metadata or rank ceilings. Logical names
retain published asset confinement; each SDK domain and host filesystem owns
its additional rules. There is no full unrestricted native-parity claim.
The binary writer still enforces explicit caller limits when supplied.

Focused native tests use the original package and original nodes, real Torch
2.8.0+cu128, CUDA and SafeTensors. Boost and Cut output tensor bytes/dtypes
match original native files. Cut empty input produces the native error.
Alpha/Zero complete GGUF files match original native writer files for the
focused matrix fixture. These checks supersede the old arbitrary-cap tests.

The actual SD1.5 checkpoint is2,132,696,762 bytes and1145 tensors. All stored
tensor bytes/dtypes and every saved nativeF32 cast were verified. Saved output
is4,265,145,968 bytes. The12GiB isolated fixture passed with peakRSS9,108,456KiB;
the earlier8GiB fixture was OOM-killed and remains in the ledger. Removing a
pack cap does not qualify that model for a smaller production worker grant.

Four fresh real guest subprocesses exercised exported TENSORBoost/GGUFUndo
through unchanged installed GuestSession/SDK assets and managed state output.
Native dtypes/bytes, reverse metadata, empty outputs, collision-free counters,
and raw/assets/output permission denials passed. These guests used sandbox
kind none inside constrained owned Docker units, not normal gVisor admission.
Historical r1 actual public gVisor receipts remain sealed; they were not rerun.

Full loader/provider/device/inference and managed GGUF binary-output seams
remain separate work; City96 is not substituted for Calcuis. No shared or
isolated SDK/broker/runtime integration was changed in this successor.
This pack directory is the V2 overlay only; pristine original sources are
retained in the canonical base and the hash-pinned test fixture package.

#### Focused r5 evidence

Fourteen new regressions passed against actual installed SafeTensors and the
pinned native GGUF writer/reader, locally and in actual gVisor. The six reviewed
failures now pass: empty state, empty and4097-byte keys,65537 empty tensors,
writer rank9 and an empty GGUF tensor name. Complete native GGUF bytes, reader
values and metadata agree for the writer cases. A header above16MiB assembles
in64KiB chunks; the100,000,000-byte native boundary is independently checked.
The real existing SDK asset reader passed the large-header fixture locally.
The gVisor test uses genuine encoded bytes and pure production helpers; it
does not claim asset RPC or empty-state managed output publication.

Positive job `143fa96fb7ab730c01a8165e03fe70dd`; expected assertion-negative `19a9c2e22e2a169bbb121cc58aaf1286`.
Both use the same source draft and actual gVisor. Positive PID1 is recorded;
the negative receipt omits PID. All13 production nodes remain release-pending.
The local frozen service has no located model-capable TEST registration;
capability of the intended Bens Linux registry route is not established.
Big-endian GGUF, provider/inference and managed binary publication remain
outside these focused checks. No SDK, runtime or service code was changed.
