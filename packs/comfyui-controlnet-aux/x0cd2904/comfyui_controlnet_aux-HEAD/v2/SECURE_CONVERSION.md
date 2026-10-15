> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 64 of 64 converted; 39 tested (scoped), 4 converted but untested/partly tested,
> 21 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.
> (The 21 are converted in source but pending capability: 20 need original checkpoints staged and a model-load test; FaceMesh needs `mediapipe`.)

# ControlNet Aux — secure conversion report (in progress)

## Provenance

- Upstream: https://github.com/Fannovel16/comfyui_controlnet_aux
- Pinned commit: `0cd290477128d42cdc3e76a826a402d866e8c684` (key `x0cd2904`, tree `4f98bb6e32b99c4f8110bb7b4e4f24f7d2ec1760`)
- Converted tree: integrated candidate `full1613` (FaceMesh private-import fix), packaged unchanged except: model files excluded (below), private host paths in test helpers redacted, and this report updated.
- Mirror mode: original node ids, display names and categories; no `-Secure` suffixes.

## Per-node status (2026-10-15)

Dispositions: **tested** = scoped behavior evidence on the registered node; **converted-untested** / **partial** = source converted, positive behavior not (fully) tested; **pending-capability** = source converted but blocked on a capability (checkpoints, dependency).

