"""Original usage-tips GET data fields, adapted to 6eb plain-mapping dispatch.

Only exact current logical names are admitted. Native scanner aliases remain
unselected. There is no request principal/path override or settings GET facade.
"""
import logging
from ..secure_services.info_note_routes import _request, _reply
from ..secure_services.autocomplete_insertion import read_usage_tips

logger = logging.getLogger(__name__)


async def get_lora_usage_tips_by_path(request):
    try:
        _request(request, 'GET')
        if request['body'] != '' or set(request['query']) - {'relative_path'}:
            raise ValueError('Usage tips accepts only relative_path')
        relative_path = request['query'].get('relative_path')
        if not relative_path:
            # Exact native status/plain text for the missing/empty query.
            return {'status': 400, 'body': 'Relative path is required',
                    'content_type': 'text/plain'}
        return _reply(200, await read_usage_tips(relative_path))
    except Exception as exc:
        logger.error('Error getting lora usage tips by path: %s', exc, exc_info=True)
        # Exact native general error fields/status. Never report a provider
        # failure as a successful missing-tip lookup.
        return _reply(500, {'success': False, 'error': str(exc)})
