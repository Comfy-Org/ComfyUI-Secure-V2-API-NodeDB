# pack-db

Converted Secure Nodes pack database. Each pack root preserves the pristine V1
source at the commit recorded in `packs/packs.json`; its materialized `v2/`
directory is the review copy of the conversion. The matching files under
`patches/` are the deployable recipe: applying the `.json` manifest and `.diff`
to that pristine V1 source reproduces the complete V2 tree byte-for-byte.

`ComfyUI_secure_nodes` consumes this repository as its `pack-db` submodule.

    packs/<slug>/<xsha>/<Pack-Name>-HEAD/
        …the pack, exactly as upstream ships it…
        v2/                    THE CONVERSION — part of the pack, inside it.
            …a complete copy of the pack with the conversion applied…
            comfy-api.d.ts     the JS API contract
            comfy-api.pyi      the Python API contract (generated)

`<xsha>` is the pack's short git commit sha; `packs/packs.json` records the
upstream URL and full commit.

**A converted pack is one that has a `v2/` subfolder** — which is precisely
what applying its patch pair produces:

    patches/<slug>/<xsha>/<slug>-<xsha>.json    per-file manifest
                          <slug>-<xsha>.diff    the boundary-only diff

The checked-in trees are conversion artifacts. `v2/` is fully materialized so
it is self-consistent when used as the pack root: sibling imports and relative
resource paths never cross back into v1. Unchanged files are represented as
`copy` entries in the manifest, so their bytes are not duplicated in the
deployable patch.

The checked-in pack is platform-neutral source and does not contain generated
virtual-environment files. Installation applies the patch into a derived pack
and selects a content-addressed, read-only runtime base containing the managed
standalone Python and common locked dependencies. It then turns the top-level
pack directory—the parent of `v2/`—into a minimal private venv whose Python
links to that base and whose private site-packages precede the common layer.
Only separately locked pack-specific dependency deltas are installed into the
private layer. The complete derived pack and both dependency layers are sealed
read-only before execution; only a realm-private disposable directory is
writable.

The standalone runtime archive, common wheelhouse/lock, and optional pack-delta
wheelhouse/lock are external content-addressed install inputs. They are not part
of the pack or patch bundle. A release that needs a private delta declares only
`runtime.dependencies.profile_sha256`. That digest identifies the exact bytes
of an immutable, platform-neutral profile object containing normalized exact
pins, the wheel-only/no-dependency-resolution policy, and the finite map from
`(Python minor, platform tag)` to actual lock digest. A target not present in
that map is unsupported and fails closed.

The external store holds profiles at
`objects/profiles/<profile-sha256>.json` and deltas at
`objects/<lock-sha256>/{requirements.lock,wheelhouse/}`. Both objects verify
their own content identities before use. There is no mutable selector in the
resolution path. The concrete target lock digest, not merely the neutral
profile digest, enters the runtime seal. Both the neutral profile digest and
the selected concrete lock digest enter the pack-image identity. The private
wheelhouse must contain exactly the profile's pins, must contain only binary
wheels, and may not shadow any normalized distribution name in the selected
common wheelhouse. Dependencies may depend on common packages, but their delta
must not replace them.

Admission also inspects every private wheel member before build, resolution,
and provisioning. It rejects unsafe or special paths, `.pth` and interpreter
customization modules, case-folded path collisions, common/trusted or
inter-private module and resource collisions, and ambiguous package takeover.
Disjoint PEP 420 namespace descendants remain valid only when neither layer
initializes their shared namespace ancestor. Each private wheel is limited to
20,000 members, 512 MiB per uncompressed member, 2 GiB total uncompressed
bytes, a 512:1 member ratio, and a 100:1 aggregate compression ratio. A whole
private wheelhouse is capped at 512 wheels, 100,000 members, 2 GiB
uncompressed, 1 GiB of both actual and projected compressed bytes, and 100:1
compression. Member components are capped at 240 UTF-8 bytes and projected
relative paths at 512 bytes before extraction. These bounds cover admitted
binary wheels while bounding extraction and path failures. Wheel `METADATA`
is separately capped at 4 MiB before it is read or parsed, and a private
`requirements.lock` is capped at 1 MiB before reading.

