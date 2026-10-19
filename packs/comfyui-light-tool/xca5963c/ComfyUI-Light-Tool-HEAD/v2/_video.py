"""Light Tool video behavior over bounded managed-asset primitives."""
import uuid

import httpx
from comfy_api.latest import io, sdk


MAX_BYTES = 64 * 1024 * 1024
TIMEOUT_SECONDS = 5.0
SOURCE_PREFIX = 'comfy-media-source:v1:'


async def _source(video_url):
    assets = sdk.ctx().assets
    if video_url.startswith(SOURCE_PREFIX):
        return await assets.resolve_media_source(video_url)
    imported = await assets.import_url(
        video_url, max_bytes=MAX_BYTES, timeout_seconds=TIMEOUT_SECONDS,
        follow_redirects=True, user_agent='light_tool_browser')
    if not 200 <= imported['status_code'] < 300:
        # The broker does not expose the final redirect URL. Preserve status
        # failure, without claiming the original httpx exception text matches.
        httpx.Response(imported['status_code'], request=httpx.Request('GET', video_url)).raise_for_status()
    return imported['asset']


def _destination(save_dir):
    filename = str(uuid.uuid4()) + '.mp4'
    # Core validates the full logical name again at the actual copy boundary.
    return filename, f'{save_dir}/{filename}' if save_dir else filename


async def load_video(video_url, server, save_dir):
    source = await _source(video_url)
    filename, name = _destination(save_dir)
    saved = await sdk.ctx().assets.copy_input(source, name=name, max_bytes=MAX_BYTES)
    handle = await sdk.ctx().assets.media_source(saved['asset'])
    # server is a retained legacy socket, never authority to choose a host URL.
    return io.NodeOutput(filename, saved['name'], handle)


async def preview_video(video_url):
    source = await _source(video_url)
    return io.NodeOutput(ui=await sdk.ctx().ui.preview_video(source))


async def save_video(video_url, server, save_dir):
    source = await _source(video_url)
    _, name = _destination(save_dir)
    saved = await sdk.ctx().output.copy_asset(source, name=name, max_bytes=MAX_BYTES)
    return io.NodeOutput(ui=await sdk.ctx().ui.preview_video(saved['asset']))
