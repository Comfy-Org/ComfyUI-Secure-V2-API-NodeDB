# Secure conversion evidence

This is a source revision of the existing one-node SDXLAspectRatio conversion.
Upstream is throttlekitty/SDXLCustomAspectRatio at
4a0bbec07134768324b49f14b2fa7f3bee66f0ba (x4a0bbec).
All four original files, Git blobs and 100644 modes match the independently
verified upstream tree b3ed5dca5cca67ca017a28d053190f2baa86bd19.
The upstream metadata references an absent license file; no terms are invented.

The schema retains the image category, 28 ordered presets and Width/Height INT
outputs. Value mode and zero permissions remain. The original algorithm.py is
byte-identical to the upstream module, including CRLF. The converted nodes.py
uses the reviewed decimal-run-boundary regex (?<!\d)(\d+)\s*[xX]\s*(\d+).
An earliest successful original match already begins at a digit-run boundary;
the constraint avoids repeated interior starts without changing match groups,
integer-conversion order or the 1024/1024 fallback. Existing 64 KiB UTF-8 and
signed-64-bit output guards remain; native integer-string errors are retained.

The single selected native Mac R3 attempt passed 548 pristine/registered-SDK
comparisons, nine declared guard refusals, one schema, 20,633 exact regex full-
and group-span/text differentials, normal manifest generation, canonical pair
and ZIP replays, wrong-expected and changed-base controls. Its 24 long repaired-
SDK cases are completion/refusal evidence only: every row has parity_proved=false.
The preceding R2 run remains INCOMPLETE_REGEX_TIME_BUDGET_NOT_PARITY because
both original and old converted parser exceeded one second at 16K/64K no-x
inputs. Those original calls were not repeated or relabeled observed parity.

R3 archive SHA256 d6fe4dff28fc2f2c66fd671c1fbe752d625f7e831f8eea31d0859da989ea607d.
Independent intake SHA256 212a68316741ff9405dcc2183ee4e0666698b4e094b3ee85f7a635127ee47876.
Native runtime: Python 3.13.14, API 0.42.0, Core
44564d0279c275eef52b11750a9d76349f4e7a88, backend
59bd3e1acba6520bb32717ad03833f6ab2967ecc. Actual duration 2.727 seconds;
observed aggregate peak RSS 359,317,504 bytes under a 1 GiB watchdog, not a hard
quota. Both owned process groups were independently absent after cleanup.
Input/runtime/full-site maps were unchanged; configuration equality is an
operator assertion with verified script provenance, not independent config bytes.

The genuine R3-generated secure-nodes.json is retained without regeneration.
Only this evidence document changed after the run. Canonical file-only packaging
and two fresh pristine replays verify final source bytes and explicit 100644
modes. No new SDK/node/manifest-generator execution occurred during handoff.

The retained historical pytest file and older 42-test log are reference material;
older prose claiming 79 tests or 82 Guest executions is not current qualification.
This receipt does not prove Guest, shared TEST, managed deployment, service or
whole installed readiness. No model inference, durable state or new SDK API is
required. Root owns publication review and the final Git change.
