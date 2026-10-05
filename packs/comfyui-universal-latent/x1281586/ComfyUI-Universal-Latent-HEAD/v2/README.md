# ComfyUI Universal Latent — Secure Nodes V2

This conversion preserves the pinned pack's 72 resolution presets, aspect-lock
and override rules, ratio inversion, latent-channel choice, downsample choice,
and represented width/height outputs.

The node runs without filesystem, network, model, raw-tensor, or frontend
authority. It creates the zero latent through the bounded public
`LatentRef.empty` API.

See [SECURE_CONVERSION.md](SECURE_CONVERSION.md) for the census and security
boundary and [doc/usage.md](doc/usage.md) for usage details.
