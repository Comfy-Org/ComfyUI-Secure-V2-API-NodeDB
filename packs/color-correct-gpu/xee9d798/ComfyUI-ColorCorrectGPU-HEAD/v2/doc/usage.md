# Usage

Connect an 'IMAGE' and adjust temperature, hue, brightness, contrast,
saturation, and gamma. The output remains an 'IMAGE'; RGB corrections affect
the first three channels and an alpha channel, when present, is preserved.

The adjustment order matches the pinned upstream implementation:
brightness, contrast, temperature, gamma, saturation, then hue.
