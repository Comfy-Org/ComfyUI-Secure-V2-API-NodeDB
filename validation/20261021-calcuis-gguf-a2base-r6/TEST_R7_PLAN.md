# calcuis-gguf test r7 (rev 5, port r7): Tier H, handle_tensors parity

MERVYN m_e5429491e6: the changed `loading` sits in GGUFSave and GGUFRun's path. Under the exact-bytes rule both rows need
it run before rev 5 publishes. Tiers A, B and Q (test r6) never execute `encoding_math.handle_tensors`.

One in-process attempt (launcher r3, 3 GiB = swap, 240 s, uid 1000, no network). Mounts are as test r6; only /driver is new.
- **rev 4:** /pack-v2 as published (encoding_math eacafdee), with the image's real tqdm.
- **rev 5:** /pack-v2 plus the port r7 leaf (encoding_math d1c4f6ca), imported and run with `sys.modules['tqdm'] = None`.
- Both are package shells: their `__init__.py` (nodes, comfy_api) is not executed.

Cases H1-H4 run `conversion_artifact.prepare_conversion` on identical fresh states (alpha and zero). Each compares the
full GGUF bytes, the filename, the stdout text and the Python warnings raised outside tqdm, and checks every per-tensor line against an
independent oracle of the qtype rule. H2 and H4 inject one QuantError, so both `loading.write` sites run:
- the `falling back to F16` line (rev 4 :91, rev 5 :108);
- the per-tensor line (rev 4 :96, rev 5 :113).

The fallback cannot be reached naturally (STATIC_CHECKS_TEST_R7.json `fallback_reachability`). stderr is recorded:
rev 4 must show a tqdm bar and rev 5 none, which is the documented no-progress-bar difference.

If it passes, the GGUFSave and GGUFRun rows say their conversion loop was re-run on the rev 5 bytes with tqdm absent
(Tier H), with the fallback reached by an injected error.
