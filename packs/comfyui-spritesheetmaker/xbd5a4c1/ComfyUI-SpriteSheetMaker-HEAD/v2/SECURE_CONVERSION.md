# SpriteSheetMaker V2 conversion

Upstream: https://github.com/OSAnimate/ComfyUI-SpriteSheetMaker
Distribution: registry release 1.0.0, pinned at
bd5a4c17587d521c9836f068906eabfc5c38ed31 (`xbd5a4c1`). The commit contains
`node.zip` byte-identical to the registry archive (SHA256
9f32b72fbaba8824e45c7c3260b7995d7f3a148dd21b9e4d192081e46150b290).
This is distribution-blob correspondence: extracted README/LICENSE/pyproject
use CRLF while author Git files use LF, and distribution Ruff cache files have
no corresponding author source files. No newer author source was substituted.
All eleven retained distribution files and their 0644 modes remain exact;
raw ZIP 0666 modes are separately recorded. Two shipped interpreter-specific
pyc files excluded by the retained source corpus are not executable source.
Apache-2.0 LICENSE and examples remain unchanged.

## Census and disposition

| Exact backend ID | Local disposition | Source and verification |
| --- | --- | --- |
| SpriteSheetMaker | supported within bounded managed-image profile | Original ImageGridNode grid method; exact ordered pixels, schemas, errors, public IMAGE output and required guests. |

Complete census: one backend node, zero frontend extensions, JS-only nodes or
routes. The original display mapping targets unregistered `ImageGridNode`;
that source quirk is preserved. Category ImageGrid, row/column defaults 2,
single IMAGE output named sprite_image and source row-major layout remain.
Final evidence is bound by the separate handoff; local recommendations require
coordinator serial review before the completion ledger is advanced.

## Behavior and workload

The extracted create_image_grid method is AST-exact, including RGB black
canvas, native Pillow paste behavior and swallowed per-cell exceptions. The
literal NumPy float32 /255 and Torch singleton-batch publication remain
pack-owned. All selected files are opened and checked for equal dimensions,
including files beyond the requested grid. Native first-frame, palette, alpha,
CMYK, grayscale, uint16 and floating TIFF behavior is retained; no EXIF
transpose, resampling or alpha-composition repair is added. Zero axes yield
empty images and small negative axes retain native errors. No filesystem write,
fingerprint, private output dictionary or host-path recovery is added.

Explicit managed-profile adaptations: public directory options are sorted and
include root and nested confined directories; source enumerates unsorted
immediate directories. Public immediate file listing is deterministic rather
than native OS ordering. Source pixel oracles normalize only file enumeration
to that managed order; a separate reversed-order test demonstrates the
observable tile permutation. Arbitrary OS-order equivalence is not claimed.
Traversal, escaped symlinks and nonportable relative names are refused.

Bounds: 128 selected files, 16 MiB per encoded file, 64 MiB aggregate encoded
bytes, absolute grid-axis value at most 4096, 32 MiB float32 IMAGE output and
128 MiB projected simultaneous ownership. Preflight reserves twice encoded
bytes, four bytes per input pixel, sixty bytes per output pixel and 8 MiB fixed
overhead before grid creation/NumPy work. This is conservative pack admission,
not a sealed physical memory profile or a proof of all native parser peaks.
Encoded read uses bounded range chunks, a separate one-byte tail and re-size
check. Concurrent same-size mutation is not an atomic snapshot guarantee.
Pillow image, BytesIO and canvas resources close on success and error, including
publication failure. No authored durable state or reusable cache is introduced.

## Public API, runtime and verification

SDK_REFS=True; only assets and raw capabilities are declared. Managed assets
list/resolve/size/read_range provide input bytes; public ImageRef.from_value
publishes the exact computed tensor. No model, Internet, output, storage,
inspect, process or frontend grant is needed. All computation remains in the
guest pack. Existing public APIs suffice; no shared runtime or generator edit.

Local selection: Python >=3.13,<3.14, inherited Torch 2.13, NumPy 2.4.6 and
Pillow 12.3. Dependency/native payload identities are recorded in the handoff;
no dependency install, sealed image, dependency profile or deployment identity
is fabricated. The actual CloudExecutionBackend local test uses a trusted
host-selected source root with the existing development interpreter; it is not
prepared-image or Linux Cloud proof.

Verification covers twelve image modes/encodings and six grid shapes, source
schema/default/error controls, bounded reads and before-compute refusal,
symlink/path confinement, exact lifecycle disposal, live directory proxy
options, two fresh required Seatbelt guests through the production outer
executor, and a separate actual CloudExecutionBackend guest. Assets/raw
denials, oversized output refusal and recovery are exercised. Literal pair
and ZIP reconstruct bytes/modes; a wrong source preimage is refused.

Observed failed predecessor gates are retained in evidence: source-oracle
symlink fixture, unregistered source-root guest admission, ZIP/cache census
and provenance normalization diagnostics. They are not final green results.
Final unchanged-byte repeats sample participating runtime sources and preserve
all predecessor logs. Tests use synthetic small images; no trained/GPU/Linux,
Cloud deployment, complete codec-universe or native-heap certification follows.