| Node id | Display name | Disposition | Evidence or gap |
| --- | --- | --- | --- |
| AIO_Preprocessor | AIO Aux Preprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `aio-shared-and-full-cli-original-dispatch-pass-r2` |
| AnimalPosePreprocessor | AnimalPose Estimator (AP10K) | pending-capability | Needs original checkpoint(s): bbox `yolox_l.torchscript.pt` / `yolox_l.onnx` (or `yolo_nas_{l,m,s}_fp16.onnx`) + pose `rtmpose-m_ap10k_256_bs5.torchscript.pt` / `rtmpose-m_ap10k_256.onnx`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| AnimeFace_SemSegPreprocessor | Anime Face Segmentor | pending-capability | Needs original checkpoint(s): `Annotators/UNet.pth` + `isnetis.ckpt` + torchvision `mobilenet_v2-b0353104.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| AnimeLineArtPreprocessor | Anime Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anime-shared-and-full-cli-original-model-pass-r1` |
| AnyLineArtPreprocessor_aux | AnyLine Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `anyline-shared-and-full-cli-original-model-pass-r2` |
| BAE-NormalMapPreprocessor | BAE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `bae-shared-and-full-cli-original-model-pass-r1` |
| BinaryPreprocessor | Binary Lines | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| CannyEdgePreprocessor | Canny Edge | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ColorPreprocessor | Color Pallete | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| ControlNetAuxSimpleAddText | ControlNetAuxSimpleAddText | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| ControlNetPreprocessorSelector | Preprocessor Selector | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| DensePosePreprocessor | DensePose Estimator | pending-capability | Needs original checkpoint(s): `densepose_r50_fpn_dl.torchscript` (option `densepose_r101_fpn_dl.torchscript`). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DepthAnythingPreprocessor | Depth Anything | pending-capability | Needs original checkpoint(s): `depth_anything_vitl14.pth` (vitb14/vits14 options); managed bundles LiheYoung/depth-anything-{large,base,small}-hf. Source converted; fails closed until assets are staged and a model-load test is approved. |
| DepthAnythingV2Preprocessor | Depth Anything V2 - Relative | pending-capability | Needs original checkpoint(s): `depth_anything_v2_vit{s,b,l}.pth` (depth-anything/Depth-Anything-V2-*); selected test asset `depth_anything_v2_vits.pth` (99.2 MB). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DiffusionEdge_Preprocessor | Diffusion Edge (batch size ↑ => speed ↑, VRAM ↑) | pending-capability | Needs original checkpoint(s): `diffusion_edge_{indoor,urban,natrual}.pt` + `swin_b-68c6b09e.pth` + `vgg16-397923af.pth` + LPIPS `vgg.pth` (upstream-tracked; excluded from v2). Source converted; fails closed until assets are staged and a model-load test is approved. |
| DSINE-NormalMapPreprocessor | DSINE Normal Map | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `dsine-shared-full-cli-original-member-model-pass-r4` |
| DWPreprocessor | DWPose Estimator | pending-capability | Needs original checkpoint(s): bbox `yolox_l.onnx` (or torchscript / yolo_nas variants) + pose `dw-ll_ucoco_384_bs5.torchscript.pt` / `dw-ll_ucoco_384.onnx`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| ExecuteAllControlNetPreprocessors | Execute All ControlNet Preprocessors | converted-untested | Runs every child preprocessor; a full positive run needs every child checkpoint. Canonical 68-schema regeneration in progress (pinned SDK adds `Schema.loop_boundary`); the lazy raw-link ExecuteAll successor (R114) is NOT in this tree. |
| FacialPartColoringFromPoseKps | Colorize Facial Parts from PoseKPS | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| FakeScribblePreprocessor | Fake Scribble Lines (aka scribble_hed) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1` |
| HEDPreprocessor | HED Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `hed-shared-and-full-cli-original-model-pass-r1` |
| HintImageEnchance | Enchance And Resize Hint Images | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromImage | Generation Resolution From Image | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageGenResolutionFromLatent | Generation Resolution From Latent | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageIntensityDetector | Image Intensity | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ImageLuminanceDetector | Image Luminance | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| InpaintPreprocessor | Inpaint Preprocessor | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| LeReS-DepthMapPreprocessor | LeReS Depth Map (enable boost for leres++) | pending-capability | Needs original checkpoint(s): `res101.pth` + pix2pix `latest_net_G.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| LineArtPreprocessor | Realistic Lineart | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `lineart-shared-and-full-cli-original-model-pass-r1` |
| LineartStandardPreprocessor | Standard Lineart | tested | Scoped typed native pass (non-model controls) — evidence: `four-image-nodes-r1` |
| M-LSDPreprocessor | M-LSD Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `mlsd-shared-and-full-cli-original-model-pass-r1` |
| Manga2Anime_LineArt_Preprocessor | Manga Lineart (aka lineart_anime_denoise) | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `manga-shared-and-full-cli-original-model-pass-r1` |
| MaskOptFlow | Mask Optical Flow (DragNUWA) | tested | Scoped typed native pass (non-model controls) — evidence: `flow-font-and-complete-source-r1` |
| MediaPipe-FaceMeshPreprocessor | MediaPipe Face Mesh | pending-capability | Needs the `mediapipe` dependency (not in the current 40-wheel private profile); its face-landmark model ships inside mediapipe. Private-core import fix is in this tree; constructor and positive behavior untested. |
| MeshGraphormer+ImpactDetector-DepthMapPreprocessor | MeshGraphormer Hand Refiner With External Detector | pending-capability | Needs original checkpoint(s): everything MeshGraphormer needs + an Impact-Pack detector (external pack integration). Source converted; fails closed until assets are staged and a model-load test is approved. |
| MeshGraphormer-DepthMapPreprocessor | MeshGraphormer Hand Refiner | pending-capability | Needs original checkpoint(s): `graphormer_hand_state_dict.bin` + `hrnetv2_w64_imagenet_pretrained.pth` + `hand_landmarker.task` + MANO/SMPL modeling data (upstream-tracked; excluded from v2). Source converted; fails closed until assets are staged and a model-load test is approved. |
| Metric3D-DepthMapPreprocessor | Metric3D Depth Map | pending-capability | Needs original checkpoint(s): `metric_depth_vit_small_800k.pth` (vit-large / vit-giant2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| Metric3D-NormalMapPreprocessor | Metric3D Normal Map | pending-capability | Needs original checkpoint(s): `metric_depth_vit_small_800k.pth` (vit-large / vit-giant2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| MiDaS-DepthMapPreprocessor | MiDaS Depth Map | converted-untested | Original Intel/dpt-hybrid-midas `pytorch_model.bin` (489.6 MB) cached; native forward and gVisor import/reader pass; learned guest forward approved, not yet run. |
| MiDaS-NormalMapPreprocessor | MiDaS Normal Map | converted-untested | Same model and gates as MiDaS-DepthMapPreprocessor. |
| OneFormer-ADE20K-SemSegPreprocessor | OneFormer ADE20K Segmentor | pending-capability | Needs original checkpoint(s): `250_16_swin_l_oneformer_ade20k_160k.pth`; managed bundle shi-labs/oneformer_ade20k_swin_large. Source converted; fails closed until assets are staged and a model-load test is approved. |
| OneFormer-COCO-SemSegPreprocessor | OneFormer COCO Segmentor | pending-capability | Needs original checkpoint(s): `150_16_swin_l_oneformer_coco_100ep.pth`; managed bundle shi-labs/oneformer_coco_swin_large. Source converted; fails closed until assets are staged and a model-load test is approved. |
| OpenposePreprocessor | OpenPose Pose | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `openpose-original7-HTTP-full1591-CLI-scoped-pass-r5` |
| PiDiNetPreprocessor | PiDiNet Soft-Edge Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1` |
| PixelPerfectResolution | Pixel Perfect Resolution | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| PyraCannyPreprocessor | PyraCanny | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| RenderAnimalKps | Render Pose JSON (Animal) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| RenderPeopleKps | Render Pose JSON (Human) | tested | Scoped typed native pass (non-model controls) — evidence: `pose-three-nodes-and-profile-r1` |
| SAMPreprocessor | SAM Segmentor | pending-capability | Needs original checkpoint(s): `mobile_sam.pt`; managed effective default facebook/sam-vit-base. Source converted; fails closed until assets are staged and a model-load test is approved. |
| SavePoseKpsAsJsonFile | Save Pose Keypoints | tested | Scoped original managed-output pass on shared HTTP and full-source CLI — evidence: `savepose-shared-full-cli-original-json-scoped-pass-r4` |
| Scribble_PiDiNet_Preprocessor | Scribble PiDiNet Lines | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `pidinet-full-cli-original-model-pass-r1` |
| Scribble_XDoG_Preprocessor | Scribble XDoG Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| ScribblePreprocessor | Scribble Lines | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| SemSegPreprocessor | Semantic Segmentor (legacy, alias for UniFormer) | pending-capability | Needs original checkpoint(s): `upernet_global_small.pth` (UniFormer). Source converted; fails closed until assets are staged and a model-load test is approved. |
| ShufflePreprocessor | Content Shuffle | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TEEDPreprocessor | TEEDPreprocessor | tested | Scoped original-model pass on shared HTTP and full-source CLI (original checkpoint exercised) — evidence: `teed-shared-and-full-cli-same-runtime-original-model-pass-r2` |
| TilePreprocessor | Tile | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileGF_Preprocessor | TTPlanet Tile GuidedFilter | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| TTPlanet_TileSimple_Preprocessor | TTPlanet Tile Simple | tested | Scoped typed native pass (non-model controls) — evidence: `nineteen-nodes-r1` |
| UniFormer-SemSegPreprocessor | UniFormer Segmentor | pending-capability | Needs original checkpoint(s): `upernet_global_small.pth`. Source converted; fails closed until assets are staged and a model-load test is approved. |
| Unimatch_OptFlowPreprocessor | Unimatch Optical Flow | pending-capability | Needs original checkpoint(s): `gmflow-scale2-regrefine6-mixdata.pth` (scale1 / scale2 options). Source converted; fails closed until assets are staged and a model-load test is approved. |
| UpperBodyTrackingFromPoseKps | Upper Body Tracking From PoseKps (InstanceDiffusion) | partial | Only limited empty / disabled / excluded tracking cases tested; full positive tracking cases open. |
| Zoe-DepthMapPreprocessor | Zoe Depth Map | pending-capability | Needs original checkpoint(s): `ZoeD_M12_N.pt`; managed bundle Intel/zoedepth-nyu-kitti. Source converted; fails closed until assets are staged and a model-load test is approved. |
| Zoe_DepthAnythingPreprocessor | Zoe Depth Anything | pending-capability | Needs original checkpoint(s): `depth_anything_metric_depth_{indoor,outdoor}.pt` (LiheYoung/Depth-Anything metric checkpoints). Source converted; fails closed until assets are staged and a model-load test is approved. |

### Test-only fixture nodes removed

The integrated candidate also registered two non-original MiDaS comparison fixtures (`AMY_Aux_MIDAS_Native_Input_R1`, `AMY_Aux_MIDAS_Same_Runtime_Original_Consumer_R1`). They, their entrypoint wrapper and the files that existed only for them (`_test_midas_first_fixture.py`, `_midas_first_original_native_golden.json`, `_test_midas_config.json`, `_test_midas_fixture_inputs.py`, `_test_midas_native_batch.py`, `_test_midas_native_detector.py`, `_test_midas_processor.json`, `tests/workflows/amy-aux-midas-original-first-r1.json`) are removed from this tree; `v2/__init__.py` now exports the 64-node entrypoint from `nodes.py`, and `secure-nodes.json` was regenerated by the SDK from this exact tree (64 original ids). The fixtures remain in the private test harness outside `v2/`.

## Refused techniques (never-do) and public replacements

| Refused technique | Public replacement in this conversion |
| --- | --- |
| Importing ComfyUI private core (`comfy.*`, `folder_paths`, model management) inside node code | Public `comfy_api.latest` `io` / `sdk` APIs; private-core references confined to test-only `_test_*` reference helpers |
| Downloading checkpoints at run time (Hugging Face Hub / torch.hub / URLs in `from_pretrained`) | Declared, SHA-256-pinned managed weights resolved by the host; no guest network |
| Unrestricted pickle loading of downloaded checkpoints | Managed loaders / restricted state-dict readers bound to pinned bytes |
| Writing files into the pack folder or arbitrary paths (SavePose JSON) | SDK managed `output` capability |
| Reaching into the executing prompt graph directly (ExecuteAll) | Public graph expansion (`enable_expand`) on the SDK node output |

## Pending (not yet supported — needs <capability>)

- 20 model-gated nodes: not yet supported — needs the original checkpoints staged in the managed model store plus an approved model-load test (per-node list above).
- MediaPipe-FaceMeshPreprocessor: not yet supported — needs the `mediapipe` dependency in the pack's private profile.
- MeshGraphormer (both nodes): not yet supported — needs MANO/SMPL modeling data and `hand_landmarker.task` delivered as managed assets (excluded from v2), plus the Impact-Pack detector for the Impact variant.
- ExecuteAllControlNetPreprocessors: canonical manifest regeneration under the current SDK and the lazy raw-link stage successor are not yet in this tree.

## Open test gates

- MiDaS learned guest forward (approved CPU-only run, not yet executed).
- ExecuteAll canonical 68-schema discovery (debug run: 60/66 retained schemas match after the SDK `loop_boundary` field; 6 still under investigation).
- SavePose empty-list error case on the registered node (prepared, not run).
- FaceMesh constructor and positive behavior; UpperBodyTracking full positive cases.
- All 20 model-gated families (checkpoint staging plan to be sent to the manager first).
- Whole-pack acceptance and normal registry publication: not started.

## Authority / permissions

| Permission set | Nodes |
| --- | --- |
| `raw` | 45 (AnimalPosePreprocessor, BinaryPreprocessor, CannyEdgePreprocessor, ColorPreprocessor, ControlNetAuxSimpleAddText, DWPreprocessor, …) |
| `raw`, `assets`, `models.download` | 15 (AnimeLineArtPreprocessor, AnyLineArtPreprocessor_aux, BAE-NormalMapPreprocessor, DSINE-NormalMapPreprocessor, FakeScribblePreprocessor, HEDPreprocessor, …) |
| `raw`, `assets` | 1 (AnimeFace_SemSegPreprocessor) |
| `assets`, `output` | 1 (SavePoseKpsAsJsonFile) |
| `raw`, `assets`, `models.download`, `output` | 1 (AIO_Preprocessor) |
| (none) | 1 (ControlNetPreprocessorSelector) |

## Assets / weights required (never committed)

Declared managed weights already in the canonical manifest (tested nodes):

| Node id | Declared weights |
| --- | --- |
| AIO_Preprocessor | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013); `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6); `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c); `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725); `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |
| AnimeLineArtPreprocessor | `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf) |
| AnyLineArtPreprocessor_aux | `Anyline/MTEED.pth` (TheMistoAI/MistoLine, sha256 a3c2d8a8ce94); `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061); `netG.pth` (lllyasviel/Annotators, sha256 ccabdcc3f5cf); `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| BAE-NormalMapPreprocessor | `scannet.pt` (lllyasviel/Annotators, sha256 03dbf1600c51) |
| DSINE-NormalMapPreprocessor | `dsine.pt` (hr16/Diffusion-Edge, sha256 629472c66ea9) |
| FakeScribblePreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| HEDPreprocessor | `ControlNetHED.pth` (lllyasviel/Annotators, sha256 5ca93762ffd6) |
| LineArtPreprocessor | `sk_model.pth` (lllyasviel/Annotators, sha256 c686ced2a666); `sk_model2.pth` (lllyasviel/Annotators, sha256 30a534781061) |
| M-LSDPreprocessor | `mlsd_large_512_fp32.pth` (lllyasviel/Annotators, sha256 5696f168eb2c) |
| Manga2Anime_LineArt_Preprocessor | `erika.pth` (lllyasviel/Annotators, sha256 badbd6baf013) |
| MiDaS-DepthMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| MiDaS-NormalMapPreprocessor | `pytorch_model.bin` (Intel/dpt-hybrid-midas, sha256 b6c4d44f9d96) |
| OpenposePreprocessor | `body_pose_model.pth` (lllyasviel/Annotators, sha256 25a948c16078); `hand_pose_model.pth` (lllyasviel/Annotators, sha256 b76b00d17509); `facenet.pth` (lllyasviel/Annotators, sha256 8beb52e54862) |
| PiDiNetPreprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| Scribble_PiDiNet_Preprocessor | `table5_pidinet.pth` (lllyasviel/Annotators, sha256 80860ac26725) |
| TEEDPreprocessor | `Annotators/7_model.pth` (bdsqlsz/qinglong_controlnet-lllite, sha256 b9037964149c) |

