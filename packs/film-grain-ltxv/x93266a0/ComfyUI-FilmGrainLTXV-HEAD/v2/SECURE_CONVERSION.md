# Film Grain LTXV conversion

Upstream: https://github.com/boobkake22/ComfyUI-FilmGrainLTXV
Pin: `93266a0efcf093cbf197f89ff51a2892a0f4cc1b` (`x93266a0`).

Census: 1 Python supported, 0 rejected, 0 pending; 0 frontend, 0 routes.

The per-frame Torch algorithm remains in the pack under `raw` permission and
value mode. It preserves noise draw order, RGB channel weights, saturation mix,
float32 grain arithmetic, image dtype, and clamping. The guest owns execution
device placement and RNG; the pack neither selects a host device nor seeds a
process-global generator. Secure execution returns a fresh image rather than
mutating another consumer's input. Valid CPU computations are differentially
tested bit-for-bit against upstream; GPU-specific RNG streams are not exercised.

Resource bounds: nonempty RGB batches, <=64 frames and <=16,777,216 elements;
finite pixels and schema-bounded scalar controls. Filesystem, network, host
imports and private constructors are absent. Canonical SDK declarations are
pinned byte-for-byte. Manifest and pristine-to-V2 patches are roundtrip-tested.

Validation: the focused 42-case suite covers the actual registration census,
exact schemas, 12 upstream pixel/RNG comparisons across three image dtypes,
noncontiguous layouts and batches, three fixed-noise channel-weight cases,
invalid controls/images and resource bounds, and a real isolated guest running
zero-intensity, monochrome and colored stochastic paths. It checks raw-capability
denial and input isolation, canonical stub hashes, license preservation, and
byte-exact pristine-to-V2 patch reconstruction. No shared API changes required.
