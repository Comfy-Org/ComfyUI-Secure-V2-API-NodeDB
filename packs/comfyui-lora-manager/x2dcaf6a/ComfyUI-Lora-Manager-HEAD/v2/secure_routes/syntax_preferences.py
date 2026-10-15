"""Native one-field settings POST adapted to published6eb dict route dispatch.

The real dispatcher supplies sdk.ctx() authenticated tenant/pack storage. No
aiohttp request facade, host path, request authority or public revision input.
"""
from __future__ import annotations

import logging

from ..secure_services.info_note_routes import _request, _parse, _reply, MAX_ENVELOPE_BYTES
from ..secure_services.syntax_preferences import FIELD, save_syntax_preference

logger = logging.getLogger(__name__)


async def update_settings(request):
    """POST /api/lm/settings, explicitly admitting only syntax format or {}."""
    try:
        _request(request, 'POST')
        if request['query']:
            raise ValueError('Syntax-setting author accepts no query overrides')
        data = _parse(request['body'])
        if type(data) is not dict or not set(data) <= {FIELD}:
            raise ValueError('Only lora_syntax_format is supported by this settings author')
        # Preserve native empty-update success without storage access.
        if data:
            result = await save_syntax_preference(data[FIELD])
            if not result['updated']:
                return _reply(409, {'success': False,
                                    'error': 'Manager preferences changed during save'})
        return _reply(200, {'success': True})
    except Exception as exc:
        # Native update_settings returns plain error text with status500.
        logger.error('Error updating settings: %s', exc, exc_info=True)
        body = str(exc)
        if len(body.encode('utf-8')) > MAX_ENVELOPE_BYTES:
            raise ValueError('Syntax-setting error response exceeds bounds') from exc
        return {'status': 500, 'body': body, 'content_type': 'text/plain'}
