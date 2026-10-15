"""Closed owned pool transports; only fixture registration until whole release."""
from .info_note_routes import _request, _parse, _reply
from ..secure_algorithms.bounds import bounded_json
from .pool_catalogue import read_pool_catalogue, cycle_list, randomize_pool


def _body(request, fields):
    _request(request, 'POST')
    if request['query']:
        raise ValueError('Pool operation accepts no query overrides')
    data = _parse(request['body'])
    if type(data) is not dict or set(data) != fields:
        raise ValueError('Invalid closed pool request')
    bounded_json(data)
    return data


async def read_cycler_list(request):
    data = _body(request, {'filters', 'sort_by'})
    rows, _ = await read_pool_catalogue()
    result = await cycle_list(rows, data['filters'], data['sort_by'])
    return _reply(200, {'success': True, 'loras': result})


async def random_sample(request):
    data = _body(request, {'config', 'loras', 'filters', 'seed'})
    config = {**data['config'], 'roll_mode': 'always', 'execution_seed': None, 'next_seed': data['seed']}
    result = await randomize_pool(config, data['loras'], data['filters'])
    return _reply(200, {'success': True, 'loras': result['ui']['loras']})