Model-gated nodes need the checkpoints listed in the per-node table. Upstream-tracked model files excluded from `v2/` (still present in the pristine tree):

| File (upstream path) | Bytes |
| --- | --- |
| `src/custom_controlnet_aux/diffusion_edge/taming/modules/autoencoder/lpips/vgg.pth` | 7289 |
| `src/custom_controlnet_aux/mesh_graphormer/hand_landmarker.task` | 7819105 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_extra.npy` | 771808 |
| `src/custom_mesh_graphormer/modeling/data/J_regressor_h36m_correct.npy` | 937168 |
| `src/custom_mesh_graphormer/modeling/data/MANO_LEFT.pkl` | 3447713 |
| `src/custom_mesh_graphormer/modeling/data/MANO_RIGHT.pkl` | 3447679 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_indices.pt` | 21639 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_size.pt` | 173 |
| `src/custom_mesh_graphormer/modeling/data/mano_195_adjmat_values.pt` | 5663 |
| `src/custom_mesh_graphormer/modeling/data/mano_downsampling.npz` | 176509 |
| `src/custom_mesh_graphormer/modeling/data/mesh_downsampling.npz` | 1720359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_indices.pt` | 48423 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_size.pt` | 175 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_adjmat_values.pt` | 12359 |
| `src/custom_mesh_graphormer/modeling/data/smpl_431_faces.npy` | 21128 |

