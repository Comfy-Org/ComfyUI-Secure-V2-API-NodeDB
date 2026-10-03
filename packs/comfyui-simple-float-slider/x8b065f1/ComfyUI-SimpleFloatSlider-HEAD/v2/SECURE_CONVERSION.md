# Secure Nodes V2 conversion

Upstream: `https://github.com/Carasibana/ComfyUI-SimpleFloatSlider`

Pinned commit: `8b065f1cd57d05e949fa8925860fb349c5f94ebb`

All three Python nodes and the frontend extension are supported. Node IDs,
schemas, scalar clamping, integer conversion, and Python rounding behavior are
preserved.

The legacy extension injected page-global CSS, replaced node prototypes, and
mutated LiteGraph's widget array. The conversion uses `comfy.defs.extend`, a
pack-owned mounted widget, typed widget handles, and lifecycle hooks. The
mounted control occupies the original `value` serialization and prompt slot;
configuration widgets remain normal host controls and are hidden or revealed
through their handles.

Typed off-grid values remain exact across workflow restoration. Dragging and
scrolling step from the current value, while changing the step setting
deliberately re-grids from the configured minimum. Temporary bounds clamp only
the displayed value, retaining the authored raw value so widening the range
restores it.

There are no deliberate behavior gaps and no frontend permissions.
