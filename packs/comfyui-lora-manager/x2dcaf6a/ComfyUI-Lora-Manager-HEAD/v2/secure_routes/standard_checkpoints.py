"""Owned standard-root selector route; requires actual route admission.

No filesystem scans, authored metadata guesses, or provider substitution.
This returns only the public catalogue of logical checkpoint names. It does
not implement the native LoRA Manager scanner or its extra model roots.
"""
import json
from comfy_api.latest import sdk


async def standard_checkpoint_names(request):
    names = await sdk.ctx().assets.list('checkpoints')
    return {'status': 200, 'content_type': 'application/json',
            'body': json.dumps(sorted(names))}
