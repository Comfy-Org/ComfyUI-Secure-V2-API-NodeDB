"""Pure closed request/result planning; six exact existing route helpers.
No storage/authentication facade or provider import.
"""
import json

MAX_ENVELOPE_BYTES = 1024 ** 2

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result

def _constant(_value):
    raise ValueError('Nonfinite JSON is not allowed')

def _parse(body):
    if type(body) is not str or len(body) > MAX_ENVELOPE_BYTES:
        raise ValueError('Commit envelope exceeds bounds')
    if len(body.encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise ValueError('Commit envelope exceeds bounds')
    depth = 0
    quoted = escaped = False
    for char in body:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            depth += 1
            if depth > 34:
                raise ValueError('Commit envelope exceeds depth bounds')
        elif char in '}]':
            depth -= 1
    return json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant)

def _revision(value):
    if value is not None and (type(value) is not str or not value
                              or len(value.encode('utf-8')) > 1024):
        raise ValueError('Invalid record revision')

def _reply(status, data):
    text = json.dumps(data, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'))
    if len(text.encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise ValueError('Record response exceeds bounds')
    return {'status': status, 'content_type': 'application/json', 'body': text}

def _request(request, method):
    if (type(request) is not dict or
            set(request) != {'method', 'path', 'query', 'body'} or
            request['method'].upper() != method or
            type(request['query']) is not dict):
        raise ValueError('Invalid closed record request')

ROUTE_PATH = '/api/lm/durable-wildcard-library'


def plan_request(request, method):
    # Closed transport fields only: tenant/pack/key/TTL/format are not overrides.
    _request(request, method)
    if type(request['method']) is not str or request['path'] != ROUTE_PATH:
        raise ValueError('Wrong durable library method or path')
    if request['query']:
        raise ValueError('Durable library accepts no query overrides')
    if method == 'GET':
        if request['body'] != '':
            raise ValueError('Durable library GET accepts no body')
        return None
    if method != 'PUT':
        raise ValueError('Unsupported durable library method')
    value = _parse(request['body'])
    if type(value) is not dict or set(value) != {'entries', 'expected_revision'}:
        raise ValueError('PUT requires only entries and expected_revision')
    if type(value['entries']) is not dict:
        raise ValueError('Whole durable library entries must be an object')
    _revision(value['expected_revision'])
    return value['entries'], value['expected_revision']


def read_response(record):
    if type(record) is not dict or set(record) != {'entries', 'revision'}:
        raise ValueError('Invalid public library read result')
    _revision(record['revision'])
    return _reply(200, {'entries': record['entries'], 'revision': record['revision']})


def save_response(result):
    if (type(result) is not dict or set(result) != {'updated', 'revision'}
            or type(result['updated']) is not bool):
        raise ValueError('Invalid public library CAS result')
    _revision(result['revision'])
    # Explicit concurrency extension. Never reread, merge or retry a collision.
    return _reply(200 if result['updated'] else 409,
                  {'updated': result['updated'], 'revision': result['revision']})


def error_response(exc):
    # Same plain-text error contract as the existing syntax preference author.
    body = str(exc)
    if len(body.encode('utf-8')) > MAX_ENVELOPE_BYTES:
        raise ValueError('Durable library error response exceeds bounds') from exc
    return {'status': 500, 'body': body, 'content_type': 'text/plain'}
