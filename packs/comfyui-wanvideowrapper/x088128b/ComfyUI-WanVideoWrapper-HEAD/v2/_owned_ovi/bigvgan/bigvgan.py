import torch
import torch.nn as nn
from types import SimpleNamespace
from .models import BigVGANVocoder
from ..weights import load_bound_state_dict
_bigvgan_vocoder_config = {'resblock': '1', 'num_gpus': 0, 'batch_size': 64, 'num_mels': 80, 'learning_rate': 0.0001, 'adam_b1': 0.8, 'adam_b2': 0.99, 'lr_decay': 0.999, 'seed': 1234, 'upsample_rates': [4, 4, 2, 2, 2, 2], 'upsample_kernel_sizes': [8, 8, 4, 4, 4, 4], 'upsample_initial_channel': 1536, 'resblock_kernel_sizes': [3, 7, 11], 'resblock_dilation_sizes': [[1, 3, 5], [1, 3, 5], [1, 3, 5]], 'activation': 'snakebeta', 'snake_logscale': True, 'resolutions': [[1024, 120, 600], [2048, 240, 1200], [512, 50, 240]], 'mpd_reshapes': [2, 3, 5, 7, 11], 'use_spectral_norm': False, 'discriminator_channel_mult': 1}

class BigVGAN(nn.Module):

    @classmethod
    async def create(cls, ckpt_path):
        self = cls.__new__(cls)
        nn.Module.__init__(self)
        vocoder_cfg = SimpleNamespace(**_bigvgan_vocoder_config)
        self.vocoder = BigVGANVocoder(vocoder_cfg).eval()
        vocoder_ckpt = await load_bound_state_dict(ckpt_path)
        self.vocoder.load_state_dict(vocoder_ckpt)
        self.weight_norm_removed = False
        self.remove_weight_norm()
        return self

    @torch.inference_mode()
    def forward(self, x):
        assert self.weight_norm_removed, 'call remove_weight_norm() before inference'
        return self.vocoder(x)

    def remove_weight_norm(self):
        self.vocoder.remove_weight_norm()
        self.weight_norm_removed = True
        return self