Redacted private host paths in 1 test helper file(s): `_test_openpose_same_runtime_original.py`.

---

## Historical report (retained; superseded by the per-node status above)

<!-- secure-conversion-report-v1 -->
# ControlNet Aux: conversion in progress

Upstream: https://github.com/Fannovel16/comfyui_controlnet_aux
Pin: `0cd290477128d42cdc3e76a826a402d866e8c684`

64 backend IDs; 27 helper drafts, nine previously trained CPU detector drafts and one unexecuted AnyLine composition draft; zero frontend extensions, JS-only nodes or routes. No complete-pack count.

## Backend node dispositions

| Exact node ID | Status | Evidence boundary |
| --- | --- | --- |
| AIO_Preprocessor | pending | Native parameter/default construction and pack-owned async dispatch drafted; selected unimplemented detectors remain fail closed; canonical SDK and registered guest proof pending |
| AnimalPosePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| AnimeFace_SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| AnimeLineArtPreprocessor | pending | Trained CPU/guest/outer IMAGE; default512 projected budget excluded, admitted profile/provisioning/device release gates pending |
| AnyLineArtPreprocessor_aux | pending | Four-mode source composition implemented; exact MTEED bytes acquired; native/trained/registered/profile tests not yet run |
| BAE-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| BinaryPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| CannyEdgePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ColorPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ControlNetAuxSimpleAddText | pending | Draft bundled-font annotation; first-image/quantization parity tested, release gate pending |
| ControlNetPreprocessorSelector | pending | Draft exact catalogue/pass-through; zero-capability guest tested, release gate pending |
| DSINE-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DWPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DensePosePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DepthAnythingPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DepthAnythingV2Preprocessor | pending | Model/asset/graph port pending; draft fails closed |
| DiffusionEdge_Preprocessor | pending | Model/asset/graph port pending; draft fails closed |
| ExecuteAllControlNetPreprocessors | pending | Model/asset/graph port pending; draft fails closed |
| FacialPartColoringFromPoseKps | pending | Source pose-coloring CPU pixels through fresh guests and outer IMAGE; no detector inference claim |
| FakeScribblePreprocessor | pending | Trained CPU HED/scribble pixel parity through guests and outer IMAGE; provisioning/device release gates pending |
| HEDPreprocessor | pending | Trained CPU pixel parity through guests and outer IMAGE; provisioning/device release gates pending |
| HintImageEnchance | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageGenResolutionFromImage | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageGenResolutionFromLatent | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageIntensityDetector | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| ImageLuminanceDetector | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| InpaintPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| LeReS-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| LineArtPreprocessor | pending | Trained fine/coarse CPU/guest/outer IMAGE; provisioning/device release gates pending |
| LineartStandardPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| M-LSDPreprocessor | pending | Trained source-wrapper CPU/guest/outer pixel parity; provisioning/device release gates pending |
| Manga2Anime_LineArt_Preprocessor | pending | Trained pinned CPU/guest/outer IMAGE; native256 rounding retained, default512 budget excluded, provisioning/profile/device gates pending |
| MaskOptFlow | pending | Exact flow visualization/masking through fresh guests and outer outputs; explicit BHW mask normalization and guest-local alias lifetime, full release gate pending |
| MediaPipe-FaceMeshPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MeshGraphormer+ImpactDetector-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MeshGraphormer-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Metric3D-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Metric3D-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MiDaS-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| MiDaS-NormalMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OneFormer-ADE20K-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OneFormer-COCO-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| OpenposePreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| PiDiNetPreprocessor | pending | Trained source-wrapper CPU/guest/outer pixel parity; provisioning/device release gates pending |
| PixelPerfectResolution | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| PyraCannyPreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| RenderAnimalKps | pending | Source first-frame pose rendering through fresh guests and outer IMAGE; no detector inference claim |
| RenderPeopleKps | pending | Source first-frame pose rendering through fresh guests and outer IMAGE; no detector inference claim |
| SAMPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| SavePoseKpsAsJsonFile | pending | Source JSON bytes/counter names through managed output, fresh guests and production outer; local output lifetime and cloud release gates pending |
| ScribblePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| Scribble_PiDiNet_Preprocessor | pending | Trained source-wrapper double-NMS CPU/guest/outer parity; provisioning/device release gates pending |
| Scribble_XDoG_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| ShufflePreprocessor | pending | Draft pure helper; seed/guest/outer behavior tested, release gate pending |
| TEEDPreprocessor | pending | Trained CPU pixels through fresh guests and outer IMAGE; NC artifact/provisioning/device release gates pending |
| TTPlanet_TileGF_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| TTPlanet_TileSimple_Preprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| TilePreprocessor | pending | Draft pure helper; narrow tests and actual guests, release gate pending |
| UniFormer-SemSegPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Unimatch_OptFlowPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| UpperBodyTrackingFromPoseKps | pending | Source tracking through fresh guests and custom outer TRACKING; integer keys and NumPy scalar coordinates preserved |
| Zoe-DepthMapPreprocessor | pending | Model/asset/graph port pending; draft fails closed |
| Zoe_DepthAnythingPreprocessor | pending | Model/asset/graph port pending; draft fails closed |

