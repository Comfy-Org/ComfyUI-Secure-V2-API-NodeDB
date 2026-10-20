"""Core catalogue constants pinned to the run core (ComfyUI 6257422, the a2 base).

The guest cannot read folder_paths. Validators use this copy of supported_pt_extensions for the original's
clip/vae/audio_encoders lists. tests/test_core_pins.py fails if the run core drifts. Core 708e6c01 has the same
extensions; its other differences are recorded in PORT_NOTES.
"""

PINNED_CORE = '6257422'

SUPPORTED_PT_EXTENSIONS = (
    '.bin',
    '.ckpt',
    '.pkl',
    '.pt',
    '.pt2',
    '.pth',
    '.safetensors',
    '.sft',
)
