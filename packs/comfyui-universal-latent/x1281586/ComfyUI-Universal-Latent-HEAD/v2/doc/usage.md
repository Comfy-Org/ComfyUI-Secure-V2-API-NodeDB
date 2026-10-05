# Usage

Choose a resolution preset, batch size, channel count, and downsample factor.
Optional width/height overrides can be applied independently or with the base
aspect ratio locked to one dimension. `invert_ratios` swaps the resolved width
and height.

The width and height outputs are the actual pixel dimensions represented by
the latent. Inputs that are not divisible by the chosen factor round upward to
the next latent cell, matching the pinned implementation.

Secure execution intentionally rejects allocations outside the host's bounded
latent limits before memory is allocated.
