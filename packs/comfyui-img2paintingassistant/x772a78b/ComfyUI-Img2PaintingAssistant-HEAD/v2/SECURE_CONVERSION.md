# Secure conversion record

Upstream is pinned at `772a78bb92bd8e8adfdec8af28ce1ac6203e77e5`.

## Census

- Python nodes: 2 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The screenshots and example workflows are inert documentation assets. They do
not add registrations or runtime authority. The pinned `pyproject.toml` names a
`LICENSE` file that is absent at this commit. This conversion records the
upstream packaging defect and does not invent or substitute license text.

## Behavior and authority

`Painting` retains the pinned OpenCV/NumPy/Torch pipeline, including its RGB
and RGBA paths, batch behavior, optional line-art zip semantics,
`correct_black_Img` scaling, filters, sharpening, color adjustments, contrast,
alpha preservation, and output order. `ProcessInspyrenetRembg` retains its
thresholded alpha mask, transparent-background behavior, all 16 selectable
background colors, and mask passthrough. Both schemas preserve node IDs,
display names, input order, optionality, defaults, bounds, steps, output types
and names, and category.

These are pack-specific pixel algorithms, so they remain in the pack's raw
compute tier rather than becoming host operations. The established V2 value
mode materializes only the declared IMAGE/MASK inputs and re-wraps the declared
IMAGE/MASK outputs. Both nodes require `raw` and receive no refs or other
capabilities. They have no filesystem, network, subprocess, storage, route,
frontend, model, or host-global authority.
