"""Original MTV algorithms; the original mandatory CUDA constructor is retained."""
import os
from pathlib import Path
import numpy as np
import torch
from .MTV.motion4d import SMPL_VQVAE,VectorQuantizer,Encoder,Decoder
script_directory=str(Path(__file__).parent/'MTV')
device=torch.device('cuda')
offload_device=torch.device('cpu')

def build_mtv_vqvae(vae_sd):
    motion_encoder = Encoder(in_channels=3, mid_channels=[128, 512], out_channels=3072, downsample_time=[2, 2], downsample_joint=[1, 1])
    motion_quant = VectorQuantizer(nb_code=8192, code_dim=3072)
    motion_decoder = Decoder(in_channels=3072, mid_channels=[512, 128], out_channels=3, upsample_rate=2.0, frame_upsample_rate=[2.0, 2.0], joint_upsample_rate=[1.0, 1.0])
    vqvae = SMPL_VQVAE(motion_encoder, motion_decoder, motion_quant).to(device)
    vqvae.load_state_dict(vae_sd, strict=True)
    return vqvae

def encode_mtv_poses_original(vqvae, poses):
    global_mean = np.load(os.path.join(script_directory, 'data', 'mean.npy'))
    global_std = np.load(os.path.join(script_directory, 'data', 'std.npy'))
    smpl_poses = []
    for pose in poses['joints3d_nonparam'][0]:
        smpl_poses.append(pose[0].cpu().numpy())
    smpl_poses = np.array(smpl_poses)
    norm_poses = torch.tensor((smpl_poses - global_mean) / global_std).unsqueeze(0)
    print(f'norm_poses shape: {norm_poses.shape}, dtype: {norm_poses.dtype}')
    vqvae.to(device)
    motion_tokens, vq_loss = vqvae(norm_poses.to(device), return_vq=True)
    recon_motion = vqvae(norm_poses.to(device))[0][0].to(dtype=torch.float32).cpu().detach() * global_std + global_mean
    vqvae.to(offload_device)
    poses_dict = {'mtv_motion_tokens': motion_tokens, 'global_mean': global_mean, 'global_std': global_std}
    return (poses_dict, recon_motion)
