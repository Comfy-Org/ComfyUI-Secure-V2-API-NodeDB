calcuis-gguf rev 5 (loader port r7, tests r6 and r7): actual result of the selected Tier A, B and Q attempts and the Tier H attempt on the "a2 base" (deployed ComfyUI 6257422 plus the undeployed GGML SDK a2 d1a9259, backend a1 894ead3), with tqdm absent from the converted role, as on the live guest.

Status `PASS_TIER_A`, `PASS_TIER_B`, `PASS_TIER_Q` (selection `m_efc6892dd4`, one attempt each, no retry, run by MERVYN under the shared lock). Launcher r3 ran each container as uid 1000 with no capabilities and a memory gate. Every mount was checked against the bound pins before each container was created (`TIER_*_PINS_CHECK.json`). Tier A ran 04:49:00-04:49:20Z, Tier B 04:49:26-04:49:42Z and Tier Q 04:49:47-04:50:02Z; none timed out or hit OOM. The data-only intake (`INTAKE.json`) re-verified every receipt hash and the Windows mirror. It also checked the bound spec, the launcher and pins copies, and the sealed zips against the pinned mounts. Then it checked the container limits and every result section.

What revision 5 changes: `encoding_math.py` no longer imports tqdm (a local stand-in iterates unchanged and prints tqdm.write's lines). The live guest has no tqdm, so revisions 1-4 failed to import there (`IMPORT_CLOSURE_MAIN.json` vs `IMPORT_CLOSURE_R7.json`; the diff is `PORT_R6_TO_R7.patch`).

How tqdm was kept out of the converted role:
- Tier A imported the converted package and all 17 mutants with `sys.modules['tqdm'] = None` (19 blocked imports). No converted module held a tqdm object.
- The control T0 imported the published revision-4 `encoding_math.py` under the same block. It raised `ModuleNotFoundError` naming tqdm, which is the live failure.
- Every Tier B and Tier Q guest started with a tqdm package that raises ImportError first on its PYTHONPATH (1 guest each).
- The original and the host kept tqdm, as on the live host.

Every result section equals the published revision-4 run, compared section by section: 800 bit-exact dequantization cells, construction-call parity for the six loaders, the qwen/cat rows, the load-order record, 17 mutants each caught by its intended check, queue validation for all 13 nodes, and manifest rows.

Tier H (`PASS_TIER_H`, selection `m_9748951bda`, one attempt, 20:40:35-20:40:39Z; intake `INTAKE_TIER_H.json`, CLEAN) covers the only code that used tqdm. It is GGUFSave and GGUFRun's conversion loop, `encoding_math.handle_tensors` through `prepare_conversion`, and it ran in process on identical states (alpha and zero):
- revision 4 with the real tqdm;
- revision 5 with tqdm absent.
The full GGUF bytes, the filenames, the stdout lines and the warnings are identical. Both `loading.write` sites ran. The F16 fallback cannot be reached naturally (BF16 has block size 1), so one QuantError was injected in both revisions. Revision 4 drew a tqdm bar on stderr and revision 5 none, which is the recorded no-progress-bar difference (`TEST_R7_PLAN.md`, `STATIC_CHECKS_TEST_R7.json`).

Not established: the live guest itself; the Phase-1 publication of the GGUF bytes (`output.save_binary`); real model loads; LoRA patching; the deployed host; the sandbox; GPU; and whole-pack, registry, service or browser use.

Node classes are unchanged: 7 tested (scoped) and 6 converted but partly tested (`NODE_CLASSES_PROPOSED.json`, with a `live` line per node). `v2/SECURE_CONVERSION.md` was refreshed after testing (docs-only); it is the only staged byte that differs from the tested tree. Applying the regenerated pair to a fresh pristine copy re-creates the staged tree exactly. Raw RESULT/stdout/stderr files are retained locally (hashes in `RAW_RESULTS_RETAINED.json`). Paths here are workspace-relative.
