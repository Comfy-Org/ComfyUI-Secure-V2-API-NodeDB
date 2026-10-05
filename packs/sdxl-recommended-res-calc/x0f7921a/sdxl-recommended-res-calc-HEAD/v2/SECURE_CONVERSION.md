# Secure conversion record

Upstream is pinned at `0f7921a4e70e8288c027302472dc9a5d70804c12`.

## Census

- Python nodes: 1 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The repository also contains standalone command-line and AUTOMATIC1111 scripts.
Neither is imported by the ComfyUI package, so both remain pristine source and
are outside the registered runtime census.

The pinned repository's `pyproject.toml` names `LICENSE`, but that file is not
present at the pinned commit. The conversion records that upstream packaging
defect and does not invent or substitute license text.

## Behavior and authority

`RecommendedResCalc` preserves the pinned 41-entry SDXL resolution table, its
ordered nearest-ratio selection, nine-decimal scale rounding, output names and
input schema. The source permits a zero height and raises `ZeroDivisionError`
when it is executed; the V2 node deliberately retains that observable edge
instead of silently changing it.

The node is deterministic scalar math and declares no permissions. It has no
tensor, model, file, network, subprocess, storage, UI, route, or host-global
authority.
