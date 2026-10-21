LoRA Manager rev 9: the Lora Info node's frontend and its 3 declared routes (port r1), tested by Tier R test r3 on the a2 base (core a2 d1a9259, backend a1 894ead3).

Status `PASS_TIER_R` (selection `m_e5bafbe525`, one attempt, run by MERVYN; 02:55:32-02:56:34Z). The data-only intake (`INTAKE.json`) re-verified the receipt, the bound spec, pins and launcher, the container limits (uid 1000, no capabilities, memory gate), the stand-in hash and labels, and every result section.

Live behaviour, with no stand-in (`RESULTS_COMPACT.json`, `platform_gap_controls`): on the unmodified a1 backend each of the 3 routes is refused with "no active execution for this guest". A route call gets no execution runtime, so its first `assets` call fails. Platform request #15 asks the host to bind one (`PLATFORM_REQUEST_15_ROUTE_RUNTIME.md`).

Parity, under a stand-in: every other row ran with a test-harness stand-in that binds a runtime to each route call (`STAND_IN.json`: its exact code and sha256 `a8a0d17d95fd24057ad1c096870323eb27e6c582fc2407e2049943bf857baad3`; label "parity under a harness stand-in for platform request #15 (not live behaviour)"; not part of the pack). Against the original's own handler and service code on synthetic sidecars: notes 15/16 equal plus 1 recorded difference (duplicate stems), descriptions 11/11, save and read-back 16/16. Frontend logic: 29 checks against a fake of the live guest API (Node.js, no browser).

Deliberate and other differences: `PORT_NOTES.json`. Manifest change, route decoding and the guest-member audit (no `getProperties`, only members the live guest implements): `STATIC_CHECKS.json`.

Not established: live route behaviour (needs request #15), a browser run (BART's smoke plan `BROWSER_SMOKE_PLAN.md` waits for #15; its workflow fixture stays with the test packet), the sandbox, a LoRA selection source on live (request #11), and whole-node certification. Two earlier attempts failed in the test harness and in the run image, not in the port (`ATTEMPTS.json`).

Paths: the original returns absolute file paths; inside the test container they are shown here as `<fixture-root>/...`.