## Observed evidence

The 20-helper suite passed 96 checks in 8.69 seconds, including two fresh guest roots/PIDs, raw denial for buffer operations, zero-capability selector execution, production manifest proxies and outer output typing, and independently lifted pristine algorithm differentials. The prior 19-helper checkpoint preserves 88 passing checks and both byte-exact roundtrips. The initial 87-pass/one-failure run incorrectly expected a scalar selector to require raw access; it is retained separately. Annotation uses the byte-exact bundled font, preserves first-image-only uint8 conversion, and bounds UTF-8 text before drawing. Shuffle preserves seeded content remapping, the source's render-local NumPy RNG use for seed zero, uint64 maximum seeds and native negative-seed failure; projected noise workspace is bounded before allocation. Progress notification is a recording double. PyraCanny retains the pinned constant-image divide/cast warnings. Tile retains native zero-dimension failures; guided tile retains its ignored resolution argument. Exact 64-node pristine CPU import and schema census were observed separately. Artifact gate remains in progress.

Python contract: generated `comfy-api.pyi` SHA256 a38c781f061321d0454044cd47ab30a227e2fbe81b196c229a8d1d6a0d0b0406. TypeScript contract: checked ModelFolder union SHA256 2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090. Their current provenance is coordinator-owned output artifacts, not a rewrite of the completed KJ pack.

