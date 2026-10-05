# ComfyUI Simple Switch — Secure Nodes V2

This secure conversion preserves all four registered switch nodes and their
six-input priority order. Values and latent handles are returned unchanged.

Audio and video latent discrimination runs in the isolated guest through the
declared `raw` capability because both subtypes share the public `LATENT` wire
type. The guest reads only the bounded latent structure needed to distinguish
4D audio, nested AV, and 5D video samples. It has no file, network, model,
storage, subprocess, UI, or host-global authority.
