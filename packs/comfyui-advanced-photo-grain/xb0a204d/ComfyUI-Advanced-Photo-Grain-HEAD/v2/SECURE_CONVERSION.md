# Secure conversion record

Upstream is pinned at `b0a204d910a0025d8ba4b53b01df831861cf8241`.

## Census

- Python nodes: 2 supported, 0 rejected, 0 pending.
- Frontend extensions: 0.
- Backend routes: 0.
- JavaScript-only nodes: 0.

The census was established through ComfyUI's actual custom-node loader. The
upstream `pyproject.toml` names `LICENSE.txt`, while the pinned repository ships
the GPL text as `LICENSE`; the secure package points at the file that actually
exists without altering its contents.

## Behavior and authority

`PhotoFilmGrain` preserves Gaussian, Poisson, and fractal noise, channel
saturation mixing, adaptive shadow gain, halation, radial lens distortion,
vignette, chromatic aberration, batching, clamps, and stochastic use of the
ordinary Torch random stream. It does not reseed or otherwise mutate the
process-global generator beyond consuming random samples exactly as upstream
does. `FreqSeparationSharpen` preserves its separable Gaussian blur,
frequency-gain modes, smooth threshold transition, halo limiter, identity fast
path, batches, shapes, and output order.

Both nodes are pack-specific tensor algorithms and remain in the pack under the
permissioned raw-compute tier. Public V2 value mode materializes only their
declared IMAGE input and returns the resulting IMAGE tensor through the normal
outer executor. They receive no filesystem, network, subprocess, storage,
model, route, frontend, or host-global authority. The legacy
`comfy.model_management` calls only selected host devices; isolated execution
instead computes on the guest's managed Torch device and returns the same
declared values.
