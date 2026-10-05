# Secure Nodes V2 conversion

Pinned upstream: `770d7b8e4104b8d864d1fed0a65713e4a3e7a953`.

The four registered nodes retain their exact IDs, schemas, display names, and
SIGMAS behavior. Model-backed nodes use the bounded public
`ModelRef.sigma_for_percent()` projection and all nodes materialize outputs
through public `SigmasRef.from_values()` with no ambient authority.

The twelve import-time global scheduler mutations are replaced by declarative
`scheduler_providers`. Their NumPy/SciPy algorithms remain pack-owned and run
in a fresh confined guest over bounded scalar model-sigma projections. The pack
does not access files, the network, subprocesses, host objects, or private SDK
constructors.
