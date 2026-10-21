ControlNet Aux revision 3 (docs only): live selection status. Static, read from the published tree at corpus f66757d8; nothing was run and no file other than the report changed.

`SELECTION_GATES.json` lists, for each gated family:
- the gate module, its sha256 and every approval check (line and text);
- the selection file, its sha256 and its approval flags.

It also lists the approved selections on main (DSINE, BAE, OpenPose), the AIO dispatch line, and ExecuteAll's unconditional raise.

Eight nodes counted as tested (scoped) refuse on live because their published selections are `approved: false`: DepthAnythingV2Preprocessor, DWPreprocessor, AnimalPosePreprocessor, DensePosePreprocessor, LeReS-DepthMapPreprocessor, MiDaS-DepthMapPreprocessor, MiDaS-NormalMapPreprocessor, Unimatch_OptFlowPreprocessor. Four pending-capability nodes are blocked the same way: UniFormer-SemSegPreprocessor, SemSegPreprocessor, Metric3D-DepthMapPreprocessor, Metric3D-NormalMapPreprocessor. All 12 wait on request #21.
