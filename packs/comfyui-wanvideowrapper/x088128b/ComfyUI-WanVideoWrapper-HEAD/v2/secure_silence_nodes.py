"""Bounded MultiTalk silence from the pinned immutable pack asset only."""
import hashlib
from pathlib import Path
import torch
from safetensors.torch import load
from comfy_api.latest import io
from .secure_tensor_nodes import MAX_TENSOR_ELEMENTS, MAX_PAYLOAD_BYTES

RESOURCE_SIZE = 1658968
RESOURCE_SHA256 = 'cd68739d78b9566cf3d575e4140f7e02f0d36e4ae9bcb33457d92711c3c6584d'


def _silence():
    root = Path(__file__).resolve().parent
    path = root / 'multitalk' / 'encoded_silence.safetensors'
    if path.is_symlink() or path.resolve() != path:
        raise ValueError('Wan bundled silence must be an immutable in-pack file')
    # Fixed resource, no caller path or host asset catalogue. Bounded read
    # precedes deserialization; no pickle or executable model/config loader.
    with path.open('rb') as stream:
        data = stream.read(RESOURCE_SIZE + 1)
    if len(data) != RESOURCE_SIZE or hashlib.sha256(data).hexdigest() != RESOURCE_SHA256:
        raise ValueError('Wan bundled silence size/hash mismatch')
    value = load(data)['audio_emb']
    if value.shape != (90, 12, 768) or value.dtype != torch.float16:
        raise ValueError('Wan bundled silence tensor contract mismatch')
    return value


class MultiTalkSilentEmbeds(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MultiTalkSilentEmbeds', display_name='MultiTalk Silent Embeds',
            category='WanVideoWrapper',
            inputs=[io.Int.Input('num_frames', default=81, min=1, max=10000, step=1, tooltip='The total frame count to generate.')],
            outputs=[io.Custom('MULTITALK_EMBEDS').Output(display_name='multitalk_embeds')])

    @classmethod
    def execute(cls, num_frames):
        encoded_silence = _silence()
        repeats = (num_frames + encoded_silence.shape[0] - 1) // encoded_silence.shape[0]
        if isinstance(repeats, int) and repeats >= 0:
            elements = repeats * encoded_silence.numel()
            # Reserve repeat, possible wire copies and the loaded resource.
            if elements > MAX_TENSOR_ELEMENTS or (3*elements + 2*encoded_silence.numel())*encoded_silence.element_size() > MAX_PAYLOAD_BYTES:
                raise ValueError('Wan silence projected repeat/wire work exceeds tensor/64 MiB bounds')
        repeated = encoded_silence.repeat(repeats, 1, 1)
        repeated = repeated[:num_frames]
        return io.NodeOutput({
            'audio_features': repeated,
            'audio_scale': 1.0,
            'audio_cfg_scale': 1.0,
            'ref_target_masks': None,
        })


NODE_CLASS_MAPPINGS = {'MultiTalkSilentEmbeds': MultiTalkSilentEmbeds}
