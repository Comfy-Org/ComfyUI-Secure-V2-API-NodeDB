"""Owned public standard catalogue; native authored scanner not reproduced."""
import json
from comfy_api.latest import sdk


async def standard_diffusion_model_names(request):
    names = await sdk.ctx().models.list_diffusion_models()
    return {'status': 200, 'content_type': 'application/json',
            'body': json.dumps(sorted(names))}
