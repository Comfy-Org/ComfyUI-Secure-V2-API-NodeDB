"""Hard selection refusal before NEW imports/RPC/model construction."""
from .selection import require_constructor

async def execute(node_id, image, resolution=512):
    require_constructor()
    from .wrapper import OneFormer_COCO_SemSegPreprocessor, OneFormer_ADE20K_SemSegPreprocessor
    if node_id == 'OneFormer-COCO-SemSegPreprocessor':
        producer = OneFormer_COCO_SemSegPreprocessor()
    elif node_id == 'OneFormer-ADE20K-SemSegPreprocessor':
        producer = OneFormer_ADE20K_SemSegPreprocessor()
    else:
        raise KeyError(node_id)
    return producer.semantic_segmentate(image, resolution=resolution)
