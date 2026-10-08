# Secure conversion: InversedNoise

## Identity and review scope

Upstream https://github.com/logtd/ComfyUI-InversedNoise at exact commit
acd77730bfa1623150fea7835102d390bf36c9e1, release xacd7773. The complete pinned
codeload archive SHA256 is
4593c217c8d10daef174d2052aab5f858a17d867d193fb68e4d072f7408a92bb.
All five pristine paths/bytes match that archive and the independently retrieved
Git tree's blob identities, sizes and 100644 modes. Codeload group-write bits were
normalized by the corpus to 0644, consistent with Git executable-bit semantics.
The example workflow, README and hidden .gitignore are retained unchanged.
NO LICENSE is present; authorized local conversion is distinct from unresolved
publication/distribution permission. No source HEAD substitution or weights.

These are per-ID bounded Mac local behavior recommendations for independent
coordinator review, not registry/count/deployment promotion. Python 3.13 uses the
existing inherited development Torch runtime, without a sealed dependency profile.
Actual dependency versions and stub origins/hashes are in source-provenance.json.

| Backend ID | Disposition | Scoped behavior evidence |
| --- | --- | --- |
| SamplerInversedEulerNode | supported | Exact native inverse math, one-based post-update callback, all-zero NaNs, canonical KSAMPLER wrapper, fresh required guest and true CPU FLOW sample_custom |
| MixNoiseNode | supported | One draw including randomness0/1, exact controlled native draw/layout/dtype math, execution-local RNG, typed LATENT metadata-preserving replacement and outer result |
| CombineNoiseLatentNode | supported | Native division/subtraction, scalar/empty/5D/broadcast/promotion/nonfinite outcomes and native errors; NOISE receiver extras retained by identity |

## Census, frontend, routes and state

The actual pinned Python loader registers exactly the three IDs above. Categories,
display names, ordered inputs, randomness options/default0.1, output types and
Combine's noise output name are preserved. No frontend source, extension,
JS-only graph node, route, authored mutable configuration or durable data exists.
There is no persistence service to invent. A retained sampler closure lives only
in its owning prompt/session; it does not retain a raw model or broker past an
invocation. All algorithms remain in pack code.

Mix originally consumes ambient Torch RNG. This conversion deliberately uses an
unseeded execution-local CPU generator: one normal draw, exact source arithmetic,
no user seed socket, no fixed seed and no cross-node/global RNG continuation claim.
Controlled seeds in tests are test-only. Native admitted noncontiguous draw layout
is tested locally; raw transport may normalize layout but preserves numerical
values. Per-execution isolation and host global RNG unchanged are explicit.

Both numeric nodes read only public LATENT.samples()/TensorRef.raw(), and Combine
reads SIGMAS via public TensorRef.from_ref(...).raw(). They publish the computed
tensor using TensorRef.from_value and replace only samples through with_samples.
The latter makes a host-owned shallow plain-dict copy: opaque, cyclic, nested,
noise_mask and batch_index extras stay untouched with original host identities.
Combine copies NOISE extras, not LATENT extras. No whole LATENT value export,
metadata reconstruction, opaque materialization or raw model access is used.
Numeric raw-compute snapshots do not promise source tensor storage/device aliases.

## Sampler contract and source fidelity

Sampler declares closures only, and uses retain('custom_sampler', inverse_loop)
then as_sampler(sigmas_direction='ascending'). The public default descending policy
is not modified. The tested explicit ascending contract accepts finite,
nonnegative, nondecreasing floating 1D SIGMAS of length2..4097, including all-zero
schedules. Source all-zero NaNs are preserved bit-exact, not refused or sanitized.
Other direction/order/nonfinite schedules are outside this explicit admitted
inverse-sampling workload and are refused before model execution.

Source first-step denominator2*sigmas[i], later denominator sigmas[i-1], Euler
update and final division by sigmas[-1] are retained. The broker receives scalar
sigma_t and expands the source's x-dtype batch vector itself; batch1/2/8/64 native
model arguments are compared. The initial vector-delivery failure for batch>1 is
retained separately as a corrected pack callshape error, not a shared API gap.
Actual model extra_args are forwarded by the host, not reconstructed in the pack.

