"""Original portrait detector body using immutable bundled detector assets."""
import logging
from pathlib import Path
import numpy as np
import torch
from .secure_portrait_pd_math import get_drive_expression_pd_fgc,det_landmarks,FanEncoder
log=logging.getLogger(__name__)
offload_device=torch.device('cpu')
_models=Path(__file__).parent/'fantasyportrait/models'
alignment_model_path=str(_models/'face_landmark.onnx')
det_model_path=str(_models/'face_det.onnx')

def load_pd_fgc_model(state_dict, providers):
    from .fantasyportrait.pd_fgc.camer import CameraDemo
    from .fantasyportrait.pd_fgc.face_align import FaceAlignment
    face_aligner = CameraDemo(face_alignment_module=FaceAlignment(providers=providers, alignment_model_path=alignment_model_path, det_model_path=det_model_path), reset=False)
    pd_fpg_motion = FanEncoder()
    m, u = pd_fpg_motion.load_state_dict(state_dict, strict=False)
    pd_fpg_motion = pd_fpg_motion.eval()
    return (face_aligner, pd_fpg_motion)

def get_emo_feature(frame_list, face_aligner, pd_fpg_motion, device):
    _, landmark_list, rect_list = det_landmarks(face_aligner, frame_list, None)
    last_valid_landmark = None
    last_valid_rect = None
    for i in range(len(landmark_list)):
        if landmark_list[i] is None:
            landmark_list[i] = last_valid_landmark
        else:
            last_valid_landmark = landmark_list[i]
        if rect_list[i] is None:
            rect_list[i] = last_valid_rect
        else:
            last_valid_rect = rect_list[i]
    if landmark_list[0] is None:
        first_valid = next((l for l in landmark_list if l is not None), None)
        for i in range(len(landmark_list)):
            if landmark_list[i] is None:
                landmark_list[i] = first_valid
            else:
                break
    if rect_list[0] is None:
        first_valid = next((r for r in rect_list if r is not None), None)
        for i in range(len(rect_list)):
            if rect_list[i] is None:
                rect_list[i] = first_valid
            else:
                break
    emo_list = get_drive_expression_pd_fgc(pd_fpg_motion, frame_list, landmark_list, device)
    head_emo_feat_list = []
    for emo in emo_list:
        headpose_emb = emo['headpose_emb']
        eye_embed = emo['eye_embed']
        emo_embed = emo['emo_embed']
        mouth_feat = emo['mouth_feat']
        emo_feat = torch.cat([eye_embed, emo_embed, mouth_feat], dim=1)
        head_emo_feat = torch.cat([headpose_emb, emo_feat], dim=1)
        head_emo_feat_list.append(head_emo_feat)
    head_emo_feat_all = torch.cat(head_emo_feat_list, dim=0).unsqueeze(0)
    return (head_emo_feat_all, rect_list, landmark_list)

def detect_portrait_original(images, portrait_model, adapter_scale=1.0, mouth_scale=1.0, emo_scale=1.0, device='cuda'):
    B, H, W, C = images.shape
    num_frames = (B - 1) // 4 * 4 + 1
    images = images.clone()[:num_frames]

    def tensor_batch_to_numpy_list(images):
        images = images.detach().cpu()
        numpy_list = []
        for img in images:
            img = img.numpy()
            img = img[..., :3]
            img = (img * 255).clip(0, 255)
            img = img.astype(np.uint8)
            numpy_list.append(img)
        return numpy_list
    numpy_list = tensor_batch_to_numpy_list(images)
    pd_fpg_sd = {}
    for k, v in portrait_model['sd'].items():
        if k.startswith('pd_fpg.'):
            pd_fpg_sd[k.replace('pd_fpg.', '')] = v
    if device == 'cuda':
        providers = ['CUDAExecutionProvider']
    else:
        providers = ['CPUExecutionProvider']
    face_aligner, pd_fpg_motion = load_pd_fgc_model(pd_fpg_sd, providers)
    pd_fpg_motion.to(device)
    head_emo_feat_all, rect_list, landmark_list = get_emo_feature(numpy_list, face_aligner, pd_fpg_motion, device=device)
    log.info(f'FantasyPortraitFaceDetector: input frames: {num_frames}')
    log.info(f'FantasyPortraitFaceDetector: features extracted for {head_emo_feat_all.shape[1]} frames')
    pd_fpg_motion.to(offload_device)
    portrait_model = portrait_model['proj_model']
    portrait_model.to(device)
    adapter_proj = portrait_model.get_adapter_proj(head_emo_feat_all.to(device, dtype=portrait_model.dtype), adapter_scale=adapter_scale, mouth_scale=mouth_scale, emo_scale=emo_scale)
    portrait_model.to(offload_device)
    pos_idx_range = portrait_model.split_audio_adapter_sequence(adapter_proj.size(1), num_frames=num_frames)
    proj_split, context_lens = portrait_model.split_tensor_with_padding(adapter_proj, pos_idx_range, expand_length=0)
    return (proj_split, rect_list, landmark_list)
