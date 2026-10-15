"""Exact original Ovi feature math; async public-asset constructor only."""
import torch
import torch.nn as nn
from .mel_converter import get_mel_converter
from .vae.autoencoder import AutoEncoderModule
from .vae.distributions import DiagonalGaussianDistribution

class FeaturesUtils(nn.Module):

    @classmethod
    async def create(cls, *, tod_vae_ckpt: str, bigvgan_vocoder_ckpt=None, mode=['16k', '44k'], need_vae_encoder: bool=True):
        self = cls.__new__(cls)
        nn.Module.__init__(self)
        self.mel_converter = get_mel_converter(mode)
        self.tod = await AutoEncoderModule.create(vae_ckpt_path=tod_vae_ckpt, vocoder_ckpt_path=bigvgan_vocoder_ckpt, mode=mode, need_vae_encoder=need_vae_encoder)
        return self

    def encode_audio(self, x) -> DiagonalGaussianDistribution:
        assert self.tod is not None, 'VAE is not loaded'
        mel = self.mel_converter(x)
        dist = self.tod.encode(mel)
        return dist

    def vocode(self, mel: torch.Tensor) -> torch.Tensor:
        assert self.tod is not None, 'VAE is not loaded'
        return self.tod.vocode(mel)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        assert self.tod is not None, 'VAE is not loaded'
        return self.tod.decode(z)

    @property
    def device(self):
        return next(self.parameters()).device

    @property
    def dtype(self):
        return next(self.parameters()).dtype

    def wrapped_decode(self, z):
        with torch.amp.autocast('cuda', dtype=self.dtype):
            mel_decoded = self.decode(z)
            audio = self.vocode(mel_decoded)
            return audio

    def wrapped_encode(self, audio):
        with torch.amp.autocast('cuda', dtype=self.dtype):
            dist = self.encode_audio(audio)
            return dist.mean