Runtime bases, `pyvenv.cfg`, `bin/` or `Scripts/`, installed `site-packages`,
and `.comfy-runtime.json` are runtime products and are never committed to this
database. Packs may share verified immutable bytes but never a writable
environment, process, or filesystem state.

Render-time tenant copies are additionally keyed by immutable source, Python,
and dependency-profile identity beneath the tenant root. Rebinding the same
pack UID to a new neutral dependency profile creates a distinct sealed runtime;
the prior runtime is retained read-only and an existing guest process is
recycled before the new profile starts.

For local development, installation copies the pristine snapshot into
`deploy-packs/<slug>/<xsha>/`, applies the certified patch there, and creates
the pack venv only in that deploy copy. The entire `deploy-packs/` workspace is
ignored by git. Installation never patches or provisions a tree under
`pack-db/`.

The local POC may reconstruct the pristine V1 input with a detached fetch of
the full commit in `packs.json`. After applying the patch and before creating
the venv, its debug profile compares the resulting `/v2` files, bytes, and
modes with this database's checked-in review tree. Production uses the
manifest hashes rather than requiring that second full tree.

The production pack-management SDK's `install_pack` command selects this flow
by approved catalog identity. It does not expose repository, patch, runtime, or
filesystem inputs directly to clients or to code executing inside a pack.

The local POC uses the same installer through
`backend/scripts/install_pack.py`. Before Cloud starts, trusted bootstrap code
builds the wheelhouse with `backend/scripts/build_pack_runtime_inputs.py`, then
passes the approved source snapshot, patch ZIP, runtime-input directory, and
standalone-Python descriptor to `install_pack.py`. Repeating the same command
validates and returns the existing sealed hash; it does not rebuild or replace
it. These filesystem arguments are local bootstrap inputs, not the eventual
public management API.

Admission builds a private target, when needed, with
`backend/scripts/build_pack_dependency_delta.py`. It accepts only an exact
`name==version` requirements file, downloads with `--no-deps` and
`--only-binary=:all:`, compares the result with the selected common runtime,
and emits the existing hash-locked `requirements.lock` format. Local install
receives the external store through `--pack-dependency-store`; no lock,
wheelhouse, or platform-specific digest is copied into the pack or patch.

After installation, `backend/scripts/build_custom_node_deployment.py` publishes
the active pack selection and its Cloud projection under the ignored deployment
workspace. Its projection contains the filtered `object_info.json`, node-pack
map, converted extension tree, and declared HTTP static roots. The deployment ID
covers the selected pack release, projection, and runtime-profile ID. The
runtime-profile ID separately covers the clean ComfyUI engine, platform, and
secure overlay; installed packs are not part of that profile. Installing or
upgrading a pack therefore does not rebuild the runtime profile.

Pack execution assets are separate from browser assets. For KJNodes, `fonts/`
is declared as the logical `kjnodes_fonts` broker root and remains inside the
installed pack; it is not copied to the web projection. The converted
`kjweb_async/` directory is browser content and is copied to its existing HTTP
compatibility root.

A conversion is authored AS a diff: `v2` files are direct edits of the
originals, so `diff <pack>/nodes/x.py <pack>/v2/nodes/x.py` reads as the
security boundary and nothing else.

The deployed artifact is one derived zip containing only the manifest and
unified diff; the zip is not checked in. The backend verifies the pristine
snapshot and the complete manifest, builds `v2/` in a temporary sibling
directory, verifies every output hash, and atomically publishes it inside the
pack. Older ComfyUI versions ignore that subfolder and continue to load the
pack root.