Pose JSON output uses existing public managed output catalogue and text writer operations, with `assets` and `output` permissions only. It preserves admitted source JSON bytes, counter names, width/height/time substitutions, empty-prefix names and the declared zero-output contract. JSON structure, encoded bytes, catalogue size, filename size and collision retries are bounded before the corresponding work. Native empty/missing-key and non-JSON errors have source controls. Nonfinite numbers, cycles, excessive structures and unsafe logical prefixes fail before output. Time substitution is tested with a controlled local clock; cross-server clock/timezone equivalence is unproved.

The catalogue enumerates managed files, whereas the original filesystem counter can also count directory names. Existing files are preserved by `new_only` writes and at most 32 collision retries; the source can overwrite after a race. Invalid JSON is rejected before creating a file, while the original can leave a partial file. These are explicit managed-output lifetime and namespace adaptations. The existing text writer does not promise atomic publication or a transaction across files. Tests use local output backing and actual guest/outer dispatch with a fixture execution backend. They do not establish cloud storage continuity, import/download delivery, Windows naming parity or aggregate resource enforcement. All 64 release dispositions remain pending.

HED and Fake Scribble passed seven focused checks, including four trained original-source CPU pixel comparisons, both safe modes, grayscale/RGB/RGBA inputs, batches, two fresh guest roots/PIDs, asset/raw denials and production manifest proxies with outer IMAGE outputs. The actual restricted weight loader, tensor transport and pack-owned network execute without model/math doubles. The operator catalogue and execution backend are test fixtures; automatic provisioning and deployed sandbox execution were not observed. Wrong-digest and projected-network-workspace checks fail before model construction.

The declared artifact is `lllyasviel/Annotators` at revision `982e7edaec38759d914a963c48c4726685de7d96`, file `ControlNetHED.pth`, SHA256 `5ca93762ffd68a29fee1af9d495bf6aab80ae86f08905fb35472a083a4c7a8fa`. Its 29,444,406 bytes were verified before default restricted loading; the closed state contains 37 float16 tensors. The pack loads exact keys strictly into its source-derived CPU network. Node execution resolves and verifies managed assets; acquisition belongs to the declaration/provisioning layer. The model card declares license `other`, which does not establish commercial deployment clearance.

