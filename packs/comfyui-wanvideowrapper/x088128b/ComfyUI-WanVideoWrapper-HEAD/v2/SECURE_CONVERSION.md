> **STATUS: IN PROGRESS — UNVERIFIED.** Published for evaluation on 2026-10-15 at the user's request.
> Nodes: 143 of 147 converted; 100 tested (scoped), 43 converted but untested/partly tested,
> 4 partial or missing. Not accepted: no whole-pack certificate. Open gates are listed below.

<!-- secure-conversion-report-v1 -->
# Secure Nodes V2 conversion report — comfyui-wanvideowrapper

**NOT COMPLETE.** This is the private143 r4 candidate, published in-progress. No node has whole-node acceptance; "tested" means at least one scoped original-vs-converted behavior case passed (CPU, bounded inputs, mostly without trained-model parity).

## Provenance

- Upstream: https://github.com/kijai/ComfyUI-WanVideoWrapper
- Pinned commit: `088128b224242e110d3906c6750e9a3a348a659b` (key `x088128b`); 241 tracked files, all mode 100644.
- Candidate: reviewed private142 r3 source + SetLoRAs registration wiring + display-name fidelity correction (20 schemas) + control-loader header preflight (independent review CLEAR).
- Mirror mode: node IDs, display names and categories are the original's. Registered schemas carry the original display name (142 of 143; upstream defines none for TextImageEncodeQwenVL).
- Publication adjustments: the vendored `wan_workflow_math/multitalk/multitalk_loop.py` reads the pack's own `multitalk/encoded_silence.safetensors` instead of a byte-identical duplicate (patch pairs cannot add binaries); the never-imported case-only twin `taehv/TAEHV.py` of `taehv/taehv.py` is omitted (paths must be case-distinct); internal evidence documents with host paths were left out of `v2/`.
- Report format: `secure-conversion-report-v1`. Earlier per-checkpoint history is kept in the conversion lane records, not in this pack.

## Status summary

| Bucket | Count | Meaning |
| --- | --- | --- |
| tested | 100 | registered; scoped original-vs-converted behavior case(s) passed |
| converted-untested | 43 | registered; source/schema/scalar checks only, no behavior case yet |
| partial / pending-capability | 4 | not registered; see per-node table |
| missing | 0 | every upstream ID has converted source |

## Per-node table

