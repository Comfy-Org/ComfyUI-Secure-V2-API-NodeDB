# Color Correct GPU — Secure Nodes V2

This conversion preserves the 'ColorCorrectGPU' node and its complete
temperature, hue, brightness, contrast, saturation, and gamma pipeline.

The implementation runs in the isolated Secure Nodes guest. Image tensors cross
the boundary only through the declared 'raw' compute tier, and the outer
executor restores the declared 'IMAGE' type.

See [SECURE_CONVERSION.md](SECURE_CONVERSION.md) for the security boundary and
[doc/usage.md](doc/usage.md) for usage details.