preview(..., value_phase='after_update', index_base=1, sigma_format='tensor')
preserves i=1..N and post-update x. Authentic denoised remains held by the host;
the callback receives 0D sigma/sigma_hat in authoritative SIGMAS dtype/device,
without source view/storage-alias promises. Managed preview audience/lifetime is
host-owned; arbitrary app events, caller IDs and broadcasts are not restored.
Preview/callback objects cannot escape their invocation. Source unused churn/noise
arguments remain inert rather than becoming new inputs or model policies.

The shared published contract is bound to
many-oct8-custom-sampler-contract/handoff.json, SHA256
ac08f08d6c440075b2cb5b14ee3250f8f6dba039cb4e5615776d0abebc3c2fb1.
Selected SDK55650333064b449eca49850bc199bec819b129967092dc59f8b69a6e459701f8,
hostf1d59032c49ba2f1c830fc0c9ddabd62d34f996931dbcf1435c3dac88476ee0a and
guestab53283fcc8e8dc559d5322a8ef39c7e64d160b22c354e1b70557c10927bfd13
are sampled before/after owner runs, not retrospectively attributed to predecessors.

## Permissions and supported workload bounds

Sampler requires closures. Mix and Combine require raw, including otherwise
simple calls. No inspect, host paths, network, assets, credentials, subprocess,
installation, global model/cache mutation, arbitrary device or dependency grants.
Raw denial, closure denial and subsequent recovery are exercised in real required
Seatbelt guests and production outer dispatch. Forged refs remain governed by
authoritative typed SDK resolution; model refs are never recovered by this pack.

Before numeric draw/computation, each dense nonnested input has <=32 axes and
<=32MiB logical data. Projected output must fit32MiB; inputs plus conservative
temporary work must fit192MiB. Combine meters full broadcast projection and a
16-byte element reserve to cover complex128 promotion; this deliberately bounds
the workload conservatively, not a claim of source maxima. Sampler meters its
input and six work buffers, in addition to existing host sampler dispatch bounds.
Host input transport and dense publisher limits remain separate; these pack
guards do not certify hard physical allocation/aggregate heap enforcement.
Resource refusal precedes drawing/integration or projected broadcast allocation.
Scalar/empty/higher-rank raw inputs and native integer-normal/index/shape failures
are tested, without silent shape/dtype/finite coercion. Randomness admission
matches its declared finite[0,1] workload and excludes bool.

## Observed evidence and release limits

Pack-owned tests/test_amy_inverse_conversion.py contains exact source schema and
source numerical controls, entropy isolation, native errors, logical resource
sentinels, production outer tests on recreated workers, all three capability
denial/recovery paths, sampler callbacks and real canonical sampling entry.
test_real_guest_ctx_sample_true_canonical_FLOW_diffusion_kernel_and_metadata uses
an actual tiny CPU BaseModel/FLOW/ModelPatcher and actual sample_custom/KSAMPLER;
it does not substitute a recorded producer or model=None. Its synthetic untrained
kernel is NOT trained-weight quality, accelerator, GPU-only placement, sealed
Linux, authenticated Cloud or deployment evidence. Standalone model protocol
controls are explicitly recording-model doubles, not that stronger entry test.
Core already owns model-native initial noise_scaling/final inverse_noise_scaling.

Final external handoff binds exact commands, observed logs, final file hashes,
pristine/V2 pair and twice pristine->V2 reconstruction (plain pair and deterministic
ZIP). Passing census/schema or total test counts alone are not support evidence.
The initial 147-pass/10-failure controls are retained: missing yet-unbuilt manifest,
an incorrect test ceiling literal and unsupported native wrapper marker kwarg,
all fixture/staging mistakes rather than altered source math. Frozen planning
and replacement consumer packets remain immutable. No full inference/device,
Cloud persistence, physical profile or publication claim is made.