| Node ID | Disposition | Evidence or gap |
| --- | --- | --- |
| `CreateCFGScheduleFloatList` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `CreateScheduleFloatList` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `DownloadAndLoadNLFModel` | pending-capability | Exact schema and existing-cache branch prepared; both original NLF TorchScript releases acquired. Not yet supported - needs the public opaque-artifact (managed download/cache) route. Owned by the NLF lane (AMY). |
| `DownloadAndLoadWav2VecModel` | converted-untested | Evidence: exact original source metadata and nine native scalar split cases only. Open: Original model payload admission. |
| `DrawArcFaceLandmarks` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): arcface-combined-r1. |
| `DrawGaussianNoiseOnImage` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): payload-noise-r1. |
| `DrawNLFPoses` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): pose-raster-r1. |
| `DummyComfyWanModelObject` | tested | PASS scoped comparisons: Two genuine registered+owning Guest source comparisons;0 installed gVisor,0 learned weights. |
| `ExtractStartFramesForContinuations` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `FaceMaskFromPoseKeypoints` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): pose-raster-r1. |
| `FantasyPortraitFaceDetector` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': ['Six exact CP313 Linux CPU ONNX wheels in PORTRAIT_ONNX_PROFILE_PROPOSAL.json', 'Actual original ONNX session/provider imports, including current protobuf version', 'Separate CUDA provider profile for original default device'], 'resource_device_behavior': 'CPU first requires six-wheel ONNX proposal; original default CUDA remains separate. Input BHWC1..65 frames, spatial<=1024, raw payload<=64MiB. Full FanEncoder+adapter inference and NumPy metadata transport unqualified.'}. |
| `FantasyPortraitModelLoader` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Asset<=2GiB; channel count<=8192; original full state/precision preserved. Peak must be measured before actual guest transfer.'}. |
| `FantasyTalkingModelLoader` | converted-untested | Evidence: source scalar recipes and exact private main consumer agreement only. Open: Original menu union. |
| `FantasyTalkingWav2VecEmbeds` | converted-untested | Evidence: exact original source metadata and nine native scalar split cases only. Open: Original model payload admission. |
| `HuMoEmbeds` | converted-untested | Evidence: source scalar default guard and small math only. Open: Original default learned 81x832x480 native peak. |
| `LandmarksToImage` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): pose-raster-r1. |
| `LoadLynxResampler` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Asset<=1GiB; original 4-layer1280-channel20-head16-query model and strict state retained. Native RAM estimate1.5..2.5GiB is planning only.'}. |
| `LoadNLFModel` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': ['Managed nlf catalogue', 'Opaque .torchscript managed artifact admission; no host JIT execution'], 'profile': ['Actual original TorchScript serialized operators and version compatibility; current source only cannot establish closure'], 'resource_device_behavior': 'Original torch.jit.load without map_location override; 8MiB streaming into<=2GiB archive. CPU/GPU archive behavior, JIT operator dependencies and optional two warmup calls unqualified.'}. |
| `LoadVQVAE` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Original VectorQuantizer .cuda() retained; current CPU path refuses before weights. Asset<=2GiB. Requires actual admitted GPU memory/device.'}. |
| `LoadWanVideoClipTextEncoder` | tested | PASS scoped original-vs-converted cases via direct SDK gVisor job (CPU, bounded inputs). |
| `LoadWanVideoT5TextEncoder` | converted-untested | Source/schema only. Open: Actual combined final SDK metadata/import. |
| `LongCatAvatarWhisperEmbeds` | converted-untested | Evidence: source schema and light validation only. Open: Final public asset/range runtime. |
| `LynxEncodeFaceIP` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Original unconditional CUDA retained. No CPU substitute. ArcFace plus trained resampler and actual GPU raw transport require a GPU slot.'}. |
| `LynxInsightFaceCrop` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': ['InsightFace exact reproducible Linux CP313 build/profile not yet frozen or admitted', 'ONNX Runtime/default providers/full five-model buffalo_l behavior', 'Original release byte equivalence before model admission'], 'resource_device_behavior': 'Original full five-model buffalo_l, default providers and ctx_id0 retained. Disposable scratch<=384MiB, ranges8MiB, assets<=256MiB each, input1..16 frames<=1024. InsightFace profile and invocation-scoped detector lifecycle unqualified.'}. |
| `MTVCrafterEncodePoses` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Original CUDA VQVAE and mean/std unchanged. NLF joints3d_nonparam structure,<=64 frames and projected quantizer work<=64MiB. Requires real NLF/GPU and NumPy output transport.'}. |
| `MochaEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-mocha-r1, full-vae-mocha-r2, full-vae-mocha-r3 +3 more. |
| `MultiTalkModelLoader` | converted-untested | Evidence: source scalar recipes and exact private main consumer agreement only. Open: Original menu union. |
| `MultiTalkSilentEmbeds` | tested | PASS scoped original-vs-converted cases via direct SDK gVisor job (CPU, bounded inputs). |
| `MultiTalkWav2VecEmbeds` | converted-untested | Evidence: source preprocessing math schema and guest validation only. Open: Original Tencent checkpoint admission. |
| `NLFPredict` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': ['Managed nlf catalogue', 'Opaque .torchscript managed artifact admission; no host JIT execution'], 'profile': ['Actual original TorchScript serialized operators and version compatibility; current source only cannot establish closure'], 'resource_device_behavior': 'Original full JIT prediction and batch/empty-frame behavior retained. Raw CPU BHWC0..64 frames, spatial<=1024, payload<=64MiB. Real NLF inference and NLFPRED transport unqualified.'}. |
| `NormalizeAudioLoudness` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): silence-stereo-r4, tone-mono-f32-r4, tone-stereo-f64-r4. |
| `OviMMAudioVAELoader` | converted-untested | Evidence: exact original source and scalar guards only. Open: Original vae+mmaudio menu/catalogue. |
| `QwenLoader` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': ['Existing50-wheel profile/tokenizer proof retained; actual model integration after current runtime scheduling'], 'resource_device_behavior': 'Original3B/7B constructors and tokenizer retained. Asset ceiling16GiB is source bound, not capacity admission. 3B native estimate8..10GiB; full host/SHM/guest state transfer requires a separate memory plan.'}. |
| `ReCamMasterPoseVisualizer` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): camera-trail-r2. |
| `TextImageEncodeQwenVL` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanMove_native` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wanmove-tracks-r1. |
| `WanVideoATITracks` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoATITracksVisualize` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): camera-trail-r2. |
| `WanVideoATI_comfy` | tested | PASS scoped comparisons: Two native270-comparison source passes; canonical patcher/model on meta, no neural forward or installed gVisor. Requires canonical MODEL; not JACK WANVIDEOMODEL recipe. |
| `WanVideoAddBindweaveEmbeds` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoAddControlEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoAddDualControlEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-dual-control-r1, full-vae-dual-control-r2, full-vae-dual-control-r3 +1 more. |
| `WanVideoAddExtraLatent` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddFantasyPortrait` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): payload-noise-r1. |
| `WanVideoAddFlashVSRInput` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoAddLucyEditLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddLynxEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-lynx-r1, full-vae-lynx-r2, full-vae-lynx-r3 +3 more. |
| `WanVideoAddMTVMotion` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddOneToAllExtendEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoAddOneToAllPoseEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoAddOneToAllReferenceEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-onetoall-r1, full-vae-onetoall-r2, full-vae-onetoall-r3 +1 more. |
| `WanVideoAddOviAudioToLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddPusaNoise` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoAddS2VEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-five-r1. |
| `WanVideoAddSCAILPoseEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-conditioning-r3, full-vae-conditioning-r4. |
| `WanVideoAddSCAILReferenceEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-conditioning-r2, full-vae-conditioning-r9. |
| `WanVideoAddStandInLatent` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddSteadyDancerEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoAddStoryMemLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-conditioning-r5, full-vae-conditioning-r6, full-vae-conditioning-r7. |
| `WanVideoAddTTMLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoAddWanMoveTracks` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wanmove-tracks-r1. |
| `WanVideoAnimateEmbeds` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': [], 'resource_device_behavior': 'Reuse existing full VAE recipe without fork. Current CPU bounds width/height<=512, frames<=64 and projected work<=64MiB exclude original default832x480x81. Full native branch matrix and large defaults remain open.'}. |
| `WanVideoApplyNAG` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoBlockList` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoBlockSwap` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoClipVisionEncode` | tested | PASS scoped original-vs-converted cases via direct SDK gVisor job (CPU, bounded inputs). |
| `WanVideoCombineEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoContextOptions` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoControlEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoControlnet` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoControlnetLoader` | partial | V2 producer, digest-bound recipe and owned materializer exist; header-order preflight integrated (independent review CLEAR, 2048/2048 differential cases). Not registered until one real-checkpoint load comparison passes; the original TheDenk checkpoint is now acquired and pinned. |
| `WanVideoDecode` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-goldens-r37, full-vae-goldens-r38, full-vae-goldens-r39 +9 more. |
| `WanVideoDecodeOviAudio` | converted-untested | Evidence: exact original source and scalar guards only. Open: Original vae+mmaudio menu/catalogue. |
| `WanVideoDiffusionForcingSampler` | pending-capability | Original math and 20-argument binder converted. Not yet supported - needs a public cleanup/lifetime contract: the original performs global offload/cleanup of a text-encoder owner that the public borrowed-embedding path does not hold at sampling time. |
| `WanVideoEasyCache` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): cache-settings-main_device-r1, cache-settings-offload_device-r1. |
| `WanVideoEmptyEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoEmptyMMAudioLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoEncode` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-goldens-r37, full-vae-goldens-r38, full-vae-goldens-r39 +3 more. |
| `WanVideoEncodeLatentBatch` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-goldens-r41. |
| `WanVideoEncodeOviAudio` | converted-untested | Evidence: exact original source and scalar guards only. Open: Original vae+mmaudio menu/catalogue. |
| `WanVideoEnhanceAVideo` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoExperimentalArgs` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoExtraModelSelect` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoFlashVSRDecoderLoader` | converted-untested | Evidence: source only, native cuda default preserved.. Open: build_tcdecoder defaults device=cuda and the original loader does not override it. Candidate preserves it. No CPU substitution, resource download or execution performed. |
| `WanVideoFreeInitArgs` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoFunCameraEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): camera-trail-r2. |
| `WanVideoImageClipEncode` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': ['ClipVisionOutputRef.last_hidden_state(*, batch_start: int = 0, batch_count: int / None = None) -> TensorRef', 'ClipVisionOutputRef.penultimate_hidden_states(*, batch_start: int = 0, batch_count: int / None = None) -> TensorRef', 'ClipVisionRef.offload() -> None', 'ImageRef.from_value(value) -> ImageRef (or equivalent public bounded raw-tier image construction)'], 'profile': [], 'resource_device_behavior': 'Original custom visual plus full VAE branch can reuse two existing assets; canonical vision branch needs generic APIs. Current<=512dimensions/64frames/64MiB projected work excludes default832x480x81.'}. |
| `WanVideoImageResizeToClosest` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): resize-closest-r2. |
| `WanVideoImageToVideoEncode` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-i2v-r1, full-vae-i2v-r2, full-vae-i2v-r3 +5 more. |
| `WanVideoImageToVideoMultiTalk` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-audio-producers-child-r2. |
| `WanVideoImageToVideoSkyreelsv3_audio` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-audio-producers-child-r2. |
| `WanVideoLatentReScale` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-five-r1. |
| `WanVideoLongCatAvatarExtendEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-longcat-avatar-child-r2. |
| `WanVideoLoopArgs` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoLoraBlockEdit` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-four_identity-r1, settings-four_scaled-r1. |
| `WanVideoLoraSelect` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoLoraSelectByName` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoLoraSelectMulti` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoMagCache` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): cache-settings-main_device-r1, cache-settings-offload_device-r1. |
| `WanVideoMiniMaxRemoverEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-seven-r1. |
| `WanVideoModelLoader` | converted-untested | Source/schema only. Open: Actual combined final SDK metadata/import. |
| `WanVideoOviCFG` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoPassImagesFromSamples` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-five-r1. |
| `WanVideoPhantomEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-five-r1. |
| `WanVideoPreviewEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-five-r1. |
| `WanVideoPromptExtender` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': ['Existing50-wheel profile/tokenizer proof retained; actual model integration after current runtime scheduling'], 'resource_device_behavior': 'Original seeded generation, custom None versus empty string, lm_head tying retained. Bounds64KiB text,8192 input tokens,1..2048 new tokens. No trained constructor/generation yet; main/offload CPU policy does not prove GPU equivalence.'}. |
| `WanVideoPromptExtenderSelect` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): prompt-selector-r1. |
| `WanVideoReCamMasterCameraEmbed` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): recam-camera-r1. |
| `WanVideoReCamMasterDefaultCamera` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): recam-camera-r1. |
| `WanVideoReCamMasterGenerateOrbitCamera` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): recam-camera-r1. |
| `WanVideoRealisDanceLatents` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoRoPEFunction` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-four_identity-r1, settings-four_scaled-r1. |
| `WanVideoSLG` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoSVIProEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): latent-ten-r2. |
| `WanVideoSampler` | converted-untested | Source/schema only. Open: Actual combined final SDK metadata/import. |
| `WanVideoSamplerExtraArgs` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoSamplerFromSettings` | converted-untested | Evidence: exact original argument entry/schema only;0 sampler body executions. delegates to the single jack main sampler.. Open: Actual trained shared sampler qualification. |
| `WanVideoSamplerSettings` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoSamplerv2` | converted-untested | Evidence: exact original argument entry/schema only;0 sampler body executions. delegates to the single jack main sampler.. Open: Actual trained shared sampler qualification. |
| `WanVideoScheduler` | converted-untested | Source/schema only. Open: Actual combined final SDK import and official schema/flags check. |
| `WanVideoSchedulerv2` | converted-untested | Source/schema only. Open: Actual combined final SDK import and official schema/flags check. |
| `WanVideoSetAttentionModeOverride` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoSetBlockSwap` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoSetLoRAs` | tested | PASS 14 cases (7 x registered in-process + owning ordinary Guest) plus 27 historical in-process; trained nonzero LoRA application, sampler consumer and installed gVisor gates open. |
| `WanVideoSetRadialAttention` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoSigmaToStep` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-four_identity-r1, settings-four_scaled-r1. |
| `WanVideoTeaCache` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): cache-settings-main_device-r1, cache-settings-offload_device-r1. |
| `WanVideoTextEmbedBridge` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): text-bridge-positive-only-r1, text-bridge-with-negative-r1. |
| `WanVideoTextEncode` | converted-untested | Source/schema only. Open: Actual combined final SDK metadata/import. |
| `WanVideoTextEncodeCached` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-text-cache-rebind-r4. |
| `WanVideoTextEncodeSingle` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-text-cache-rebind-r4. |
| `WanVideoTinyVAELoader` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): tiny-vae-goldens-r2. |
| `WanVideoTorchCompileSettings` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-four_identity-r1, settings-four_scaled-r1. |
| `WanVideoUltraVicoSettings` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoUni3C_ControlnetLoader` | partial | Same as WanVideoControlnetLoader for the Uni3C checkpoint (fp16, 1,997,314,376 B, acquired and pinned); real-checkpoint load comparison pending. |
| `WanVideoUni3C_embeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): wan-controls-child-r2. |
| `WanVideoUniAnimateDWPoseDetector` | converted-untested | Evidence: original source/schema/math plus real in-process sdk; no trained model inference. Open: {'installed_sdk': [], 'profile': ['Actual original TorchScript serialized operators and version compatibility; current source only cannot establish closure'], 'resource_device_behavior': 'Original TorchScript pair; public 8MiB streaming, each archive<=256MiB. Input1..64 CPU BHWC frames<=1024; one optional reference. Actual JIT ops and native nondetection/geometry inference pending.'}. |
| `WanVideoUniAnimatePoseInput` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): payload-noise-r1. |
| `WanVideoUniLumosEmbeds` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): conditioning-ten-r2. |
| `WanVideoVACEEncode` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-vace-r2, full-vae-vace-r3, full-vae-vace-r4 +3 more. |
| `WanVideoVACEModelSelect` | converted-untested | Registered (canonical 105); no behavior case recorded yet. |
| `WanVideoVACEStartToEndFrame` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): vace-frame-resized_end_mask-r2, vace-frame-start_only-r2. |
| `WanVideoVAELoader` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): full-vae-conditioning-r2, full-vae-conditioning-r3, full-vae-conditioning-r4 +43 more. |
| `WanVideoVRAMManagement` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): settings-eight-r1. |
| `WanVideoWanDrawWanMoveTracks` | tested | PASS scoped original-vs-converted cases on the secure service (gVisor): camera-trail-r2. |
| `Wav2VecModelLoader` | converted-untested | Evidence: source preprocessing math schema and guest validation only. Open: Original Tencent checkpoint admission. |
| `WhisperModelLoader` | converted-untested | Evidence: source schema and light validation only. Open: Final public asset/range runtime. |

## Refused techniques (never-do) and public replacements

| Never do | Public replacement |
| --- | --- |
| Global host-model unload / cache emptying from a node | Owned resource leases released by the runtime; forcing sampler waits for a public cleanup contract |
| Arbitrary host filesystem paths, `folder_paths`, writing `.pt` caches | Digest-bound SDK assets (`assets`: resolve / size / digest / read_range) and managed outputs |
| Network downloads inside nodes (hub downloads, urllib, torch.hub) | Pinned, managed asset acquisition outside the node; required-weight declarations |
| Direct CUDA/device authority or compile toggles as grants | SDK device/offload policy; device options carried as plain data; CPU fp32/SDPA fallback |
| Pickle / `torch.load` of untrusted files | SafeTensors with header validation; TorchScript only via the preserved original constructor from pinned assets |
| `trust_remote_code` / online tokenizers | `trust_remote_code=False, local_files_only=True` with bundled pinned tokenizer files |
| Importing ComfyUI internals (`comfy`, `folder_paths`, `server`) | Public `comfy_api.latest` (`io`, `sdk`) only; enforced by an import audit during discovery |
| Server routes / PromptServer messages | Execution-scoped SDK progress |
| Mutating host-owned objects across the boundary | Typed copies; aliasing is not promised |
| Stub or fake nodes, fabricated outputs, suppressed errors | Leave the node unregistered (partial) until real behavior exists |

## Pending capabilities (not yet supported)

- `WanVideoDiffusionForcingSampler` - needs a public cleanup/lifetime contract for borrowed text-encoder owners.
- `DownloadAndLoadNLFModel` - needs the public opaque-artifact (managed download/cache) route.
- `WanVideoControlnetLoader`, `WanVideoUni3C_ControlnetLoader` - need one real-checkpoint load comparison each (checkpoints acquired); registration follows.
- MTVCrafter nodes - upstream requires CUDA unconditionally; needs GPU qualification.
- Durable text-embedding caches - need cache quota/lifecycle/eviction semantics.

## Open test gates

- Trained main workflow (model loader, T5 loader, text encode, sampler, schedulers): one end-to-end 1.3B original-vs-converted run.
- Sampler consumer and video render; full-size domains; GPU/device behavior.
- Trained-model parity for loader/encoder families (vision, audio, Lynx, portrait, Qwen, Ovi, HuMo).
- SetLoRAs: compatible trained nonzero WAN LoRA application; empty-plan consumer; remaining 27 historical cases on ordinary Guest; capability-negative test.
- Required-weight declarations: 19 loaders declared weights historically but the current official encoding yields none; restore the declarations before production.
- Combined all-147 metadata import, installed gVisor qualification, browser/UI acceptance.
- v2/tests are historical scoped unit tests; test_wan_candidate_artifacts.py still asserts the checkpoint-era registration count (65) and must be refreshed.

## Authority and permissions

Registered nodes request only these SDK permission sets. None grants raw network access, host filesystem paths or device authority; `models.download` lets a node request managed downloads of pinned model files through the SDK, and `assets` gives digest-bound reads of declared assets.

| Permissions | Nodes |
| --- | --- |
| `raw` | 55 |
| `raw`, `assets`, `models.download` | 27 |
| (none) | 26 |
| `raw`, `assets` | 15 |
| `assets` | 6 |
| `assets`, `raw`, `models.download` | 4 |
| `raw`, `assets`, `storage` | 3 |
| `raw`, `assets`, `models`, `models.download` | 2 |
| `assets`, `raw` | 1 |
| `inspect` | 1 |
| `models` | 1 |
| `models`, `closures` | 1 |
| `raw`, `inspect` | 1 |

## Assets and weights required (names + sources; never committed)

| Node(s) | Folder | File | Source | Status |
| --- | --- | --- | --- | --- |
| `DownloadAndLoadWav2VecModel` | audio_encoders | `model.safetensors` | https://huggingface.co/facebook/wav2vec2-base-960h/blob/22aad52d435eb6dbaf354bdad9b0da84ce7d6156/model.safetensors | declared (official encoding) |
| `DownloadAndLoadWav2VecModel` | audio_encoders | `pytorch_model.bin` | https://huggingface.co/TencentGameMate/chinese-wav2vec2-base/blob/3991242c806928916fff4a8c0e4f76acf661b743/pytorch_model.bin | declared (official encoding) |
| `LynxEncodeFaceIP` | detection | `facexlib/recognition_arcface_ir_se50.pth` | https://huggingface.co/camenduru/PuLID/blob/f45b1ab19fc398695ea69f9c85a60112644df82e/facexlib/recognition_arcface_ir_se50.pth | declared (official encoding) |
| `LynxInsightFaceCrop` | detection | `models/buffalo_l/1k3d68.onnx` | https://huggingface.co/lithiumice/insightface/blob/8c253c7565ac522f99c69317f2362700b89645c4/models/buffalo_l/1k3d68.onnx | declared (official encoding) |
| `LynxInsightFaceCrop` | detection | `models/buffalo_l/2d106det.onnx` | https://huggingface.co/lithiumice/insightface/blob/8c253c7565ac522f99c69317f2362700b89645c4/models/buffalo_l/2d106det.onnx | declared (official encoding) |
| `LynxInsightFaceCrop` | detection | `models/buffalo_l/det_10g.onnx` | https://huggingface.co/lithiumice/insightface/blob/8c253c7565ac522f99c69317f2362700b89645c4/models/buffalo_l/det_10g.onnx | declared (official encoding) |
| `LynxInsightFaceCrop` | detection | `models/buffalo_l/genderage.onnx` | https://huggingface.co/lithiumice/insightface/blob/8c253c7565ac522f99c69317f2362700b89645c4/models/buffalo_l/genderage.onnx | declared (official encoding) |
| `LynxInsightFaceCrop` | detection | `models/buffalo_l/w600k_r50.onnx` | https://huggingface.co/lithiumice/insightface/blob/8c253c7565ac522f99c69317f2362700b89645c4/models/buffalo_l/w600k_r50.onnx | declared (official encoding) |
| `WanVideoUniAnimateDWPoseDetector` | controlnet | `yolox_l.torchscript.pt` | https://huggingface.co/hr16/yolox-onnx/blob/a124b32c3b7c5cebda1c7cd96178f0f9d2050125/yolox_l.torchscript.pt | declared (official encoding) |
| `WanVideoUniAnimateDWPoseDetector` | controlnet | `dw-ll_ucoco_384_bs5.torchscript.pt` | https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/blob/359d662a9b33b73f6d0f21732baf8845f17bb4be/dw-ll_ucoco_384_bs5.torchscript.pt | declared (official encoding) |
| `LoadWanVideoClipTextEncoder`, `WanVideoClipVisionEncode` | clip_vision | `open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors` | https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors | declared historically; current encoding omits (open gate) |
| `LoadWanVideoT5TextEncoder` | text_encoders | `umt5-xxl-enc-fp8_e4m3fn.safetensors` | https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/umt5-xxl-enc-fp8_e4m3fn.safetensors | declared historically; current encoding omits (open gate) |
| `MochaEmbeds`, `WanVideoAddDualControlEmbeds`, `WanVideoAddLynxEmbeds`, `WanVideoAddOneToAllReferenceEmbeds`, `WanVideoAddSCAILPoseEmbeds`, `WanVideoAddSCAILReferenceEmbeds`, `WanVideoAddStoryMemLatents`, `WanVideoDecode`, `WanVideoEncode`, `WanVideoEncodeLatentBatch`, `WanVideoImageToVideoEncode`, `WanVideoLongCatAvatarExtendEmbeds`, `WanVideoVACEEncode`, `WanVideoVAELoader` | vae | `Wan2_1_VAE_bf16.safetensors` | https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/Wan2_1_VAE_bf16.safetensors | declared historically; current encoding omits (open gate) |
| `WanVideoDecode`, `WanVideoTinyVAELoader` | vae_approx | `taew2_1.safetensors` | https://huggingface.co/OzzyGT/taew2_1/blob/4f23bfa06fbb9bc3331d70db8c1dfc5eb2cd1441/taew2_1.safetensors | declared historically; current encoding omits (open gate) |
| `WanVideoModelLoader` | diffusion_models | `Wan2_1-T2V-1_3B_bf16.safetensors` | https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/Wan2_1-T2V-1_3B_bf16.safetensors | declared historically; current encoding omits (open gate) |
| `WanVideoControlnetLoader` | controlnet | `diffusion_pytorch_model.safetensors` | https://huggingface.co/TheDenk/wan2.1-t2v-1.3b-controlnet-canny-v1/blob/1735ab9e2250b8989581d8078f4ce95d2a058f2d/diffusion_pytorch_model.safetensors | acquired for the pending load comparison |
| `WanVideoUni3C_ControlnetLoader` | controlnet | `Wan21_Uni3C_controlnet_fp16.safetensors` | https://huggingface.co/Kijai/WanVideo_comfy/blob/8260d429d19fd7a72304cad059160b95d843913f/Wan21_Uni3C_controlnet_fp16.safetensors | acquired for the pending load comparison |
| `DownloadAndLoadNLFModel`, `LoadNLFModel` | nlf | `nlf_l_multi_0.3.2.torchscript`, `nlf_l_multi_0.2.2.torchscript` | original GitHub releases of the NLF project (pinned by sha256 in the lane) | acquired; route pending |

## Safety narrowings and observable normalization (carried forward)

_Written at earlier checkpoints; the narrowings still apply to the converted helpers. Registration remarks inside (for example "unregistered") are historical - the per-node table above is current._

- Unregistered MoCha staging admits dense CPU raw values only and preserves the pinned BCTHW RGB transform, frame truncation to1+4k, latent-mask nearest interpolation, <=.5/>.5/zero threshold order (including surviving NaNs), reference ordering and target/sequence arithmetic. Input, overlapping clone/transform/mask/concat and rotary work are checked before allocation against16,777,216 elements/64MiB; grid batch<=64 and projected grid<=1,000,000. Frequency dimensions must be finite and projected exponent/frequency vectors are bounded even when output rows are0. These explicit temporary resource narrowings are not an admitted whole-model workload/profile. The CPU-only stage does not silently implement a source device option or managed offload. Native direct BF16 rotary view_as_complex failures are preserved; this observation does not prove the full trained sampler supplies BF16 at that callsite.
- ATI trail rendering caps aggregate track text at64KiB before JSON parsing, tracks at64, coordinates at finite absolute1,000,000, radii/retention at absolute100, projected draw calls250,000, output elements16,777,216 and overlapping repeat/CPU/raster/publication reserve64MiB before allocation. Bounded native negative/zero/malformed outcomes remain; max_retain=0 still raises division-by-zero. Source returns RGB despite BGR wording and paints0..255 into floating-point images; neither normalization nor channel swapping is introduced. Short batches repeat then slice81; long batches truncate81. These fixture bounds exclude normal480x832 rendering and do not constitute enforced physical memory or GPU authority.
- Text is capped at 64 KiB; block-list expansion is checked before allocating ranges and capped at 10,001 entries.
- MultiTalk silence reads only the fixed immutable `multitalk/encoded_silence.safetensors` in the assigned read-only pack jail, with1658968-byte exact size and SHA `cd68739d78b9566cf3d575e4140f7e02f0d36e4ae9bcb33457d92711c3c6584d` verified before bytes parsing. No caller-selected paths, filesystem writes, downloads or pickle. Symlink escape/corrupt/oversize resources fail closed. The actual90x12x768 float16 tensor is repeated and sliced unchanged; negative frame requests may produce empty tensors or native negative-dimension errors. Repeat/wire reserve is bounded to16,777,216 elements/64MiB; this excludes the declared10000-frame maximum, so full workload/profile remains pending. Default81 and bounded1000-frame CPU behavior are tested; local projected reserve is not physical memory enforcement.
- Schedule lists allocate at most1000 entries; direct negative/zero/reversed ranges and unknown interpolation preserve bounded source outcomes. Schedule values must be scalar finite numbers with absolute magnitude<=1,000,000; interpolation text<=64KiB and projected loop<=10001 iterations. These are explicit malformed/oversized direct-call narrowings, not changes to declared widget ranges. Progress retains the source list's literal string and best-effort failure behavior, but routing belongs exclusively to the executing node/client captured by the broker; arbitrary caller UNIQUE_ID retargeting is not retained. Hidden UNIQUE_ID schema declaration remains, without exporting graph internals or accepting caller routing parameters. Headless/no-client execution cannot broadcast. The declared FLOAT socket intentionally carries a scalar list, not OUTPUT_IS_LIST or per-item coercion, exactly as pinned source.
- LoRA block selection retains all 40 declared switches, literal True-versus-truthy filtering and exact comma/whitespace layer-filter behavior. Direct malformed omitted/list layer_filter still raises the native error. Filters and direct extra keys are capped at 4,096; this node does not load/apply LoRAs or persist a library.
- Raw helper inputs have per-tensor/NumPy-array 16,777,216-element bounds and per-argument aggregate 64 MiB tensor/array/text, 8,192 visited values, 4,096 container items, depth 16. NumPy arrays accept only bool/integer/unsigned/float dtypes; object, complex and string arrays are refused. These refuse over-budget direct calls; they do not certify full model memory quotas. Exact MTV NumPy inputs now pass coordinator's bounded numeric array transport; no arbitrary Opaque materialization is granted.
- UniLumos generated zero fills and Phantom concatenation also preflight projected output element/byte limits before allocation. This is an explicit resource narrowing; safe bounded source behavior is retained.
- Ovi empty audio output [length,20] is similarly preflight-bounded before torch.zeros. Its dictionary intentionally has latent_ovi_audio rather than a fabricated samples key, as upstream does. Payload merge helpers preserve direct aliases, but raw guest transport does not expose host object identity.
- RealisDance concatenation and SVI continuation output are preflight-bounded with promoted tensor dtype bytes before zero-fill/concatenation. Native source frame divisibility, negative padding and mismatched geometry failures are retained for bounded direct inputs. TTM nearest mask interpolation and 16/48-channel scaling are not replaced with another interpolation mode.
- S2V stack promotion and projected audio buckets are checked before allocation, with at most 10,001 intermediate frame buckets. This explicit work/element/byte narrowing does not prove overall inference memory enforcement. Fixed-start sampling leaves NumPy global RNG unchanged; source negative window=-1 can succeed for the tested bounded case, and that observed result is preserved instead of inventing a native failure.
- VACE frame assembly preflights projected output and resized/repeated intermediates before allocation under element/64 MiB bounds. It uses public ImageRef/MaskRef.from_value and canonical image resize, not private raw constructors or imported ComfyUI internals. Empty inpaint mask batches retain the native subsequent division-by-zero without weakening nonempty IMAGE broker validation; unknown/malformed typed transport may still reject earlier than a direct legacy call.
- Face masks reserve projected RGB canvases, stacked RGB, float conversion and final MASK before any canvas allocation. This explicitly narrows unbounded legacy work. Empty frame lists retain the source [1,64,64] zero mask; no valid-person detections retain blank canvases, and bounded malformed triplets/dimensions retain native errors. OpenCV/einops are existing managed dependencies; observed versions are 5.0.0/0.8.2, not an untested cross-version pixel guarantee.
- OneToAll pose/prefix reserves overlapping transform intermediates; continuation padding reserves clone/repeated-tail/concat before allocation. The source intentionally shallow-copies the top-level embeds but mutates an existing nested one_to_all_embeds dictionary; direct alias/mutation evidence does not promise mutation of a host-owned dictionary across guest transport. Pose RGB is sliced to3 channels, but an explicit prefix retains all its source channels; that asymmetry is not silently normalized.
- Raw transport copies preserve tensor values/layout/dtype but do not promise mutating host-owned input aliases. Direct pack-side mutation/alias behavior is tested; a host object escape is not restored.
- These temporary bounds exclude common full Wan workloads, not merely malicious inputs. An observed no-allocation probe rejects VACE81frames832x480 before output creation: float32 RGB would be388,177,920bytes (370.20MiB), MASK129,392,640bytes (123.40MiB), combined493.59MiB. No large output/inference was allocated. Small-fixture passes do not establish default81-frame deployment support; trusted compute/allocation budgets and enforcement must precede any quota increase.
- Native vision staging also retains temporary64MiB work limits: projected tile/join intermediates and eight-times-token-work reserve are bounded. After the first bounded token window, total projected row work is checked before further retrieval/concatenation. The source input/combined batch remains temporarily1..64 RGB; each source tile call may have256 rows and is windowed only in transport. These are conservative fixture bounds, not an encoder allocation policy or a guarantee that real trained tile8/tile16 configurations fit. Canonical native crop ignores the crop widget as pinned upstream does; untiled uses penultimate, any positive tile count uses final tokens. Only the last source image's tiled encoding survives, then broadcasts for multi-image batches; single-image merged tokens are not scaled by1-ratio. All are source quirks preserved, not silently fixed. CPU token transport evidence does not establish GPU placement/residency equivalence.
- WanVideoControlEmbeds target_shape remains torch.Size in-process, but current composite wire transports that subtype as a list. A dedicated test extracts both exact pinned sampler noise allocations (nodes_sampler.py lines 336–343 and 2067–2074) and proves identical seeded CPU values/shapes for Size/list inputs. Wire comparisons normalize only this field; arbitrary consumer type-checking and the full sampler loop remain unproven.
- WanVideoSigmaToStep returns its FLOAT argument unchanged despite declaring INT, as the pinned source does; no integer coercion is introduced.
- Source widget/method default mismatch in TorchCompileSettings is preserved rather than silently normalized.
- Public image resize preserves pinned NumPy dimension alignment and Lanczos pixel behavior. Projected output is capped at 8,388,608 batch-pixels before resize; invalid unknown aspect mode retains the native UnboundLocalError. Typed-image transport validation can change malformed input error detail; no full malformed-image equivalence is claimed.

## Persistence disposition

Implemented helpers have workflow-input/data-owned state only; fresh filesystems/guest processes verify those cases without durable pack state. The whole pack has prompt embedding and model caches. Existing runtime KV and managed SafeTensors outputs may express bounded cache storage, but durable cloud backing, eviction/index consistency, quota/delete semantics and reuse after filesystem/worker resets are NOT proven. Removing .pt writes or shipping immutable defaults is not declared parity.

