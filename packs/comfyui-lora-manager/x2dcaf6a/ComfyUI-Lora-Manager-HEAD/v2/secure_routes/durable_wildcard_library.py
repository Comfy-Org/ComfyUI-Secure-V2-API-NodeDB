"""Private whole-library author; registration and authenticated profile HELD.

These module-level mappings use the existing guest route context. Authority is
host-assigned, never selected by query/body. No native file/search/editor parity.
"""
from ..secure_services.durable_wildcard_library import read_library, save_library
from ..secure_services.durable_wildcard_requests import (
    plan_request, read_response, save_response, error_response,
)


async def get_library(request):
    try:
        plan_request(request, 'GET')
        return read_response(await read_library())
    except Exception as exc:
        return error_response(exc)


async def put_library(request):
    try:
        entries, revision = plan_request(request, 'PUT')
        # Existing service validates and bounds the entire encoded document
        # BEFORE resolving storage. Exactly one CAS; no pre-read, retry or merge.
        return save_response(await save_library(entries, revision))
    except Exception as exc:
        return error_response(exc)
