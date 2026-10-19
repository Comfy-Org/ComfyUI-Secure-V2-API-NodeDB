"""Light memory-only image fetch and owner-managed metadata consumers.

Prepared source only; provider implementation/ceilings/runtime remain unqualified. HTTPX below
constructs the original HTTP status exception locally; it performs no request.
"""
import hashlib
import httpx
import torch
from comfy_api.latest import sdk
from ._light_url_codecs import image_from_encoded, metadata_from_encoded

# Bounded consumer requests; trusted provider may deny requests above its ceiling.
MAX_URL_BYTES = 64 * 1024 * 1024
TIMEOUT_SECONDS = 5.0
CHUNK_BYTES = 8 * 1024 * 1024


async def encoded_bytes(assets, asset):
    size = await assets.size(asset)
    if type(size) is not int or not 0 <= size <= MAX_URL_BYTES:
        raise ValueError('Imported image exceeds the bounded consumer byte budget')
    digest = await assets.digest(asset)
    parts = []
    done = 0
    actual = hashlib.sha256()
    while done < size:
        count = min(CHUNK_BYTES, size - done)
        part = await assets.read_range(asset, offset=done, length=count)
        if type(part) is not bytes or len(part) != count:
            raise RuntimeError('Imported image range length differs from its managed asset')
        parts.append(part)
        actual.update(part)
        done += count
    if actual.hexdigest() != digest:
        raise RuntimeError('Imported image bytes differ from their managed asset digest')
    return b''.join(parts)


async def load_image_from_url(url, keep_alpha_channel):
    assets = sdk.ctx().assets
    image_list = []
    for value in url.replace('，', ',').split(','):
        fetched = await assets.fetch_bytes(value.strip(), max_bytes=MAX_URL_BYTES,
            timeout_seconds=TIMEOUT_SECONDS, follow_redirects=False,
            user_agent='default')
        status = fetched['status_code']
        if status == 200:
            payload = fetched['content']
            if type(payload) is not bytes or len(payload) > MAX_URL_BYTES:
                raise RuntimeError('Successful bounded image fetch supplied no admitted bytes')
            image_list.append(image_from_encoded(payload, keep_alpha_channel))
        else:
            if fetched['content'] is not None:
                raise RuntimeError('Bounded image fetch returned content for a rejected status')
            print(f'LoadImageFromURL(Light-Tool): Failed to retrieve image, status code: {status}')
    return (torch.cat(image_list, dim=0),)


def _http_status_response(imported):
    # Root supplies the terminal response fields. Header bytes avoid the
    # default ASCII encoder rejecting an already-decoded non-ASCII Location.
    location = imported['redirect_location']
    headers = [] if location is None else [(b'location', location.encode('utf-8'))]
    response = httpx.Response(imported['status_code'], headers=headers,
        request=httpx.Request('GET', imported['response_url']),
        extensions={'reason_phrase': imported['reason_phrase'].encode('ascii')})
    response.headers.encoding = 'utf-8'
    return response


def _metadata_imported_name(imported_name):
    # The name comes from the trusted import result, never from URL authority
    # or a caller-selected owner. Trusted deletion must recheck this owner
    # against its active authenticated dispatch, not rely on this parsing.
    if type(imported_name) is not str:
        raise RuntimeError('Managed URL import supplied no owned input name')
    parts = imported_name.split('/')
    if (len(parts) != 4 or parts[0] != '.imports'
            or len(parts[1]) != 64 or len(parts[2]) != 32
            or any(char not in '0123456789abcdef' for char in parts[1] + parts[2])):
        raise RuntimeError('Managed URL import supplied no owned input name')
    _metadata_logical_name(imported_name)
    return imported_name


def _metadata_logical_name(name):
    if (len(name.encode('utf-8')) > 1024
            or any(char in name for char in ('\\', ':', '\x00'))
            or any(part in ('', '.', '..') or len(part.encode('utf-8')) > 255
                   for part in name.split('/'))):
        raise ValueError('Metadata filename is outside the managed logical-name policy')


def _metadata_owned_names(image_url, imported_name):
    imported_name = _metadata_imported_name(imported_name)
    # Preserve the original requested-URL expression exactly: this filename
    # precedes redirect resolution and deliberately adds another .png suffix.
    filename = image_url.split('?')[0].rsplit('/')[-1] + '.png'
    owner = imported_name.split('/')[1]
    target = f'.imports/{owner}/light-tool-metadata/{filename}'
    _metadata_logical_name(target)
    return imported_name, target


async def load_metadata_from_url(image_url):
    assets = sdk.ctx().assets
    imported = await assets.import_url(image_url, max_bytes=MAX_URL_BYTES,
        timeout_seconds=TIMEOUT_SECONDS, follow_redirects=True, user_agent='light_tool_browser')
    status = imported['status_code']
    if not 200 <= status < 300:
        _http_status_response(imported).raise_for_status()
    source = imported['asset']
    if source is None:
        raise RuntimeError('Successful managed URL import supplied no asset')
    # Existing delete_input must route .imports names through the optional
    # owner-aware provider hook under assets.import_url.manage. There is no
    # fallback here to broad native input deletion or assets.delete.
    source_name = None
    operation_error = None
    try:
        # Establish a safe cleanup candidate before target validation can fail.
        # The trusted hook still independently verifies active owner authority.
        source_name = _metadata_imported_name(imported['name'])
        _, name = _metadata_owned_names(image_url, source_name)
        await assets.delete_input(name)
        copied = await assets.copy_input(source, name=name, max_bytes=MAX_URL_BYTES)
        if copied['name'] != name or copied['asset'] is None:
            raise RuntimeError('Managed metadata copy supplied no matching input object')
    except BaseException as error:
        operation_error = error
        raise
    finally:
        cleanup_errors = []
        try:
            if source_name is not None:
                await assets.delete_input(source_name)
        except BaseException as error:
            cleanup_errors.append(error)
        # Releasing the source handle is independent of deleting its file and
        # must still be attempted if deletion itself fails or is cancelled.
        try:
            await source.release()
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            if operation_error is not None:
                raise BaseExceptionGroup('Metadata import operation and cleanup failed',
                                         [operation_error, *cleanup_errors]) from None
            if len(cleanup_errors) == 1:
                raise cleanup_errors[0]
            raise BaseExceptionGroup('Metadata import cleanup failed', cleanup_errors) from None
    print(f'File downloaded as input/{name}')
    payload = await encoded_bytes(assets, copied['asset'])
    return (metadata_from_encoded(payload),)
