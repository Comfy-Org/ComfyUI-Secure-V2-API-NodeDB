# Secure Nodes V2 conversion

Upstream: `https://github.com/ApexArtist/comfyui-apex-artist`

Pinned commit: `5aaac3bd6c84e2ba3c7a5848bcd3e4aa00d3831c`

## Census and disposition

- Backend nodes: **6/6 supported**, 0 rejected, 0 pending.
- Frontend registrations: **0/2 supported, 2/2 rejected**, 0 pending.
- Non-node route behaviors: **0/14 supported, 14/14 rejected**, 0 pending.
- Pending API gaps: **none**.

The four image nodes run their pinned tensor algorithms in the isolated guest
using only the bounded `raw` tensor capability. The prompt node reads the
immutable, pinned `prompt_presets.json` shipped with this release and preserves
the source's deterministic seed behavior. The LoRA node resolves a logical
entry from the host LoRA catalogue and asks the existing host operation to
apply it; paths and weights never enter the guest.

## Rejected legacy browser behavior

The two source extensions are not shipped in V2. They construct ambient DOM
panels, reach directly into the global graph/canvas, enumerate host model
folders through pack routes, serve caller-supplied filesystem paths, generate
and mutate thumbnails beside model files, and mutate `prompt_presets.json`
inside the installed pack. The fourteen routes exist only to support those
behaviors. Restoring them would reintroduce broad filesystem and page authority
and would make the sealed release mutable, so they are explicit security
rejections rather than silent no-ops.

The immutable presets and all six queued node computations remain available.
No new V2 API surface was added for this conversion.
