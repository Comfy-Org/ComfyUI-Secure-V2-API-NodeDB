# Ovi bf16 cross diagnostic r1 (WSL x86 CPU): a diagnostic finding, not a parity PASS

One selected attempt (m_f599abfab8) of packet wan-ovi-cross-r1 (a090205f, CONFIG 1d652215) ran one bounded Linux container on WSL
CPU (image e48accf7, one thread, uid/gid 1000, no capabilities, no network, read-only root, memory = swap = 6 GiB). Both trees were
mounted; one interpreter held the original and the converted Ovi decoders. Stages S0 (minimal), S1 (+ full original package) and S2
(+ converted-site and the full converted package); each stage decoded the same bf16 latent with both models, outside and inside an
SDK dispatch scope, twice each.

DIAGNOSIS cfd0bcdf: verdict PROCESS_STATE. All 24 decoder outputs equal the wsl r1 ORIGINAL bf16 decoder output (8616d26a); both full
nodes at S2 gave the wsl r1 ORIGINAL waveform (c31fc291); model dumps, per-module traces and oneDNN summaries are identical.
INTAKE_REVIEW.json (36 checks) recomputed DIAGNOSIS.json byte-identically. HASH_BINDING.json binds the evidence to the staged bytes.

Report label: fp32 exact across separate processes; bf16 bit-exact with the original in one interpreter (cross r1), while separate processes can differ by process-level numeric state (wsl r1: max_abs 0.287 on the waveform), not converted code.
