"""comfy.sd.CLIPType member names pinned to the deployed core (ComfyUI 6257422).

pig.py get_clip_type falls back to STABLE_DIFFUSION for a name the running core lacks, while the SDK
constructor rejects unknown names. The guest resolves the original fallback against this list;
tests/test_clip_types_pinned.py fails if the runtime core's CLIPType drifts from it.
"""

PINNED_CORE = '6257422'

CLIP_TYPE_NAMES = (
    'STABLE_DIFFUSION',
    'STABLE_CASCADE',
    'SD3',
    'STABLE_AUDIO',
    'HUNYUAN_DIT',
    'FLUX',
    'MOCHI',
    'LTXV',
    'HUNYUAN_VIDEO',
    'PIXART',
    'COSMOS',
    'LUMINA2',
    'WAN',
    'HIDREAM',
    'CHROMA',
    'ACE',
    'OMNIGEN2',
    'QWEN_IMAGE',
    'HUNYUAN_IMAGE',
    'HUNYUAN_VIDEO_15',
    'OVIS',
    'KANDINSKY5',
    'KANDINSKY5_IMAGE',
    'NEWBIE',
    'FLUX2',
    'LONGCAT_IMAGE',
    'COGVIDEOX',
    'LENS',
    'PIXELDIT',
    'IDEOGRAM4',
    'BOOGU',
    'KREA2',
    'JOYIMAGE',
    'MAGE',
    'MINIMAX',
    'YUE2',
)


def resolve_clip_type(name):
    """pig.py: getattr(comfy.sd.CLIPType, type.upper(), comfy.sd.CLIPType.STABLE_DIFFUSION) -> member name."""
    upper = name.upper()
    return upper if upper in CLIP_TYPE_NAMES else 'STABLE_DIFFUSION'
