# calcuis GGUF — Secure Nodes V2 technical draft

This is **not a completed/released pack**. All13 IDs remain release-pending.
The conversion retains the exact pinned source as its sibling and does not
substitute the different City96 implementation for calcuis behavior.

Working technical paths include the exported FP32 booster and FP16
GGUF reverse converter using public raw/asset/output brokers, guest-owned
range parsing/quantization, and exact pinned metadata text. The CUDA FP8 cutter
retains its CUDA-only policy. The r3 focused fixture verifies real CUDA math
and exact original native saved tensor bytes, including the native empty-input
error. This does not qualify Cut's production guest output path.
The single SafeTensors CLIP branch uses the existing typed service but has no
trained-model evidence. Model/CLIP provider branches fail closed with an
explicit prerequisite rather than returning a misleading value.

Revision 2: GGUFSave, GGUFRun, VaeGGUF and AudioEncoderLoaderGGUF use the
Phase-1 SDK verbs (output.save_binary, assets.gguf_tensor_state,
models.vae_from_state_dict, models.audio_encoder_from_state_dict). They are
tested bit-exact against the original only on the Phase-1 SDK branch (core
844d7d60 / backend 7f73734e; pending SDK deployment). On the current runtime
they fail closed until the Phase-1 SDK ships. Operators must set
COMFY_SECURE_MAX_GGUF_MAPPING_BYTES and COMFY_SECURE_MAX_BINARY_OUTPUT_BYTES
(tested with 256 MiB each; the default 0 refuses the guest verbs).

See SECURE_CONVERSION.md for exact per-ID limitations, resource policies,
output-name compatibility changes and persistence disposition. The draft
secure-nodes.json describes registrations only; it is not a support certificate.
Standalone CLI/install/network tools are deliberately pristine-only.

The r3 correction reads SafeTensors payloads one tensor at a time and removes
conversion-invented1GiB storage/output limits. Its real2.13GB checkpoint test
passed under a12GiB fixture grant with about8.7GiB peakRSS. Guest Boost/Undo
tests use genuine existing SDK brokers in four fresh subprocesses inside
constrained Docker units; normal gVisor admission remains unqualified here.

The r5 successor removes the six reviewed decoder/writer rejections and
chunks headers through the existing SDK range API. Native SafeTensors owns
the100,000,000-byte format limit. Focused native and gVisor evidence is scoped
in SECURE_CONVERSION.md; all13 production nodes remain release-pending.
