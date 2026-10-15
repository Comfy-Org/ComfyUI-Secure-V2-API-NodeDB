"""Held packaged-template routes on the current plain-mapping dispatch contract.

Only pinned packaged documents are included. Dynamic filesystem/path capture,
live directory edits and HTTP admission are outside this source adapter.
"""
from __future__ import annotations

import json
import logging
import os
from ..secure_services.template_documents import DOCUMENTS

logger = logging.getLogger(__name__)

def _reply(status, data):
    return {'status': status, 'content_type': 'application/json',
            'body': json.dumps(data)}

def _blank():
    return {'last_node_id': 0, 'last_link_id': 0, 'nodes': [], 'links': [],
            'groups': [], 'config': {}, 'extra': {}, 'version': 0.4}

async def get_example_workflows(request):
    """GET /example-workflows: exact native packaged list and display labels."""
    try:
        workflows = [{'value': 'Default', 'label': 'Default (Blank)', 'path': None}]
        for filename in sorted(DOCUMENTS):
            if filename.endswith('.json'):
                workflows.append({'value': filename,
                    'label': os.path.splitext(filename)[0].replace('_', ' '),
                    'path': f'example_workflows/{filename}'})
        return _reply(200, {'success': True, 'workflows': workflows})
    except Exception as exc:
        logger.error('Error listing example workflows: %s', exc, exc_info=True)
        return _reply(500, {'success': False, 'error': str(exc)})

async def get_example_workflow(request):
    """GET one declared literal packaged filename, including Default."""
    try:
        filename = request['path'].rsplit('/', 1)[-1]
        if not filename:
            return _reply(400, {'success': False, 'error': 'Filename not provided'})
        if filename == 'Default':
            return _reply(200, {'success': True, 'workflow': _blank()})
        if filename not in DOCUMENTS:
            return _reply(404, {'success': False, 'error': f'Workflow not found: {filename}'})
        return _reply(200, {'success': True, 'workflow': json.loads(DOCUMENTS[filename])})
    except Exception as exc:
        logger.error('Error loading example workflow: %s', exc, exc_info=True)
        return _reply(500, {'success': False, 'error': str(exc)})
