# Simple QR Codes — bounded Mac-local conversion

Upstream commit 99996a62abcd8371581c48c43cad03b2dfdc56ea. All twelve IDs,
schema defaults/options/category/list-output flags and algorithms are preserved.
Seven QR writers, OpenCV multi-reader and three frame algorithms remain
pack-side under raw compute. ShowData's original rendering is retained; its
own ui.data updates its owning data widget through the published onExecuted
hook rather than a caller-ID broadcast. Upstream declares ./js but ships no
JavaScript; this hook is an explicit intent adaptation, not recovered JS.
Its input is the bounded plain scalar/tree/dense tensor profile, not arbitrary
native host object repr or host handle extraction.

All 19 retained source files match the commit-addressed archive and Git blob
identities/executable modes. The archive has two additional committed Python
cache files, individually recorded and never extracted or imported. The
old_versions ZIP is an inactive byte-exact resource, never executable.
MIT notice and immutable resources are retained; logos are IMAGE values or
source-created color squares, not paths. Text frames use native OpenCV Hershey
text, not a host font catalogue. No authored document/service/model state.

Native qrcode 8.0, segno 1.6.1 and segno-pil 1.0.0 are supplied by the exact
coordinator's 61-file readonly pure-wheel fixture. Fresh guest tests compose
those unchanged files and V2 into one temporary development import root.
There is no ambient install or shipped dependency copy. Actual scientific
runtime: Python 3.13, Torch 2.13.0, torchvision 0.28.0, NumPy 2.4.6,
Pillow 12.3.0 and OpenCV 5.0.0.93. Active metadata binds that measured profile,
not acceptance of upstream Pillow 10.4/OpenCV 4.11, a sealed runtime,
Linux/accelerator or Cloud provisioning.

Admission bounds are explicit supported workload restrictions, not source
maxima or hard parser/allocator peak-memory guarantees: 4096B per input string,
4,194,304 pixels per input/intermediate/frame, 32MiB logical input buffers,
96MiB estimated QR output buffers; ShowData has 4096 tree items/32 depth,
32MiB cumulative logical numeric buffers and 64KiB cumulative/result UTF8.
QR matrix and native scaling/border are checked before raster creation;
logo aspect/frame extents before their allocations. Default512 is tested.
Native invalid QR/Pillow/NumPy/OpenCV errors remain source controls.

Native B&W returns float32 grayscale (1,H,W), not ordinary BHWC RGB; its
two masks preserve native values/layout. Actual outer transport and the
unchanged source reader admit that grayscale output directly. No layout/math
repair has been applied and general BHWC typed-operation interoperability is
not claimed. Segno's format_light/finder_light typo and frame placement quirks
remain unchanged. qrcode style objects live only in the isolated pack realm;
no cross-node/global host state promise.

Whole local readiness still requires the source/schema/guest/UI/bounds/artifact
gates and coordinator independent intake. No count or deployment promotion
comes from this report.