PiDiNet, Scribble PiDiNet and M-LSD passed ten focused checks. Six independent original-wrapper comparisons cover both PiDiNet safe modes, the scribble wrapper's second NMS/blur stage, M-LSD threshold modes and grayscale/RGB/RGBA inputs. Each case traverses two fresh actual guests with asset/raw denials and the production manifest outer IMAGE path. Direct trained network-forward checks ensure M-LSD's native catch-all does not conceal an untested network. Algorithm and constructor AST comparisons preserve the pinned code; the unused MobileNet pretrained-backbone downloader is deliberately refused, while the used constructor retains `pretrained=False`. Offline provisioning identity, CPU device selection and progress are oracle doubles; model state/math, restricted loading and guest tensor transport are real. An initial missing Enum in the source-lifting fixture caused seven failures before comparison, retained separately; adding the omitted source import corrected the harness.

Both additional artifacts use the same pinned Annotators revision: `table5_pidinet.pth`, 2,871,148 bytes, SHA256 `80860ac267258b5f27486e0ef152a211d0b08120f62aeb185a050acc30da486c`; and `mlsd_large_512_fp32.pth`, 6,341,481 bytes, SHA256 `5696f168eb2c30d4374bbfd45436f7415bb4d88da29bea97eea0101520fba082`. Checksum verification preceded default restricted loading. The canonical loader selects PiDiNet's `state_dict` and excludes epoch metadata before guest admission; its 83 tensor keys then undergo the exact upstream module-prefix normalization. M-LSD strictly loads all 362 tensor keys, including batch-normalization integer counters. No unsafe loader, downloaded code, key filtering or new shared API is used.

TEED declares `bdsqlsz/qinglong_controlnet-lllite` revision `67006a35a5955437d118490bfec822402eff09f5`, file `Annotators/7_model.pth`, SHA256 `b9037964149c55156c6adbffdfbd7e8ca7d2ef2a4d90573520efa7f3a1aacf06`. Its 247,232 bytes were verified before default restricted loading; all 36 floating tensor keys load strictly. Pinned network and detector math remain pack-owned; removing the local smish JIT decorator avoids execution-time compilation. Tests compare against the original scripted activation, including trained logits before quantization and pixel outputs across safe-step settings, channels and dtypes. Actual fresh guest roots/PIDs and production manifest outer IMAGE checks use real weights, assets and tensor transport with raw/assets denial. Operator catalogue, progress and execution backend are fixtures; no automatic provisioning, GPU or cloud claim. The card declares CC BY-NC-SA 4.0; technical testing does not establish commercial deployment clearance. The initial outer failure from stale manifest asset permissions is retained; manifest regeneration resolves it without relaxing capability checks.

Realistic fine/coarse and anime line-art passed seven focused checks, including strict original architecture/call AST comparisons, four trained CPU pixel cases across channels/dtypes, both realistic model choices, two fresh actual guest roots/PIDs, raw/assets denial and declared outer IMAGE outputs. No model/math doubles are used; operator catalogues, progress and execution backend remain fixtures. Artifacts use the reviewed Annotators revision: `sk_model.pth` SHA256 `c686ced2a666b4850b4bb6ccf0748031c3eda9f822de73a34b8979970d90f0c6` and `sk_model2.pth` SHA256 `30a534781061f34e83bb9406b4335da4ff2616c95d22a585c1245aa8363e74e0`, each 17,173,511 bytes/24 tensors; `netG.pth` SHA256 `ccabdcc3f5cf3c07cf65d58776acb21df7dfda825cdc70c9766a93fd62bfc488`, 217,631,959 bytes/32 tensors. Hash verification precedes default `weights_only=True` CPU parsing. The initial ZIP-only globals scanner limitation is preserved; default restricted legacy-stream parsing succeeds without aliases or unsafe fallback. Anime preserves the exact upstream module-prefix normalization and extra resize to multiples of256. Its conservative projected budget excludes default512 and other larger workloads; small64-resolution trained evidence does not certify them. These work estimates are not hard per-realm RAM/VRAM enforcement. Artifact provisioning, admitted compute profiles, GPU and commercial deployment clearance remain unresolved.

## Limits and persistence

Four pose helpers passed 18 focused checks twice (10.13/10.63 seconds). Independent lifted pristine algorithms cover normalized/pixel coordinates, missing points, facial point/polygon modes, native malformed cases, first-frame-only rendering and in-process source tracking mutation. All four traverse two fresh actual guest roots/PIDs and production manifest outer IMAGE/TRACKING outputs. Inputs are bounded before allocation. Initial failures separately preserve an outer-test fixture mistake and an actual shared transport loss of integer tracking keys/NumPy scalar coordinates. The unchanged behavior assertions pass after the generic transport repair; neither detector inference nor pose-file durability is established.

