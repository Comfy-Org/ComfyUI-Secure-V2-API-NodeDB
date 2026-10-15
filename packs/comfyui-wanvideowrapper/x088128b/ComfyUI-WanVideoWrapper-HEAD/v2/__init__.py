"""PRIVATE146 source candidate. No installable manifest or promotion claim."""
from .secure_schedule_nodes import CreateCFGScheduleFloatList as _node0
from .secure_schedule_nodes import CreateScheduleFloatList as _node1
from .secure_fantasytalking_nodes import DownloadAndLoadWav2VecModel as _node2
from .secure_arcface_raster_nodes import DrawArcFaceLandmarks as _node3
from .secure_gaussian_nodes import DrawGaussianNoiseOnImage as _node4
from .secure_nlf_raster_nodes import DrawNLFPoses as _node5
from .secure_sampling_model_nodes import DummyComfyWanModelObject as _node6
from .secure_tensor_nodes import ExtractStartFramesForContinuations as _node7
from .secure_pose_nodes import FaceMaskFromPoseKeypoints as _node8
from .secure_portrait_detector_node import FantasyPortraitFaceDetector as _node9
from .secure_portrait_resource import FantasyPortraitModelLoader as _node10
from .secure_audio_projection_nodes import FantasyTalkingModelLoader as _node11
from .secure_fantasytalking_nodes import FantasyTalkingWav2VecEmbeds as _node12
from .secure_humo_nodes import HuMoEmbeds as _node13
from .secure_landmark_nodes import LandmarksToImage as _node14
from .secure_lynx_resampler import LoadLynxResampler as _node15
from .secure_nlf_nodes import LoadNLFModel as _node16
from .secure_mtv_nodes import LoadVQVAE as _node17
from .secure_wan_clip_resource import LoadWanVideoClipTextEncoder as _node18
from .wan_workflow_text_nodes import LoadWanVideoT5TextEncoder as _node19
from .secure_whisper_nodes import LongCatAvatarWhisperEmbeds as _node20
from .secure_lynx_face_nodes import LynxEncodeFaceIP as _node21
from .secure_lynx_face_nodes import LynxInsightFaceCrop as _node22
from .secure_mtv_nodes import MTVCrafterEncodePoses as _node23
from .secure_full_vae_mocha import MochaEmbeds as _node24
from .secure_audio_projection_nodes import MultiTalkModelLoader as _node25
from .secure_silence_nodes import MultiTalkSilentEmbeds as _node26
from .secure_multitalk_wav2vec_nodes import MultiTalkWav2VecEmbeds as _node27
from .secure_nlf_nodes import NLFPredict as _node28
from .secure_audio_loudness_nodes import NormalizeAudioLoudness as _node29
from .secure_ovi_nodes import OviMMAudioVAELoader as _node30
from .secure_qwen_nodes import QwenLoader as _node31
from .secure_recam_raster_nodes import ReCamMasterPoseVisualizer as _node32
from .secure_qwenvl_nodes import TextImageEncodeQwenVL as _node33
from .secure_wanmove_track_nodes import WanMove_native as _node34
from .secure_model_control_payload_nodes import WanVideoATITracks as _node35
from .secure_ati_visual_nodes import WanVideoATITracksVisualize as _node36
from .wan_ati_adapter.secure_ati_model_nodes import WanVideoATI_comfy as _node37
from .secure_bindweave_nodes import WanVideoAddBindweaveEmbeds as _node38
from .secure_tensor_nodes import WanVideoAddControlEmbeds as _node39
from .secure_full_vae_dual_control import WanVideoAddDualControlEmbeds as _node40
from .secure_tensor_nodes import WanVideoAddExtraLatent as _node41
from .secure_portrait_payload_nodes import WanVideoAddFantasyPortrait as _node42
from .secure_tensor_nodes import WanVideoAddFlashVSRInput as _node43
from .secure_tensor_nodes import WanVideoAddLucyEditLatents as _node44
from .secure_full_vae_lynx import WanVideoAddLynxEmbeds as _node45
from .secure_tensor_nodes import WanVideoAddMTVMotion as _node46
from .secure_tensor_nodes import WanVideoAddOneToAllExtendEmbeds as _node47
from .secure_tensor_nodes import WanVideoAddOneToAllPoseEmbeds as _node48
from .secure_full_vae_onetoall import WanVideoAddOneToAllReferenceEmbeds as _node49
from .secure_tensor_nodes import WanVideoAddOviAudioToLatents as _node50
from .secure_tensor_nodes import WanVideoAddPusaNoise as _node51
from .secure_tensor_nodes import WanVideoAddS2VEmbeds as _node52
from .secure_full_vae_conditioning import WanVideoAddSCAILPoseEmbeds as _node53
from .secure_full_vae_conditioning import WanVideoAddSCAILReferenceEmbeds as _node54
from .secure_tensor_nodes import WanVideoAddStandInLatent as _node55
from .secure_tensor_nodes import WanVideoAddSteadyDancerEmbeds as _node56
from .secure_full_vae_conditioning import WanVideoAddStoryMemLatents as _node57
from .secure_tensor_nodes import WanVideoAddTTMLatents as _node58
from .secure_wanmove_track_nodes import WanVideoAddWanMoveTracks as _node59
from .secure_animate_node import WanVideoAnimateEmbeds as _node60
from .secure_tensor_nodes import WanVideoApplyNAG as _node61
from .secure_scalar_nodes import WanVideoBlockList as _node62
from .secure_scalar_nodes import WanVideoBlockSwap as _node63
from .secure_clip_vision_nodes import WanVideoClipVisionEncode as _node64
from .secure_tensor_nodes import WanVideoCombineEmbeds as _node65
from .secure_tensor_nodes import WanVideoContextOptions as _node66
from .secure_tensor_nodes import WanVideoControlEmbeds as _node67
from .secure_model_control_payload_nodes import WanVideoControlnetApply as _node68
from .secure_tiny_decode_nodes import WanVideoDecode as _node69
from .secure_ovi_nodes import WanVideoDecodeOviAudio as _node70
from .secure_cache_settings_nodes import WanVideoEasyCache as _node71
from .secure_tensor_nodes import WanVideoEmptyEmbeds as _node72
from .secure_tensor_nodes import WanVideoEmptyMMAudioLatents as _node73
from .secure_full_vae_encode import WanVideoEncode as _node74
from .secure_full_vae_encode import WanVideoEncodeLatentBatch as _node75
from .secure_ovi_nodes import WanVideoEncodeOviAudio as _node76
from .secure_scalar_nodes import WanVideoEnhanceAVideo as _node77
from .secure_scalar_nodes import WanVideoExperimentalArgs as _node78
from .secure_model_asset_select_nodes import WanVideoExtraModelSelect as _node79
from .secure_flashvsr_decoder_nodes import WanVideoFlashVSRDecoderLoader as _node80
from .secure_scalar_nodes import WanVideoFreeInitArgs as _node81
from .secure_fun_camera_nodes import WanVideoFunCameraEmbeds as _node82
from .secure_image_clip_node import WanVideoImageClipEncode as _node83
from .secure_ref_nodes import WanVideoImageResizeToClosest as _node84
from .secure_full_vae_i2v import WanVideoImageToVideoEncode as _node85
from .secure_long_audio_conditioning_nodes import WanVideoImageToVideoMultiTalk as _node86
from .secure_long_audio_conditioning_nodes import WanVideoImageToVideoSkyreelsv3_audio as _node87
from .secure_tensor_nodes import WanVideoLatentReScale as _node88
from .secure_longcat_avatar_extend import WanVideoLongCatAvatarExtendEmbeds as _node89
from .secure_scalar_nodes import WanVideoLoopArgs as _node90
from .secure_scalar_nodes import WanVideoLoraBlockEdit as _node91
from .secure_lora_single_nodes import WanVideoLoraSelect as _node92
from .secure_lora_single_nodes import WanVideoLoraSelectByName as _node93
from .secure_lora_multi_nodes import WanVideoLoraSelectMulti as _node94
from .secure_cache_settings_nodes import WanVideoMagCache as _node95
from .secure_tensor_nodes import WanVideoMiniMaxRemoverEmbeds as _node96
from .wan_workflow_model_nodes import WanVideoModelLoader as _node97
from .secure_tensor_nodes import WanVideoOviCFG as _node98
from .secure_tensor_nodes import WanVideoPassImagesFromSamples as _node99
from .secure_tensor_nodes import WanVideoPhantomEmbeds as _node100
from .secure_tensor_nodes import WanVideoPreviewEmbeds as _node101
from .secure_qwen_nodes import WanVideoPromptExtender as _node102
from .secure_prompt_extender_settings_nodes import WanVideoPromptExtenderSelect as _node103
from .secure_recam_camera_nodes import WanVideoReCamMasterCameraEmbed as _node104
from .secure_recam_camera_nodes import WanVideoReCamMasterDefaultCamera as _node105
from .secure_recam_camera_nodes import WanVideoReCamMasterGenerateOrbitCamera as _node106
from .secure_tensor_nodes import WanVideoRealisDanceLatents as _node107
from .secure_scalar_nodes import WanVideoRoPEFunction as _node108
from .secure_scalar_nodes import WanVideoSLG as _node109
from .secure_tensor_nodes import WanVideoSVIProEmbeds as _node110
from .wan_workflow_sampler_nodes import WanVideoSampler as _node111
from .secure_passthrough_nodes import WanVideoSamplerExtraArgs as _node112
from .secure_sampler_adapter_nodes import WanVideoSamplerFromSettings as _node113
from .secure_sampler_settings_nodes import WanVideoSamplerSettings as _node114
from .secure_sampler_adapter_nodes import WanVideoSamplerv2 as _node115
from .wan_workflow_scheduler_nodes import WanVideoScheduler as _node116
from .wan_workflow_scheduler_nodes import WanVideoSchedulerv2 as _node117
from .secure_model_control_nodes import WanVideoSetAttentionModeOverride as _node118
from .secure_model_control_nodes import WanVideoSetBlockSwap as _node119
from .secure_model_control_nodes import WanVideoSetRadialAttention as _node120
from .secure_scalar_nodes import WanVideoSigmaToStep as _node121
from .secure_cache_settings_nodes import WanVideoTeaCache as _node122
from .secure_text_embed_bridge import WanVideoTextEmbedBridge as _node123
from .wan_workflow_text_nodes import WanVideoTextEncode as _node124
from .secure_text_variant_nodes import WanVideoTextEncodeCached as _node125
from .secure_text_variant_nodes import WanVideoTextEncodeSingle as _node126
from .secure_tiny_vae_nodes import WanVideoTinyVAELoader as _node127
from .secure_scalar_nodes import WanVideoTorchCompileSettings as _node128
from .secure_model_control_nodes import WanVideoUltraVicoSettings as _node129
from .secure_uni3c_embed_nodes import WanVideoUni3C_embeds as _node130
from .secure_unianimate_node import WanVideoUniAnimateDWPoseDetector as _node131
from .secure_unianimate_input_nodes import WanVideoUniAnimatePoseInput as _node132
from .secure_tensor_nodes import WanVideoUniLumosEmbeds as _node133
from .secure_full_vae_vace import WanVideoVACEEncode as _node134
from .secure_model_asset_select_nodes import WanVideoVACEModelSelect as _node135
from .secure_frame_nodes import WanVideoVACEStartToEndFrame as _node136
from .secure_full_vae_nodes import WanVideoVAELoader as _node137
from .secure_scalar_nodes import WanVideoVRAMManagement as _node138
from .secure_wanmove_raster_nodes import WanVideoWanDrawWanMoveTracks as _node139
from .secure_multitalk_wav2vec_nodes import Wav2VecModelLoader as _node140
from .secure_whisper_nodes import WhisperModelLoader as _node141
from .secure_set_loras_node import WanVideoSetLoRAs as _node142
from .secure_control_loader_nodes import WanVideoControlnetLoader as _node143
from .secure_control_loader_nodes import WanVideoUni3C_ControlnetLoader as _node144
from .secure_diffusion_forcing_node import WanVideoDiffusionForcingSampler as _node145
NODE_CLASS_MAPPINGS = {
    'CreateCFGScheduleFloatList': _node0,
    'CreateScheduleFloatList': _node1,
    'DownloadAndLoadWav2VecModel': _node2,
    'DrawArcFaceLandmarks': _node3,
    'DrawGaussianNoiseOnImage': _node4,
    'DrawNLFPoses': _node5,
    'DummyComfyWanModelObject': _node6,
    'ExtractStartFramesForContinuations': _node7,
    'FaceMaskFromPoseKeypoints': _node8,
    'FantasyPortraitFaceDetector': _node9,
    'FantasyPortraitModelLoader': _node10,
    'FantasyTalkingModelLoader': _node11,
    'FantasyTalkingWav2VecEmbeds': _node12,
    'HuMoEmbeds': _node13,
    'LandmarksToImage': _node14,
    'LoadLynxResampler': _node15,
    'LoadNLFModel': _node16,
    'LoadVQVAE': _node17,
    'LoadWanVideoClipTextEncoder': _node18,
    'LoadWanVideoT5TextEncoder': _node19,
    'LongCatAvatarWhisperEmbeds': _node20,
    'LynxEncodeFaceIP': _node21,
    'LynxInsightFaceCrop': _node22,
    'MTVCrafterEncodePoses': _node23,
    'MochaEmbeds': _node24,
    'MultiTalkModelLoader': _node25,
    'MultiTalkSilentEmbeds': _node26,
    'MultiTalkWav2VecEmbeds': _node27,
    'NLFPredict': _node28,
    'NormalizeAudioLoudness': _node29,
    'OviMMAudioVAELoader': _node30,
    'QwenLoader': _node31,
    'ReCamMasterPoseVisualizer': _node32,
    'TextImageEncodeQwenVL': _node33,
    'WanMove_native': _node34,
    'WanVideoATITracks': _node35,
    'WanVideoATITracksVisualize': _node36,
    'WanVideoATI_comfy': _node37,
    'WanVideoAddBindweaveEmbeds': _node38,
    'WanVideoAddControlEmbeds': _node39,
    'WanVideoAddDualControlEmbeds': _node40,
    'WanVideoAddExtraLatent': _node41,
    'WanVideoAddFantasyPortrait': _node42,
    'WanVideoAddFlashVSRInput': _node43,
    'WanVideoAddLucyEditLatents': _node44,
    'WanVideoAddLynxEmbeds': _node45,
    'WanVideoAddMTVMotion': _node46,
    'WanVideoAddOneToAllExtendEmbeds': _node47,
    'WanVideoAddOneToAllPoseEmbeds': _node48,
    'WanVideoAddOneToAllReferenceEmbeds': _node49,
    'WanVideoAddOviAudioToLatents': _node50,
    'WanVideoAddPusaNoise': _node51,
    'WanVideoAddS2VEmbeds': _node52,
    'WanVideoAddSCAILPoseEmbeds': _node53,
    'WanVideoAddSCAILReferenceEmbeds': _node54,
    'WanVideoAddStandInLatent': _node55,
    'WanVideoAddSteadyDancerEmbeds': _node56,
    'WanVideoAddStoryMemLatents': _node57,
    'WanVideoAddTTMLatents': _node58,
    'WanVideoAddWanMoveTracks': _node59,
    'WanVideoAnimateEmbeds': _node60,
    'WanVideoApplyNAG': _node61,
    'WanVideoBlockList': _node62,
    'WanVideoBlockSwap': _node63,
    'WanVideoClipVisionEncode': _node64,
    'WanVideoCombineEmbeds': _node65,
    'WanVideoContextOptions': _node66,
    'WanVideoControlEmbeds': _node67,
    'WanVideoControlnet': _node68,
    'WanVideoControlnetLoader': _node143,
    'WanVideoDecode': _node69,
    'WanVideoDecodeOviAudio': _node70,
    'WanVideoDiffusionForcingSampler': _node145,
    'WanVideoEasyCache': _node71,
    'WanVideoEmptyEmbeds': _node72,
    'WanVideoEmptyMMAudioLatents': _node73,
    'WanVideoEncode': _node74,
    'WanVideoEncodeLatentBatch': _node75,
    'WanVideoEncodeOviAudio': _node76,
    'WanVideoEnhanceAVideo': _node77,
    'WanVideoExperimentalArgs': _node78,
    'WanVideoExtraModelSelect': _node79,
    'WanVideoFlashVSRDecoderLoader': _node80,
    'WanVideoFreeInitArgs': _node81,
    'WanVideoFunCameraEmbeds': _node82,
    'WanVideoImageClipEncode': _node83,
    'WanVideoImageResizeToClosest': _node84,
    'WanVideoImageToVideoEncode': _node85,
    'WanVideoImageToVideoMultiTalk': _node86,
    'WanVideoImageToVideoSkyreelsv3_audio': _node87,
    'WanVideoLatentReScale': _node88,
    'WanVideoLongCatAvatarExtendEmbeds': _node89,
    'WanVideoLoopArgs': _node90,
    'WanVideoLoraBlockEdit': _node91,
    'WanVideoLoraSelect': _node92,
    'WanVideoLoraSelectByName': _node93,
    'WanVideoLoraSelectMulti': _node94,
    'WanVideoMagCache': _node95,
    'WanVideoMiniMaxRemoverEmbeds': _node96,
    'WanVideoModelLoader': _node97,
    'WanVideoOviCFG': _node98,
    'WanVideoPassImagesFromSamples': _node99,
    'WanVideoPhantomEmbeds': _node100,
    'WanVideoPreviewEmbeds': _node101,
    'WanVideoPromptExtender': _node102,
    'WanVideoPromptExtenderSelect': _node103,
    'WanVideoReCamMasterCameraEmbed': _node104,
    'WanVideoReCamMasterDefaultCamera': _node105,
    'WanVideoReCamMasterGenerateOrbitCamera': _node106,
    'WanVideoRealisDanceLatents': _node107,
    'WanVideoRoPEFunction': _node108,
    'WanVideoSLG': _node109,
    'WanVideoSVIProEmbeds': _node110,
    'WanVideoSampler': _node111,
    'WanVideoSamplerExtraArgs': _node112,
    'WanVideoSamplerFromSettings': _node113,
    'WanVideoSamplerSettings': _node114,
    'WanVideoSamplerv2': _node115,
    'WanVideoScheduler': _node116,
    'WanVideoSchedulerv2': _node117,
    'WanVideoSetAttentionModeOverride': _node118,
    'WanVideoSetBlockSwap': _node119,
    'WanVideoSetLoRAs': _node142,
    'WanVideoSetRadialAttention': _node120,
    'WanVideoSigmaToStep': _node121,
    'WanVideoTeaCache': _node122,
    'WanVideoTextEmbedBridge': _node123,
    'WanVideoTextEncode': _node124,
    'WanVideoTextEncodeCached': _node125,
    'WanVideoTextEncodeSingle': _node126,
    'WanVideoTinyVAELoader': _node127,
    'WanVideoTorchCompileSettings': _node128,
    'WanVideoUltraVicoSettings': _node129,
    'WanVideoUni3C_ControlnetLoader': _node144,
    'WanVideoUni3C_embeds': _node130,
    'WanVideoUniAnimateDWPoseDetector': _node131,
    'WanVideoUniAnimatePoseInput': _node132,
    'WanVideoUniLumosEmbeds': _node133,
    'WanVideoVACEEncode': _node134,
    'WanVideoVACEModelSelect': _node135,
    'WanVideoVACEStartToEndFrame': _node136,
    'WanVideoVAELoader': _node137,
    'WanVideoVRAMManagement': _node138,
    'WanVideoWanDrawWanMoveTracks': _node139,
    'Wav2VecModelLoader': _node140,
    'WhisperModelLoader': _node141,
}
WEB_DIRECTORY = "web"
__all__ = ["NODE_CLASS_MAPPINGS"]
