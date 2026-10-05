# Secure conversion report

- Upstream: `https://github.com/theshubzworld/ComfyUI-Universal-Latent`
- Pinned commit: `1281586aba8861acbcc815b30386d354e0a7798d`
- Python census: **1 supported, 0 rejected, 0 pending**
- Frontend census: **0 extensions, 0 JS-only nodes**
- Routes: **0**

`UniversalLatent` retains its node ID, display name, category, complete input
schema, output contract, ordered preset catalogue, rounding, overrides,
aspect-lock behavior, ratio inversion, channel selection, and downsample
selection. The legacy direct Torch allocation is replaced with the public,
bounded `sdk.LatentRef.empty` operation.

The declared legacy batch range is preserved for workflow/schema parity. The
secure allocator additionally enforces its global allocation bounds (including
a maximum batch of 64 and a 16,777,216-element latent limit), so requests that
could create unreasonable allocations fail closed before allocation.

The pinned repository declares an MIT `LICENSE` in `pyproject.toml` but does not
contain the referenced license file. This conversion does not invent missing
upstream license text.