Manga line-art adds six focused checks: exact nine architecture class ASTs and detector call AST, trained RGB/gray/RGBA and batch/dtype pixel comparisons, two fresh actual guest roots/PIDs, raw/assets denial, two manifest-driven outer IMAGE cases, digest rejection and pre-allocation validation using the native ceiling to multiples of256. `erika.pth` at the same immutable Annotators revision is 172,789,563 bytes, SHA256 `badbd6baf013cefbd98993307b02cc14a26c770d067416e4fdecc8720b88feeb`; checksum and unchanged metadata precede default restricted CPU loading of707 tensors/172,540,124 tensor bytes. Batch-normalization integer counters are retained, all707 source-normalized keys load strictly, and pinned substring `module.` normalization is unchanged. No tensor filtering, unsafe parser, algorithm/model double or new inference API is used. Operator catalogue and execution backend remain fixtures. Conservative workspace estimates exclude default512; the observed64-resolution cases invoke the original256-rounded internal network and do not certify larger workloads or hard RAM/VRAM enforcement. Card license `other`, provisioning, managed compute profiles and GPU release remain unresolved.

Trained HED, Fake Scribble, PiDiNet, Scribble PiDiNet, M-LSD, TEED, both line-art and manga line-art CPU inference paths are observed within the tested cases. Automatic weights provisioning, GPU/device-policy parity and cloud deployment remain unverified. Twenty-nine model/graph/pose branches remain unimplemented and fail closed. V2 entry import omits ambient environment/sys.path mutation and runtime installers. Unported sources remain review input, not admitted execution. Editable config, cloud pose-output persistence and other model artifacts remain pending. Python 3.13 is the managed runtime tested here.

Optical-flow masking adds 28 focused checks. Three pure visualization functions and the masking class retain their pinned ASTs, removing only the ambient helper import. Exact FP32/FP64/FP16 pixels, resizing, mask truncation, local input mutation and native BF16 failure are covered. The source requires N1HW masks and fails on canonical BHW MASK input; the port explicitly adds the channel dimension before unchanged math. Flow visualization's unknown-value clearing and masking mutate the local tensor as in source. Actual guest and outer execution return exact results while host input remains unchanged, an explicit guest-local alias normalization. Four admitted cases and four raw denials across two fresh required Seatbelt guests plus manifest-driven outer custom OPTICAL_FLOW/IMAGE outputs use real tensor transport. The initial 27-pass/one-failure test expected a different raw-denial message; the retained log is corrected only to the observed permission error. No weights, model inference, new shared API, heap/profile grant or cloud claim. Projected visualization workspace is bounded before work. Thirty model/graph/pose branches remain unimplemented; all 64 release dispositions remain pending.

## Selection provenance

Historical Aug4 download rank8/2,507,966downloads. Registry SHA a0f27ea0f7b4ae1b26f2cf84b72ab3b2ad06eb4eb1f3aed7a338a4a2b1d47408. No current trending claim. HARVEY conditional static gains remain separate.

## AMY AnyLine successor

The complete original 64-ID schema is unchanged. AnyLine now declares exact MTEED plus fine/coarse/anime/manga artifacts and uses the existing pack-owned managed loaders. It retains first-channel inclusive intensity masking, three-dimensional morphology over HWC, composition arithmetic, source mode spelling and native incompatible-size failures. Existing inherited workload bounds remain; default resolutions are not newly admitted by this source change. Canonical manifest regeneration/validation against the selected SDK and actual native/registered inference are pending. No raw filesystem model loading or source-import fallback exists in the converted code.

## Isolated AIO source successor

The original AIO helper now preserves `none` image identity and dispatches through the source AUX registry using the unchanged pinned input metadata. Required/optional merge order, explicit defaults, numeric fallback, absent combo defaults, and the upstream unhashable-list TypeError remain exact. The selected converted node retains its original workload validation and detector arithmetic. The helper contains no provider, artifact fallback, new detector, or source import fallback.

AIO declares the union of the existing AUX class permissions and nine existing weight records. The source AUX registry includes schema-excluded output/pose/flow entries; the unchanged AIO schema still exposes the original 47 choices including `none`. These declarations do not admit permissions or a runtime profile. Every unsupported selected detector still reaches its existing fail-closed branch. Canonical SDK manifest regeneration/equality, actual native and registered comparisons, model restricted-load admission, and separately fitting finite Linux/gVisor profiles remain future gates. Ten new stdlib source controls passed; they did not import scientific/SDK/vendor modules or execute inference. All 64 release gates remain pending.
