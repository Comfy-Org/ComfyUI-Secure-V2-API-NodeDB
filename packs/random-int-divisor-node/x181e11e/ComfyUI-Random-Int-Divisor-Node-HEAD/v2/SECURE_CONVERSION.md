# Secure Nodes V2 conversion

Upstream: <https://github.com/Jaminanim/ComfyUI-Random-Int-Divisor-Node>

Pinned commit: `181e11e74a5b75bb43ca54604ddc2858e6a405d6`

Release: `x181e11e`

## Census

- Backend: 3 supported, 0 rejected, 0 pending.
- Frontend, routes, settings, dependencies, and model weights: none.

The actual pinned package entrypoint exports `RandomIntegerNodeEfficient`,
`RandomIntegerNodeList`, and `RandomIntegerNodeEfficientAdvanced`. Their IDs,
display names, categories, schemas, stochastic-per-run behavior, error messages,
and distinct sampling algorithms are preserved.

## Behavior

The two simple nodes retain their efficient index-based and explicit-list
selection algorithms, including negative ranges and divisor validation. The
advanced node retains uniform and Gaussian sampling, multiple divisors,
exclusions, independent-axis controls, aspect-ratio modes, megapixel limiting,
maximum bidirectional ratio limiting, and upstream fallback behavior.

Every node is marked non-idempotent so the host executes it for each run, which
is the V2 equivalent of the pinned `IS_CHANGED = NaN` declarations.

## Security boundary

These are pure scalar nodes. They use only Python's `random` and `math` modules
and declare no Secure Nodes capabilities. They have no filesystem, process,
network, model, tensor, route, storage, frontend, or ambient host authority.
